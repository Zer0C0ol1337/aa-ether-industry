"""Celery-Tasks für den Preisabgleich."""

import logging

from celery import shared_task
from django.utils import timezone

from . import esi
from .app_settings import PRICE_REGION_ID, PRICE_STATION_ID
from .models import ActivityMaterial, ActivityProduct, ItemPrice, ItemType
from .utils import upsert

logger = logging.getLogger(__name__)


@shared_task
def update_adjusted_prices():
    """Speichert die CCP-Preise (adjusted für Jobkosten, average als Rückfallwert)."""
    known = set(ItemType.objects.values_list("type_id", flat=True))
    now = timezone.now()
    objs = [
        ItemPrice(
            type_id=row["type_id"],
            adjusted_price=row.get("adjusted_price"),
            average_price=row.get("average_price"),
            adjusted_updated=now,
        )
        for row in esi.fetch_market_prices()
        if row["type_id"] in known
    ]
    upsert(ItemPrice, objs, ["type"], ["adjusted_price", "average_price", "adjusted_updated"])
    logger.info("CCP-Preise aktualisiert: %s Items", len(objs))
    return len(objs)


@shared_task
def update_jita_prices():
    """Ermittelt günstigstes Sell- und bestes Buy-Angebot in Jita 4-4 für alle Rezept-Items."""
    relevant = set(ActivityMaterial.objects.values_list("type_id", flat=True))
    relevant |= set(ActivityProduct.objects.values_list("type_id", flat=True))

    best_sell, best_buy = {}, {}
    for order in esi.iter_region_orders(PRICE_REGION_ID):
        type_id = order["type_id"]
        if order["location_id"] != PRICE_STATION_ID or type_id not in relevant:
            continue
        price = order["price"]
        if order["is_buy_order"]:
            if price > best_buy.get(type_id, 0):
                best_buy[type_id] = price
        elif type_id not in best_sell or price < best_sell[type_id]:
            best_sell[type_id] = price

    now = timezone.now()
    objs = [
        ItemPrice(type_id=t, jita_sell=best_sell.get(t), jita_buy=best_buy.get(t), jita_updated=now)
        for t in set(best_sell) | set(best_buy)
    ]
    upsert(ItemPrice, objs, ["type"], ["jita_sell", "jita_buy", "jita_updated"])
    logger.info("Jita-Preise aktualisiert: %s Items", len(objs))
    return len(objs)


@shared_task
def update_all_prices():
    """Führt beide Preisabgleiche nacheinander aus (für Celery Beat)."""
    update_adjusted_prices()
    update_jita_prices()
