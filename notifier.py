"""Email HTML récapitulatif envoyé à l'administrateur via SMTP (Gmail)."""

from __future__ import annotations

import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from html import escape

from .models import Lot, Settings


def render_html(lots: list[Lot], day: date, bibserv_url: str) -> str:
    blocks: list[str] = []
    for lot in lots:
        rows = "".join(
            f"<tr><td style='padding:6px 10px;border-bottom:1px solid #e3e8f0'>{escape(l.code_cai)}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e3e8f0'>{escape(l.designation)}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e3e8f0;text-align:right;"
            f"font-weight:700'>{l.quantite}</td></tr>"
            for l in lot.lignes
        )
        blocks.append(
            f"<div style='margin:0 0 22px'>"
            f"<div style='background:#002f6c;color:#fff;padding:10px 14px;border-radius:6px 6px 0 0'>"
            f"<strong>{escape(lot.code_tiers_livre)}</strong> – {escape(lot.lieu_livraison)}"
            f"<span style='float:right;color:#f8c200'>{lot.total} pneu(s)</span></div>"
            f"<table style='width:100%;border-collapse:collapse;font-size:14px'>"
            f"<tr style='background:#f4f6fa;text-align:left'><th style='padding:6px 10px'>CAI</th>"
            f"<th style='padding:6px 10px'>Désignation</th>"
            f"<th style='padding:6px 10px;text-align:right'>Qté nette</th></tr>{rows}</table>"
            f"<div style='font-size:12px;color:#5b6678;padding:4px 2px'>Garages : "
            f"{escape(', '.join(lot.garages))}</div></div>"
        )
    total = sum(lot.total for lot in lots)
    return (
        "<div style='font-family:Arial,Helvetica,sans-serif;max-width:680px;margin:auto;color:#14213d'>"
        f"<h2 style='color:#002f6c;margin-bottom:4px'>Commandes du {day.strftime('%d/%m/%Y')}</h2>"
        f"<p style='margin-top:0'>{len(lots)} lot(s) – {total} pneu(s) au total.</p>"
        f"{''.join(blocks)}"
        f"<p><a href='{escape(bibserv_url, quote=True)}' style='background:#f8c200;color:#002f6c;"
        "padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:700;display:inline-block'>"
        "Ouvrir BibServ</a></p>"
        "<p style='font-size:12px;color:#5b6678'>Un lot = un Code Tiers Livré. "
        "Aucune commande n'est passée automatiquement : saisissez ces paniers vous-même dans BibServ.</p>"
        "</div>"
    )


def render_text(lots: list[Lot], day: date) -> str:
    out = [f"Commandes du {day.strftime('%d/%m/%Y')}", ""]
    for lot in lots:
        out.append(f"{lot.code_tiers_livre} - {lot.lieu_livraison} ({lot.total} pneu(s))")
        out += [f"  {l.code_cai}  {l.designation}  x{l.quantite}" for l in lot.lignes]
        out.append("")
    return "\n".join(out)


def send_summary(settings: Settings, lots: list[Lot], day: date) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[BibServ] {len(lots)} lot(s) à commander – {day.strftime('%d/%m/%Y')}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.notification_email
    msg.set_content(render_text(lots, day))
    msg.add_alternative(render_html(lots, day, settings.bibserv_url), subtype="html")

    ctx = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=30) as s:
            s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
