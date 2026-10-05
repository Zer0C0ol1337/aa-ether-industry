"""App-Konfiguration für aa-ether-industry."""

from django.apps import AppConfig

from . import __version__


class EtherIndustryConfig(AppConfig):
    """Registriert die App bei Django und zeigt die Version im Admin-Titel."""

    name = "ether_industry"
    label = "ether_industry"
    verbose_name = f"Ether Industry v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"
