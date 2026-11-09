"""Client minimal de l'API Baserow (extraction des lignes en attente, passage en Commandée)."""

from __future__ import annotations

from datetime import date

import requests

from .models import OrderRow, Settings

PENDING = "En attente"
ORDERED = "Commandée"
BATCH_SIZE = 200
TIMEOUT = 30


def _select_value(raw: object) -> str:
    """Un champ « choix unique » revient sous forme d'objet {id, value, color}."""
    if isinstance(raw, dict):
        return str(raw.get("value", ""))
    return str(raw or "")


class BaserowClient:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Token {settings.baserow_token}"})
        self._table = f"{settings.baserow_api_url}/api/database/rows/table/{settings.baserow_orders_table_id}"

    def fetch_pending(self, up_to: date) -> list[OrderRow]:
        """Lignes « En attente » dont la date est <= up_to.

        Les reliquats d'un jour précédent (exécution manquée) sont repris, pour qu'aucune
        commande ne reste bloquée.
        """
        url: str | None = f"{self._table}/"
        params: dict[str, str | int] | None = {
            "user_field_names": "true",
            "size": BATCH_SIZE,
            "filter__Statut__contains": "attente",
            "order_by": "id",
        }
        rows: list[OrderRow] = []
        while url:
            resp = self._session.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            for r in data["results"]:
                if _select_value(r.get("Statut")) != PENDING:
                    continue
                row = OrderRow(
                    id=r["id"],
                    date=r["Date"],
                    garage=r.get("Garage") or "",
                    lieu_livraison=r.get("Lieu_Livraison") or "",
                    code_tiers_livre=(r.get("Code_Tiers_Livre") or "").strip(),
                    code_cai=str(r.get("Code_CAI") or "").strip(),
                    designation=r.get("Designation") or "",
                    quantite=int(r["Quantite"]),
                    statut=PENDING,
                )
                if row.date <= up_to:
                    rows.append(row)
            url = data.get("next")  # l'URL suivante contient déjà les paramètres
            params = None
        return rows

    def mark_ordered(self, row_ids: list[int]) -> None:
        """Bascule les lignes en « Commandée » par lots de 200."""
        for i in range(0, len(row_ids), BATCH_SIZE):
            chunk = row_ids[i : i + BATCH_SIZE]
            resp = self._session.patch(
                f"{self._table}/batch/",
                params={"user_field_names": "true"},
                json={"items": [{"id": rid, "Statut": ORDERED} for rid in chunk]},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
