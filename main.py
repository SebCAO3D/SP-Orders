"""Point d'entrée : extraction -> consolidation -> email -> passage en « Commandée »."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from src.aggregator import build_lots
from src.baserow_client import BaserowClient
from src.models import Settings
from src.notifier import send_summary

PARIS = ZoneInfo("Europe/Paris")
CUTOFF = (16, 30)

log = logging.getLogger("daily_orders")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    now = datetime.now(PARIS)

    # Le cron GitHub est en UTC : on ne traite qu'à partir de 16h30 heure de Paris, un jour ouvré.
    if not settings.force_run:
        if now.weekday() >= 5:
            log.info("Week-end : rien à faire.")
            return 0
        if (now.hour, now.minute) < CUTOFF:
            log.info("Il est %s à Paris : avant 16h30, déclenchement ignoré.", now.strftime("%H:%M"))
            return 0

    client = BaserowClient(settings)
    rows = client.fetch_pending(up_to=now.date())
    if not rows:
        log.info("Aucune ligne « En attente » : pas d'email.")
        return 0

    lots = build_lots(rows)
    log.info("%d ligne(s) -> %d lot(s)", len(rows), len(lots))

    # Email d'abord : si l'envoi échoue, les lignes restent « En attente » et la
    # prochaine exécution recommence (aucune commande perdue).
    send_summary(settings, lots, now.date())
    client.mark_ordered([r.id for r in rows])
    log.info("Email envoyé, %d ligne(s) passée(s) en Commandée.", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
