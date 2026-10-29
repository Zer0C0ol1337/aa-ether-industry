"""Datenmodelle: Items, Blueprints mit Rezepten und Marktpreise."""

from django.db import models


class General(models.Model):
    """Nur für Rechte, ohne eigene Tabelle (Muster aus aa-miningtax)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Kann die Industrie-Tools nutzen"),
            ("manage_industry", "Kann Einstellungen und Daten verwalten"),
        )


class ItemType(models.Model):
    """Ein Item aus der SDE (Schiff, Modul, Mineral, Blueprint …)."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    name_de = models.CharField(max_length=255, blank=True, default="", db_index=True)
    group_id = models.PositiveIntegerField(null=True, blank=True)
    category_id = models.PositiveIntegerField(null=True, blank=True)
    market_group_id = models.PositiveIntegerField(null=True, blank=True)
    volume = models.FloatField(null=True, blank=True)
    published = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        ordering = ["name"]

    def __str__(self):
        """Anzeigename im Admin."""
        return self.name


class Blueprint(models.Model):
    """Ein Blueprint; der Schlüssel ist die Type-ID des Blueprints selbst."""

    type = models.OneToOneField(
        ItemType, primary_key=True, on_delete=models.CASCADE, related_name="blueprint"
    )
    max_production_limit = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()

    def __str__(self):
        """Anzeigename im Admin."""
        return self.type.name


class BlueprintActivity(models.Model):
    """Eine Tätigkeit eines Blueprints (Bauen, Reaction, Erfindung …) mit Dauer."""

    # Die Zahlen entsprechen den activityIDs von CCP
    MANUFACTURING = 1
    RESEARCH_TIME = 3
    RESEARCH_MATERIAL = 4
    COPYING = 5
    INVENTION = 8
    REACTION = 11

    ACTIVITY_CHOICES = (
        (MANUFACTURING, "Herstellung"),
        (RESEARCH_TIME, "TE-Forschung"),
        (RESEARCH_MATERIAL, "ME-Forschung"),
        (COPYING, "Kopieren"),
        (INVENTION, "Erfindung"),
        (REACTION, "Reaction"),
    )

    # Zuordnung SDE-Schlüssel -> activityID
    SDE_KEYS = {
        "manufacturing": MANUFACTURING,
        "research_time": RESEARCH_TIME,
        "research_material": RESEARCH_MATERIAL,
        "copying": COPYING,
        "invention": INVENTION,
        "reaction": REACTION,
    }

    # Feste ID = blueprint_id * 100 + activityID, damit der Import ohne Rückgabe-IDs auskommt
    id = models.BigIntegerField(primary_key=True)
    blueprint = models.ForeignKey(Blueprint, on_delete=models.CASCADE, related_name="activities")
    activity = models.PositiveSmallIntegerField(choices=ACTIVITY_CHOICES)
    time = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()
        unique_together = ("blueprint", "activity")

    @staticmethod
    def make_id(blueprint_id, activity):
        """Berechnet die feste Primärschlüssel-ID einer Tätigkeit."""
        return int(blueprint_id) * 100 + int(activity)

    def __str__(self):
        """Anzeigename im Admin."""
        return f"{self.blueprint} – {self.get_activity_display()}"


class ActivityMaterial(models.Model):
    """Ein benötigtes Material einer Tätigkeit (Grundmenge pro Run)."""

    activity = models.ForeignKey(BlueprintActivity, on_delete=models.CASCADE, related_name="materials")
    type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField()

    class Meta:
        default_permissions = ()


class ActivityProduct(models.Model):
    """Ein Ergebnis einer Tätigkeit (Menge pro Run, bei Erfindung mit Chance)."""

    activity = models.ForeignKey(BlueprintActivity, on_delete=models.CASCADE, related_name="products")
    type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name="produced_by")
    quantity = models.PositiveIntegerField()
    probability = models.FloatField(null=True, blank=True)

    class Meta:
        default_permissions = ()


class ItemPrice(models.Model):
    """Preise eines Items: CCP-Durchschnitt/Adjusted sowie Jita Sell/Buy."""

    type = models.OneToOneField(ItemType, primary_key=True, on_delete=models.CASCADE, related_name="price")
    adjusted_price = models.FloatField(null=True, blank=True)
    average_price = models.FloatField(null=True, blank=True)
    jita_sell = models.FloatField(null=True, blank=True)
    jita_buy = models.FloatField(null=True, blank=True)
    adjusted_updated = models.DateTimeField(null=True, blank=True)
    jita_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()


class IndustryStructure(models.Model):
    """Eine Industrie-Struktur der Corp (aus Corptools bzw. aa-structures), mit System, Sicherheit und eingebauten Rigs."""

    structure_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    type_id = models.PositiveIntegerField()
    system_id = models.PositiveIntegerField(null=True, blank=True)
    system_name = models.CharField(max_length=100, blank=True, default="")
    security_status = models.FloatField(null=True, blank=True)
    corporation_name = models.CharField(max_length=255, blank=True, default="")
    rig_type_ids = models.JSONField(default=list, blank=True)
    rig_source = models.CharField(
        max_length=20, blank=True, default="", help_text="Woher die Rigs stammen: corptools oder aa-structures."
    )
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ["name"]

    def __str__(self):
        """Anzeigename im Admin und in der Auswahl."""
        return self.name


class RigType(models.Model):
    """Boni eines Struktur-Rigs aus seiner Dogma (eve_sde oder ESI), Prozentwerte positiv, ohne Sicherheits-Multiplikator.

    from_dogma = True heißt: echte Dogma-Werte gefunden (lokal aus eve_sde oder aus der ESI).
    """

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    material_bonus = models.FloatField(default=0)
    time_bonus = models.FloatField(default=0)
    cost_bonus = models.FloatField(default=0)
    hisec_mod = models.FloatField(null=True, blank=True)
    lowsec_mod = models.FloatField(null=True, blank=True)
    nullsec_mod = models.FloatField(null=True, blank=True)
    from_dogma = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ["name"]

    def __str__(self):
        """Anzeigename im Admin."""
        return self.name


class SystemCostIndex(models.Model):
    """Industrie-Kostenindex eines Sonnensystems aus der ESI, in Prozent."""

    system_id = models.PositiveIntegerField(primary_key=True)
    manufacturing = models.FloatField(default=0)
    reaction = models.FloatField(default=0)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
