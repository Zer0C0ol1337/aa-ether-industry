# Changelog

## [0.2.1] - 2026-10-29

### Hinzugefügt
- **aa-structures als zweite Quelle:** ist die App Structures installiert, werden Industrie-Strukturen und ihre Rigs (Fitting, Rig-Slots) auch von dort gelesen. Corptools hat Vorrang; fehlen dort die Rigs (keine Corp-Assets ohne Director-Token), kommen sie aus aa-structures. Strukturen, die nur aa-structures kennt, werden ergänzt.
- Struktur-Übersicht zeigt, woher die Rigs stammen, und einen Hinweis, wenn keine gefunden wurden
- Migration `0003_rig_source`

### Geändert
- Button „Aus Corptools neu einlesen“ heißt jetzt „Strukturen neu einlesen“

## [0.2.0] - 2026-10-29

### Hinzugefügt
- **Strukturen aus Corptools:** Raitaru, Azbel, Sotiyo, Athanor und Tatara der Corp werden mit System, Sicherheitsstatus und eingebauten Rigs eingelesen (Corp-Assets im Rig-Slot) – Übersicht auf der Startseite, Button „Aus Corptools neu einlesen“ für Verwalter
- **Struktur im Rechner auswählen:** Rollenbonus (Material, Zeit, Jobkosten) und die passenden Rigs werden automatisch eingerechnet, Rig-Boni mit dem Sicherheits-Multiplikator des Systems (Highsec, Lowsec, Nullsec, Wurmloch); die Rig-Auswahl ist überschreibbar
- Rig-Boni und Sicherheits-Multiplikatoren aus der Dogma der Rigs – lokal aus django-eveonline-sde (kommt mit Corptools), sonst aus der ESI; bis sie geladen sind, Standardwerte mit Hinweis
- **TE und Bauzeit:** TE des Blueprints, Struktur- und Rig-Zeitbonus, Skills (Industry, Advanced Industry, Reactions) und Implantat (BX-801/802/804) ergeben die echte Bauzeit, dazu gesparte Zeit und **Gewinn pro Stunde**
- Skills werden aus Corptools vorbelegt (bester eigener Charakter); Struktur, Skills, Implantat und Steuer werden pro User gemerkt
- **Kostenindex automatisch** aus der ESI für das System der gewählten Struktur (überschreibbar)
- **Eigene Corp-Blueprints:** ME/TE der BPOs/BPCs aus Corptools mit einem Klick übernehmen
- Erste Tests (Boni-Formeln, Rechnung, Corptools-Abgleich, Rechner-Seite)
- Migration `0002_structures_rigs`

### Geändert
- Jobkosten: der Struktur-Rollenbonus (Raitaru −3 %, Azbel −4 %, Sotiyo −5 %) senkt den Kostenindex-Anteil; TE ändert nur die Zeit, nicht die Jobkosten
- Der Preisabgleich (alle 6 Stunden) gleicht danach auch Strukturen, Rigs und Kostenindizes ab – kein neuer Beat-Eintrag nötig

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
