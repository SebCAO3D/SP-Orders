# Commandes SP – réapprovisionnement Michelin

Garages (SP) → `index.html` (GitHub Pages) → **passerelle Cloudflare Worker** → Baserow →
GitHub Actions (16h30) → email à l'administrateur → saisie manuelle dans BibServ.

## Pourquoi une passerelle (Worker) ?

GitHub Pages est statique : tout ce qui est dans `index.html` est lisible par les garages.
Y mettre le token Baserow permettrait à n'importe quel mécanicien de lire **toutes** les
commandes et **tous** les clients des autres garages. Le Worker (gratuit) garde le token
côté serveur, impose la clé de chaque garage, ne renvoie que ses lieux et ses lignes,
et refuse tout ce qui est hors périmètre (lieux, modifications, suppressions).
Il applique aussi côté serveur : date du jour, anti-doublon, désignation, code tiers, cut-off.

## Arborescence

```
index.html                      front garage (à publier sur GitHub Pages)
worker/src/index.js             passerelle API (Cloudflare Workers)
worker/wrangler.toml
main.py + src/*.py              chaîne Python 3.11+ (Pydantic)
.github/workflows/daily_orders.yml
config/*.example.json           modèles de configuration (garages, catalogue)
```

## Mise en route (≈ 30 min)

### 1. Baserow
Créez une table **Commandes** avec ces champs (noms exacts) :
`Date` (date, format ISO, sans heure) · `Garage` (texte) · `Lieu_Livraison` (texte) ·
`Code_Tiers_Livre` (texte) · `Code_CAI` (texte) · `Designation` (texte) ·
`Quantite` (nombre, 0 décimale) · `Statut` (choix unique : **En attente** / **Commandée**).
Créez un *Database token* (Paramètres → Tokens API) avec droits création, lecture,
modification et suppression sur cette table. Notez l'ID de la table (dans l'URL).

### 2. Configuration des garages et du catalogue
Copiez `config/garages.example.json` → `config/garages.json` et
`config/catalog.example.json` → `config/catalog.json`, puis adaptez-les.
Générez une clé par garage : `openssl rand -hex 24`. Ces deux fichiers ne sont **jamais**
commités (ils sont dans `.gitignore`) : ils vont dans les secrets du Worker.
Stock du catalogue : `ok` 🟢, `faible` 🟠, `rupture` 🔴 (non commandable).

### 3. Déployer le Worker
```bash
cd worker
npx wrangler login
npx wrangler deploy                       # affiche l'URL https://commandes-sp.XXX.workers.dev
npx wrangler secret put BASEROW_API_URL           # ex. https://api.baserow.io
npx wrangler secret put BASEROW_TOKEN
npx wrangler secret put BASEROW_ORDERS_TABLE_ID
npx wrangler secret put ALLOWED_ORIGIN            # https://VOTRE-USER.github.io  (sans slash final)
npx wrangler secret put GARAGES_JSON  < ../config/garages.json
npx wrangler secret put CATALOG_JSON  < ../config/catalog.json
```
Après toute modification des JSON, relancez les deux dernières commandes.

### 4. Front garage
Dans `index.html`, remplacez `API_URL` par l'URL du Worker. Poussez le dépôt sur GitHub,
puis Settings → Pages → branche `main`, dossier racine. Lien à donner à chaque garage :

`https://VOTRE-USER.github.io/VOTRE-DEPOT/?garage=nord&k=LA_CLE_DU_GARAGE_NORD`

(le lien est personnel : chaque clé n'ouvre que son garage).

### 5. GitHub Actions
Settings → Secrets and variables → Actions :
* **Secrets** : `BASEROW_API_URL`, `BASEROW_TOKEN`, `BASEROW_ORDERS_TABLE_ID`, `SMTP_HOST`
  (`smtp.gmail.com`), `SMTP_PORT` (`587`), `SMTP_USER`, `SMTP_PASS`, `NOTIFICATION_EMAIL`.
  Pour Gmail, `SMTP_PASS` est un **mot de passe d'application** (validation en 2 étapes requise).
* **Variable** (onglet Variables) : `BIBSERV_URL` = adresse de votre espace BibServ.

Test : onglet Actions → *Consolidation quotidienne* → Run workflow, case « force » cochée.

## Points à connaître

* **Heure d'été/hiver** : le cron GitHub est en UTC. Deux déclencheurs (14h30 et 15h30 UTC)
  couvrent les deux saisons ; `main.py` ignore celui qui tombe avant 16h30 à Paris, et le
  second passage ne fait rien s'il n'y a plus de ligne « En attente ».
* **Retard possible** : GitHub peut retarder un cron de plusieurs minutes aux heures de pointe.
  L'email de 16h32 n'est donc pas garanti à la minute près.
* **Après 16h30 et le week-end** : la saisie est refusée (cohérent avec « date infalsifiable »
  et « modifiable jusqu'à 16h29 »). Si une exécution est manquée, les lignes restent « En attente »
  et sont reprises à l'exécution suivante.
* **Email avant statut** : l'email part d'abord, puis les lignes passent en « Commandée ».
  Si l'envoi échoue, rien n'est perdu ; si le passage de statut échouait après l'envoi, un
  doublon d'email serait possible (préférable à une commande oubliée).
* **Ajouter un garage / client** : éditez `garages.json`, relancez `wrangler secret put GARAGES_JSON`.
* **Révoquer un accès** : changez la clé du garage dans `garages.json` et redéployez le secret.
