"""Consolidation : 1 lot = 1 Code Tiers Livré ; quantités des CAI identiques additionnées."""

from __future__ import annotations

from collections import defaultdict

from .models import Line, Lot, OrderRow


def build_lots(rows: list[OrderRow]) -> list[Lot]:
    by_tiers: dict[str, list[OrderRow]] = defaultdict(list)
    for row in rows:
        by_tiers[row.code_tiers_livre].append(row)

    lots: list[Lot] = []
    for tiers, group in sorted(by_tiers.items()):
        qty: dict[str, int] = defaultdict(int)
        names: dict[str, str] = {}
        for row in group:
            qty[row.code_cai] += row.quantite
            names.setdefault(row.code_cai, row.designation)
        lots.append(
            Lot(
                code_tiers_livre=tiers,
                lieu_livraison=group[0].lieu_livraison,
                garages=sorted({r.garage for r in group}),
                lignes=[
                    Line(code_cai=cai, designation=names[cai], quantite=q)
                    for cai, q in sorted(qty.items())
                ],
            )
        )
    return lots
