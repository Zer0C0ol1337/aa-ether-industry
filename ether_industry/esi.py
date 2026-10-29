"""Schlanke ESI-Zugriffe für öffentliche Marktdaten (kein Token nötig)."""

import logging
import time

import requests

from .app_settings import ESI_BASE_URL, USER_AGENT

logger = logging.getLogger(__name__)


def _session():
    """Erzeugt eine Session mit dem von CCP verlangten User-Agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def _get(session, url, params=None, retries=4):
    """GET mit Wiederholung bei Serverfehlern, Rate-Limits und Netzwerkproblemen."""
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=30)
        except (requests.ConnectionError, requests.Timeout) as exc:
            logger.warning("ESI nicht erreichbar (%s), Versuch %s/%s", exc, attempt, retries)
            time.sleep(5 * attempt)
            continue

        if response.status_code in (420, 429) or response.status_code >= 500:
            wait = int(response.headers.get("Retry-After", 5 * attempt))
            logger.warning("ESI %s für %s, warte %ss", response.status_code, url, wait)
            time.sleep(wait)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError(f"ESI-Anfrage nach {retries} Versuchen fehlgeschlagen: {url}")


def fetch_market_prices():
    """Liefert CCP-Durchschnitts- und Adjusted-Preise aller Items (ein einziger Aufruf)."""
    with _session() as session:
        return _get(session, f"{ESI_BASE_URL}/markets/prices/").json()


def iter_region_orders(region_id):
    """Liefert nacheinander alle offenen Orders einer Region, Seite für Seite."""
    url = f"{ESI_BASE_URL}/markets/{region_id}/orders/"
    with _session() as session:
        first = _get(session, url, params={"order_type": "all", "page": 1})
        pages = int(first.headers.get("X-Pages", 1))
        yield from first.json()
        for page in range(2, pages + 1):
            yield from _get(session, url, params={"order_type": "all", "page": page}).json()


def fetch_industry_systems():
    """Liefert die Industrie-Kostenindizes aller Systeme (ein einziger Aufruf)."""
    with _session() as session:
        return _get(session, f"{ESI_BASE_URL}/industry/systems/").json()


def fetch_type(type_id):
    """Liefert die Typ-Daten eines Items inklusive Dogma-Attributen."""
    with _session() as session:
        return _get(session, f"{ESI_BASE_URL}/universe/types/{int(type_id)}/").json()


def fetch_dogma_attribute(attribute_id):
    """Liefert Name und Beschreibung eines Dogma-Attributs."""
    with _session() as session:
        return _get(session, f"{ESI_BASE_URL}/dogma/attributes/{int(attribute_id)}/").json()
