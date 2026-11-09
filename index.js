/**
 * Passerelle API Commandes SP -> Baserow (Cloudflare Worker, offre gratuite).
 *
 * Pourquoi ce composant : GitHub Pages est statique. Mettre le token Baserow dans
 * index.html le rendrait lisible par n'importe quel garage (donc toutes les commandes
 * et tous les clients). Ici le token reste côté serveur, et chaque requête est
 * cloisonnée au garage authentifié.
 *
 * Secrets (wrangler secret put ...) :
 *   BASEROW_API_URL, BASEROW_TOKEN, BASEROW_ORDERS_TABLE_ID,
 *   GARAGES_JSON, CATALOG_JSON, ALLOWED_ORIGIN
 */

const TZ = "Europe/Paris";
const CUTOFF_MINUTES = 16 * 60 + 30; // 16h30
const MAX_QTY = 999;

// ---------- Utilitaires ----------

function parisNow() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    weekday: "short",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const get = (t) => parts.find((p) => p.type === t).value;
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    minutes: Number(get("hour")) * 60 + Number(get("minute")),
    weekday: get("weekday"), // Mon..Sun
  };
}

function orderingState() {
  const n = parisNow();
  if (n.weekday === "Sat" || n.weekday === "Sun") {
    return { open: false, today: n.date, message: "Saisie fermée le week-end. Réouverture lundi." };
  }
  if (n.minutes >= CUTOFF_MINUTES) {
    return {
      open: false,
      today: n.date,
      message: "Clôture de 16h30 passée : les commandes du jour sont parties. Réouverture au prochain jour ouvré.",
    };
  }
  return { open: true, today: n.date, message: "" };
}

function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Headers": "Content-Type, X-Garage, X-Key",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(env, status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...corsHeaders(env) },
  });
}

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function safeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(String(a));
  const y = enc.encode(String(b));
  let diff = x.length ^ y.length;
  const len = Math.max(x.length, y.length);
  for (let i = 0; i < len; i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

function parseJsonSecret(raw, name) {
  try {
    return JSON.parse(raw);
  } catch {
    throw new HttpError(500, `Configuration invalide : ${name}`);
  }
}

// ---------- Authentification et périmètre du garage ----------

function authenticate(request, env) {
  const garageId = (request.headers.get("X-Garage") || "").trim().toLowerCase();
  const key = request.headers.get("X-Key") || "";
  const garages = parseJsonSecret(env.GARAGES_JSON, "GARAGES_JSON");
  const garage = garages[garageId];
  // Comparaison faite même si le garage est inconnu pour limiter les écarts de timing.
  const ok = safeEqual(key, garage ? garage.key : "x".repeat(32));
  if (!garage || !ok || !key) throw new HttpError(401, "Accès refusé. Vérifiez votre lien.");
  return { garageId, garage };
}

/** Lieux de livraison autorisés pour CE garage uniquement. */
function placesOf(garageId, garage) {
  const places = [
    {
      id: "atelier",
      type: "atelier",
      label: garage.atelier.libelle,
      code_tiers: garage.atelier.code_tiers,
    },
  ];
  for (const c of garage.clients || []) {
    places.push({ id: c.id, type: "client", label: c.nom, code_tiers: c.code_tiers });
  }
  return places;
}

function catalogOf(env) {
  const cat = parseJsonSecret(env.CATALOG_JSON, "CATALOG_JSON");
  return Array.isArray(cat) ? cat : [];
}

// ---------- Baserow ----------

function brHeaders(env) {
  return { Authorization: `Token ${env.BASEROW_TOKEN}`, "Content-Type": "application/json" };
}

function brUrl(env, path, query = "") {
  const base = env.BASEROW_API_URL.replace(/\/+$/, "");
  const q = query ? `${query}&` : "";
  return `${base}/api/database/rows/table/${env.BASEROW_ORDERS_TABLE_ID}/${path}?${q}user_field_names=true`;
}

async function brFetch(url, init) {
  const res = await fetch(url, init);
  if (!res.ok) {
    console.error("Baserow", res.status, await res.text().catch(() => ""));
    throw new HttpError(502, "Base de données indisponible. Réessayez dans un instant.");
  }
  return res.status === 204 ? null : res.json();
}

function statusOf(row) {
  const s = row.Statut;
  return typeof s === "object" && s !== null ? s.value : s;
}

function toOrder(row) {
  return {
    id: row.id,
    date: row.Date,
    lieu: row.Lieu_Livraison,
    code_tiers: row.Code_Tiers_Livre,
    cai: row.Code_CAI,
    designation: row.Designation,
    quantite: Number(row.Quantite),
    statut: statusOf(row),
  };
}

async function listGarageRows(env, garageId, today) {
  const q = `filter__Garage__equal=${encodeURIComponent(garageId)}&order_by=-id&size=200`;
  const data = await brFetch(brUrl(env, "", q), { headers: brHeaders(env) });
  // Visible : commandes du jour + celles encore en attente (reliquats d'un jour manqué).
  return data.results.filter((r) => r.Date === today || statusOf(r) === "En attente");
}

async function getOwnedRow(env, garageId, rowId) {
  if (!/^\d+$/.test(rowId)) throw new HttpError(400, "Identifiant invalide.");
  const res = await fetch(brUrl(env, `${rowId}/`), { headers: brHeaders(env) });
  if (res.status === 404) throw new HttpError(404, "Ligne introuvable.");
  if (!res.ok) throw new HttpError(502, "Base de données indisponible.");
  const row = await res.json();
  // 404 (et non 403) pour ne rien révéler de l'existence d'une ligne d'un autre garage.
  if (row.Garage !== garageId) throw new HttpError(404, "Ligne introuvable.");
  return row;
}

function assertEditable(row, state) {
  if (!state.open) throw new HttpError(409, state.message);
  if (statusOf(row) !== "En attente" || row.Date !== state.today) {
    throw new HttpError(409, "Cette ligne n'est plus modifiable.");
  }
}

function parseQty(value) {
  const q = Number(value);
  if (!Number.isInteger(q) || q < 1 || q > MAX_QTY) {
    throw new HttpError(400, `Quantité invalide (entier de 1 à ${MAX_QTY}).`);
  }
  return q;
}

// ---------- Routes ----------

async function handle(request, env) {
  const url = new URL(request.url);
  const { garageId, garage } = authenticate(request, env);
  const state = orderingState();
  const places = placesOf(garageId, garage);
  const path = url.pathname.replace(/\/+$/, "");

  if (request.method === "GET" && path === "/api/config") {
    return json(env, 200, {
      garage: { id: garageId, nom: garage.nom },
      lieux: places,
      catalogue: catalogOf(env),
      today: state.today,
      open: state.open,
      message: state.message,
    });
  }

  if (request.method === "GET" && path === "/api/orders") {
    const rows = await listGarageRows(env, garageId, state.today);
    return json(env, 200, { today: state.today, open: state.open, orders: rows.map(toOrder) });
  }

  if (request.method === "POST" && path === "/api/orders") {
    if (!state.open) throw new HttpError(409, state.message);
    const body = await request.json().catch(() => ({}));
    const place = places.find((p) => p.id === body.lieu_id);
    if (!place) throw new HttpError(400, "Lieu de livraison non autorisé.");
    const item = catalogOf(env).find((c) => String(c.cai) === String(body.cai));
    if (!item) throw new HttpError(400, "Code CAI inconnu.");
    if (item.stock === "rupture") throw new HttpError(409, "Référence en rupture de stock.");
    const quantite = parseQty(body.quantite);

    // Anti-doublon : Date + Garage + Tiers livré + CAI (vérifié côté serveur).
    const existing = await listGarageRows(env, garageId, state.today);
    const dup = existing.find(
      (r) =>
        r.Date === state.today &&
        r.Code_Tiers_Livre === place.code_tiers &&
        String(r.Code_CAI) === String(item.cai),
    );
    if (dup) {
      throw new HttpError(409, "Cette référence est déjà dans le panier pour ce lieu. Ajustez la quantité sur la ligne existante.");
    }

    const created = await brFetch(brUrl(env, ""), {
      method: "POST",
      headers: brHeaders(env),
      body: JSON.stringify({
        Date: state.today,
        Garage: garageId,
        Lieu_Livraison: place.label,
        Code_Tiers_Livre: place.code_tiers,
        Code_CAI: String(item.cai),
        Designation: item.designation,
        Quantite: quantite,
        Statut: "En attente",
      }),
    });
    return json(env, 201, { order: toOrder(created) });
  }

  const m = path.match(/^\/api\/orders\/(\d+)$/);
  if (m && request.method === "PATCH") {
    const row = await getOwnedRow(env, garageId, m[1]);
    assertEditable(row, state);
    const body = await request.json().catch(() => ({}));
    const quantite = parseQty(body.quantite);
    const updated = await brFetch(brUrl(env, `${row.id}/`), {
      method: "PATCH",
      headers: brHeaders(env),
      body: JSON.stringify({ Quantite: quantite }),
    });
    return json(env, 200, { order: toOrder(updated) });
  }

  if (m && request.method === "DELETE") {
    const row = await getOwnedRow(env, garageId, m[1]);
    assertEditable(row, state);
    await brFetch(brUrl(env, `${row.id}/`), { method: "DELETE", headers: brHeaders(env) });
    return json(env, 200, { deleted: row.id });
  }

  throw new HttpError(404, "Route inconnue.");
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }
    try {
      return await handle(request, env);
    } catch (err) {
      if (err instanceof HttpError) return json(env, err.status, { error: err.message });
      console.error(err);
      return json(env, 500, { error: "Erreur interne." });
    }
  },
};
