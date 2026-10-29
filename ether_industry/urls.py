"""URL-Routen des Plugins."""

from django.urls import path

from . import views

app_name = "ether_industry"

urlpatterns = [
    # Produktsuche
    path("", views.index, name="index"),
    # JSON-Vorschläge für die Autovervollständigung
    path("autocomplete/", views.autocomplete, name="autocomplete"),
    # Kostenrechnung für eine Blueprint-Tätigkeit
    path("calc/<int:activity_id>/", views.calculator, name="calculator"),
    # Strukturen, Rigs und Kostenindizes neu einlesen (Verwalter)
    path("structures/sync/", views.sync_structures, name="sync_structures"),
]
