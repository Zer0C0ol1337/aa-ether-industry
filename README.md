# aa-ether-industry

**Version 0.2.1** – Industrie- und Trading-Tools für Alliance Auth, gebaut für Ether Element [3THEL].

## Funktionen

- Import aller Blueprints und Rezepte aus der offiziellen CCP-SDE
- Preise aus Jita 4-4 (Sell/Buy) und CCP-Adjusted-Preise, automatisch per Celery
- Industrie-Rechner für Herstellung und Reactions: Materialbedarf, Jobkosten, Produktwert, Gewinn, Marge, **Bauzeit und Gewinn pro Stunde**
- **Strukturen aus Corptools und/oder aa-structures** (Raitaru, Azbel, Sotiyo, Athanor, Tatara) mit ihren Rigs: Rollenbonus und Rig-Boni samt Sicherheits-Multiplikator werden im Rechner automatisch eingerechnet, Kostenindex des Systems kommt aus der ESI
- TE, Skills (aus Corptools vorbelegt) und Implantate; ME/TE eigener Corp-Blueprints mit einem Klick

## Installation unter Docker (offizielles Alliance-Auth-Docker-Setup)

Alle Befehle im Ordner der Auth-Installation auf dem Server, dort wo `docker-compose.yml` und der Ordner `conf/` liegen.

### 1. Plugin eintragen

In `conf/requirements.txt` eine Zeile ergänzen:

```
aa-ether-industry @ git+https://github.com/Zer0C0ol1337/aa-ether-industry.git@v0.2.1
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

## Strukturen und Rigs (optional, mit Corptools und/oder aa-structures)

Ist [allianceauth-corptools](https://github.com/pvyParts/allianceauth-corp-tools) installiert, liest das Plugin die Industrie-Strukturen der Corp und die eingebauten Rigs aus.
Voraussetzung: ein **Corp-Token in Corptools** mit Strukturen und Corp-Assets (für ME/TE eigener Blueprints zusätzlich Blueprints).
Ist zusätzlich oder stattdessen die App [Structures (aa-structures)](https://gitlab.com/ErikKalkoken/aa-structures) installiert, liest das Plugin Strukturen und Rigs auch von dort (aa-structures holt die Fittings mit seinem eigenen Owner-Token). Corptools hat Vorrang; fehlen dort die Rigs, werden die aus aa-structures genommen.
Der Abgleich läuft automatisch nach jedem Preisabgleich; Verwalter (`manage_industry`) können ihn auf der Startseite auch von Hand anstoßen.

- Rollenboni: Raitaru/Azbel/Sotiyo Material −1 %, Zeit −15/−20/−30 %, Jobkosten −3/−4/−5 %; Tatara Reaction-Zeit −25 %
- Rig-Boni und Sicherheits-Multiplikatoren kommen aus der Dogma der Rigs – lokal aus django-eveonline-sde (kommt mit Corptools), nur falls dort nicht vorhanden aus der ESI. Welches Rig für welches Produkt gilt, liefert CCP nicht mit – das Plugin ordnet es über den Rig-Namen zu; im Rechner lässt sich die Auswahl ändern.
- TE senkt nur die Bauzeit, nicht die Jobkosten.
- Ohne Corptools und aa-structures funktioniert der Rechner wie bisher mit frei eingegebenen Boni.

## Einstellungen

| Einstellung | Standard | Zweck |
|---|---|---|
| `ETHER_INDUSTRY_USER_AGENT` | Platzhalter | User-Agent für ESI und SDE-Download |
| `ETHER_INDUSTRY_SDE_URL` | neueste CCP-SDE (JSONL) | Quelle für den Import |
| `ETHER_INDUSTRY_ESI_BASE_URL` | `https://esi.evetech.net/latest` | ESI-Adresse |
| `ETHER_INDUSTRY_PRICE_REGION_ID` | `10000002` (The Forge) | Region für Marktpreise |
| `ETHER_INDUSTRY_PRICE_STATION_ID` | `60003760` (Jita 4-4) | Station für Marktpreise |
| `ETHER_INDUSTRY_STRUCTURE_CORP_IDS` | alle Corps (Corptools-Corp-Audit bzw. aa-structures-Owner) | Nur Strukturen/Blueprints dieser Corp-IDs verwenden, z. B. `[98000001]` |

## Lizenz

GPL-3.0
