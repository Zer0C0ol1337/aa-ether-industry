# Changelog

## [0.1.3] - 2026-10-05

### Hinzugefügt
- Autovervollständigung im Suchfeld (ab 2 Zeichen, mit Icon, Pfeiltasten und Enter)
- Route `autocomplete/` liefert Vorschläge als JSON

### Geändert
- Suche sortiert Treffer, die mit der Eingabe beginnen, nach oben

## [0.1.2] - 2026-10-05

### Behoben
- Migration `0001_initial` fehlte im Repo bzw. Paket, dadurch wurden keine Tabellen angelegt

## [0.1.1] - 2026-10-05

### Hinzugefügt
- Migration `0001_initial` wird mitgeliefert (nötig für Docker, dort darf nicht im Container migriert werden)
- Installationsanleitung für Alliance Auth unter Docker

## [0.1.0] - 2026-10-05

### Hinzugefügt
- Plugin-Grundgerüst für Alliance Auth (hatchling, GPL-3.0)
- Rechte `basic_access` und `manage_industry`
- SDE-Import (CCP JSON Lines): Items, Blueprints, Tätigkeiten, Materialien, Produkte
- Preisabgleich per Celery: CCP Adjusted/Average sowie Jita Sell/Buy
- Industrie-Rechner für Herstellung und Reactions (ME, Struktur-Bonus, Kostenindex, Steuer, SCC-Zuschlag)
- Produktsuche (englische und deutsche Namen)
