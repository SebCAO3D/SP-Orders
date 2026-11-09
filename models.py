"""Modèles de données et configuration, validés par Pydantic (sans dépendance en plus)."""

from __future__ import annotations

import os
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Configuration lue dans les variables d'environnement (GitHub Secrets)."""

    model_config = ConfigDict(frozen=True)

    baserow_api_url: str
    baserow_token: str
    baserow_orders_table_id: int
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_pass: str
    notification_email: str
    bibserv_url: str = "https://www.bibserv.michelin.com"
    force_run: bool = False

    @field_validator("baserow_api_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            baserow_api_url=env["BASEROW_API_URL"],
            baserow_token=env["BASEROW_TOKEN"],
            baserow_orders_table_id=int(env["BASEROW_ORDERS_TABLE_ID"]),
            smtp_host=env["SMTP_HOST"],
            smtp_port=int(env.get("SMTP_PORT") or 587),
            smtp_user=env["SMTP_USER"],
            smtp_pass=env["SMTP_PASS"],
            notification_email=env["NOTIFICATION_EMAIL"],
            bibserv_url=env.get("BIBSERV_URL") or "https://www.bibserv.michelin.com",
            force_run=env.get("FORCE_RUN") == "1",
        )


class OrderRow(BaseModel):
    """Une ligne de la table Commandes Baserow."""

    id: int
    date: date
    garage: str
    lieu_livraison: str
    code_tiers_livre: str
    code_cai: str
    designation: str
    quantite: int = Field(gt=0)
    statut: str


class Line(BaseModel):
    """Ligne consolidée : un CAI, quantité nette pour un lot."""

    code_cai: str
    designation: str
    quantite: int


class Lot(BaseModel):
    """1 lot = 1 Code Tiers Livré Michelin unique."""

    code_tiers_livre: str
    lieu_livraison: str
    garages: list[str]
    lignes: list[Line]

    @property
    def total(self) -> int:
        return sum(line.quantite for line in self.lignes)
