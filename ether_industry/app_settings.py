"""Einstellungen des Plugins – alle per local.py überschreibbar."""

from django.conf import settings

from . import __version__

# Offizielle CCP-SDE im JSON-Lines-Format (Kurz-URL leitet immer auf die neueste Version um)
SDE_URL = getattr(
    settings,
    "ETHER_INDUSTRY_SDE_URL",
    "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip",
)

# Basis-URL der ESI
ESI_BASE_URL = getattr(settings, "ETHER_INDUSTRY_ESI_BASE_URL", "https://esi.evetech.net/latest")

# CCP verlangt einen User-Agent mit Kontaktmöglichkeit – bitte in local.py anpassen
USER_AGENT = getattr(
    settings,
    "ETHER_INDUSTRY_USER_AGENT",
    f"aa-ether-industry/{__version__} (Ether Element; bitte Kontakt in local.py setzen)",
)

# Referenzmarkt für Preise: The Forge / Jita IV - Moon 4 - Caldari Navy Assembly Plant
PRICE_REGION_ID = getattr(settings, "ETHER_INDUSTRY_PRICE_REGION_ID", 10000002)
PRICE_STATION_ID = getattr(settings, "ETHER_INDUSTRY_PRICE_STATION_ID", 60003760)
