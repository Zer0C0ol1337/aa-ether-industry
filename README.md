# aa-ether-industry

**Version 0.1.3** – Industrie- und Trading-Tools für Alliance Auth, gebaut für Ether Element [3THEL].

## Funktionen

- Import aller Blueprints und Rezepte aus der offiziellen CCP-SDE
- Preise aus Jita 4-4 (Sell/Buy) und CCP-Adjusted-Preise, automatisch per Celery
- Industrie-Rechner für Herstellung und Reactions: Materialbedarf mit ME und Struktur-Bonus, Jobkosten, Produktwert, Gewinn und Marge

## Installation unter Docker (offizielles Alliance-Auth-Docker-Setup)

Alle Befehle im Ordner der Auth-Installation auf dem Server, dort wo `docker-compose.yml` und der Ordner `conf/` liegen.

### 1. Plugin eintragen

In `conf/requirements.txt` eine Zeile ergänzen:

```
aa-ether-industry @ git+https://github.com/Zer0C0ol1337/aa-ether-industry.git@v0.1.3
```

### 2. Konfiguration

Am Ende von `conf/local.py`:

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

### 3. Image neu bauen und starten

```bash
docker compose build
docker compose --env-file=.env up -d
```

### 4. Datenbank, Static Files, Daten laden

```bash
docker compose exec allianceauth_gunicorn bash
# jetzt im Container:
auth migrate
auth collectstatic --noinput
auth ether_industry_import_sde
auth shell -c "from ether_industry.tasks import update_all_prices; update_all_prices()"
exit
```

Der SDE-Import dauert ein paar Minuten, der erste Preisabgleich ebenfalls (alle Orders von The Forge).
Den SDE-Import nach größeren EVE-Patches wiederholen.

### 5. Neustart und Rechte

```bash
docker compose restart
```

Im Admin der passenden Gruppe oder dem State das Recht
`ether_industry | general | Kann die Industrie-Tools nutzen` geben.

### Update auf eine neue Version

Versionsnummer in `conf/requirements.txt` anpassen, dann Schritt 3, danach `auth migrate` und `auth collectstatic --noinput` im Container, dann neu starten.

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
