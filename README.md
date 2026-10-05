# aa-ether-industry

**Version 0.1.0** – Industrie- und Trading-Tools für Alliance Auth, gebaut für Ether Element [3THEL].

## Funktionen (0.1.0)

- Import aller Blueprints und Rezepte aus der offiziellen CCP-SDE
- Tägliche Preise aus Jita 4-4 (Sell/Buy) und CCP-Adjusted-Preise
- Industrie-Rechner für Herstellung und Reactions: Materialbedarf mit ME und Struktur-Bonus, Jobkosten, Produktwert, Gewinn und Marge

## Installation

```bash
# im venv der Auth-Installation
pip install -e /pfad/zu/aa-ether-industry
```

In `local.py`:

```python
INSTALLED_APPS += ["ether_industry"]

# Pflicht laut CCP: User-Agent mit Kontakt
ETHER_INDUSTRY_USER_AGENT = "aa-ether-industry (Ether Element; Kontakt: dein-ingame-name / discord)"

# Preise alle 6 Stunden aktualisieren
from celery.schedules import crontab
CELERYBEAT_SCHEDULE["ether_industry_update_prices"] = {
    "task": "ether_industry.tasks.update_all_prices",
    "schedule": crontab(minute=20, hour="*/6"),
}
```

Danach:

```bash
python manage.py makemigrations ether_industry   # nur beim ersten Mal, Migration ins Repo committen
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py ether_industry_import_sde       # nach jedem größeren EVE-Patch wiederholen
python manage.py shell -c "from ether_industry.tasks import update_all_prices; update_all_prices()"
```

Zum Schluss Auth und Celery neu starten und der passenden Gruppe/State das Recht
`ether_industry | general | Kann die Industrie-Tools nutzen` geben.

## Einstellungen

| Einstellung | Standard | Zweck |
|---|---|---|
| `ETHER_INDUSTRY_USER_AGENT` | Platzhalter | User-Agent für ESI und SDE-Download |
| `ETHER_INDUSTRY_SDE_URL` | neueste CCP-SDE (JSONL) | Quelle für den Import |
| `ETHER_INDUSTRY_ESI_BASE_URL` | `https://esi.evetech.net/latest` | ESI-Adresse |
| `ETHER_INDUSTRY_PRICE_REGION_ID` | `10000002` (The Forge) | Region für Marktpreise |
| `ETHER_INDUSTRY_PRICE_STATION_ID` | `60003760` (Jita 4-4) | Station für Marktpreise |

## Lizenz

GPL-3.0
