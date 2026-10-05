"""Admin-Ansichten zum Nachschlagen der importierten Daten."""

from django.contrib import admin

from .models import Blueprint, ItemPrice, ItemType


@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    """Items durchsuchen."""

    list_display = ("type_id", "name", "name_de", "category_id", "published")
    search_fields = ("name", "name_de", "type_id")
    list_filter = ("published",)


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    """Blueprints durchsuchen."""

    list_display = ("type", "max_production_limit")
    search_fields = ("type__name",)
    raw_id_fields = ("type",)


@admin.register(ItemPrice)
class ItemPriceAdmin(admin.ModelAdmin):
    """Preise prüfen."""

    list_display = ("type", "jita_sell", "jita_buy", "adjusted_price", "jita_updated")
    search_fields = ("type__name",)
    raw_id_fields = ("type",)
