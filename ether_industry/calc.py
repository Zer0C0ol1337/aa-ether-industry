"""Rechenlogik für Herstellung und Reactions."""

import math

from .models import BlueprintActivity, ItemPrice

# SCC-Zuschlag auf jeden Industriejob, in Prozent des geschätzten Item-Werts
SCC_SURCHARGE_PCT = 4.0


def adjusted_quantity(base, runs, me_pct, bonus_pct):
    """EVE-Formel: ME und Struktur-Bonus senken den Bedarf, nie unter 1 Stück pro Run."""
    raw = base * runs * (1 - me_pct / 100) * (1 - bonus_pct / 100)
    return max(runs, math.ceil(round(raw, 2)))


def _price(item, mode):
    """Liefert den Stückpreis eines Items: Jita Sell/Buy, sonst CCP-Durchschnitt, sonst 0."""
    try:
        price = item.price
    except ItemPrice.DoesNotExist:
        return 0.0, False
    value = price.jita_sell if mode == "sell" else price.jita_buy
    if value:
        return value, True
    return price.average_price or 0.0, False


def _adjusted(item):
    """Liefert den CCP-Adjusted-Price eines Items (Basis der Jobkosten)."""
    try:
        return item.price.adjusted_price or 0.0
    except ItemPrice.DoesNotExist:
        return 0.0


def calculate(activity, runs, me_pct, bonus_pct, cost_index_pct, facility_tax_pct, material_mode, product_mode,
              time_factor=1.0, structure_cost_bonus_pct=0.0):
    """Berechnet Materialbedarf, Kosten, Produktwert, Gewinn und Bauzeit für eine Tätigkeit.

    bonus_pct: Struktur- und Rig-Materialbonus zusammen (siehe bonuses.combined_material_bonus)
    time_factor: Faktor auf die Grundzeit pro Run aus TE, Struktur, Rig, Skills und Implantat
    structure_cost_bonus_pct: Rollenbonus der Struktur auf den Kostenindex-Anteil der Jobkosten
    TE beeinflusst nur die Zeit, nicht die Jobkosten.
    """
    # ME gilt nur für die Herstellung, nicht für Reactions
    me_effective = me_pct if activity.activity == BlueprintActivity.MANUFACTURING else 0

    materials, material_total, eiv, missing = [], 0.0, 0.0, 0
    for mat in activity.materials.select_related("type", "type__price").order_by("type__name"):
        qty = adjusted_quantity(mat.quantity, runs, me_effective, bonus_pct)
        unit, from_market = _price(mat.type, material_mode)
        total = qty * unit
        material_total += total
        eiv += mat.quantity * runs * _adjusted(mat.type)
        missing += 0 if unit else 1
        materials.append(
            {"type": mat.type, "base": mat.quantity, "qty": qty, "unit": unit, "total": total, "market": from_market}
        )

    index_part = cost_index_pct * (1 - structure_cost_bonus_pct / 100)
    job_cost = eiv * (index_part + facility_tax_pct + SCC_SURCHARGE_PCT) / 100

    products, product_total = [], 0.0
    for prod in activity.products.select_related("type", "type__price"):
        qty = prod.quantity * runs
        unit, from_market = _price(prod.type, product_mode)
        products.append({"type": prod.type, "qty": qty, "unit": unit, "total": qty * unit, "market": from_market})
        product_total += qty * unit

    total_cost = material_total + job_cost
    profit = product_total - total_cost
    base_duration = activity.time * runs
    duration = int(round(base_duration * time_factor))
    hours = duration / 3600
    return {
        "materials": materials,
        "products": products,
        "material_total": material_total,
        "eiv": eiv,
        "job_cost": job_cost,
        "total_cost": total_cost,
        "product_total": product_total,
        "profit": profit,
        "margin_pct": (profit / total_cost * 100) if total_cost else 0.0,
        "missing_prices": missing,
        "base_duration": base_duration,
        "duration": duration,
        "time_saved": base_duration - duration,
        "isk_per_hour": profit / hours if hours else 0.0,
        "index_part_pct": index_part,
    }
