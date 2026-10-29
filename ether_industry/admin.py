"""Admin-Ansichten zum Nachschlagen der importierten Daten."""

from django.contrib import admin

from .models import Blueprint, IndustryStructure, ItemPrice, ItemType, RigType, SystemCostIndex


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


@admin.register(IndustryStructure)
class IndustryStructureAdmin(admin.ModelAdmin):
    """Aus Corptools eingelesene Industrie-Strukturen (werden beim Abgleich überschrieben)."""

    list_display = ("name", "type_id", "system_name", "security_status", "corporation_name", "synced_at")
    search_fields = ("name", "system_name")


@admin.register(RigType)
class RigTypeAdmin(admin.ModelAdmin):
    """Rig-Boni aus der ESI-Dogma."""

    list_display = ("name", "material_bonus", "time_bonus", "hisec_mod", "lowsec_mod", "nullsec_mod", "from_dogma")
    search_fields = ("name",)


@admin.register(SystemCostIndex)
class SystemCostIndexAdmin(admin.ModelAdmin):
    """Kostenindizes der Systeme in Prozent."""

    list_display = ("system_id", "manufacturing", "reaction", "updated")
    search_fields = ("system_id",)

