# PRD-006: Bundessteuerberaterkammer Scraper

## Status: APPROVED

---

## 1. Übersicht

### Hintergrund
Die DATEV-Website (`datev.de/kasus`) ist aktuell nicht erreichbar. Als Alternative soll ein neuer Scraper für das **amtliche Steuerberaterverzeichnis der Bundessteuerberaterkammer** implementiert werden.

**Ziel-URL:** https://steuerberaterverzeichnis.berufs-org.de/

### Unterschiede zum DATEV-Scraper

| Aspekt | DATEV-Scraper | BStBK-Scraper |
|--------|---------------|---------------|
| Output | Google Sheets | SQLite (collector.db) |
| Datenmodell | Flach (1 Zeile = 1 Eintrag) | Relational (Kanzlei → Steuerberater) |
| Ergebnisse | Direkt auf Suchergebnis-Seite | Trefferliste → Detailseiten |
| Duplikate | PLZ\|Name | Safe ID (eindeutig) |
| PLZ-Tracking | plz-Tabelle (processed_at) | plz_scraper-Tabelle (generisch) |

---

## 2. Website-Analyse

### 2.1 Suchformular
- **URL:** https://steuerberaterverzeichnis.berufs-org.de/
- **PLZ-Feld:** `id="plz-text"`
- **Submit:** `input[type="submit"]`

### 2.2 Suchergebnisse
- Trefferliste mit Links zu Detailseiten
- Beispiel: PLZ 47574 → 52 Ergebnisse
- Jeder Treffer verlinkt auf eine Detailseite

### 2.3 Detailseite - Verfügbare Felder

**Beispiel 1: Einzelperson = Kanzlei** (Wolfgang Auclair)
```
Name:         Wolfgang Auclair
Straße:       Emmericher Weg 72
PLZ/Ort:      47574 Goch
Telefon:      02823 93110
E-Mail:       kanzlei@stb-auclair.de
Safe ID:      DE.BStBK.05e9b4ec-ed9d-4d60-8289-a08646d1e54c.6f70
Bestelldatum: 22.02.2000
Kammer:       Steuerberaterkammer Düsseldorf
```

**Beispiel 2: Steuerberater in Kanzlei** (Hubert Aymans)
```
Name:         Hubert Aymans
Kanzlei:      Thielen Steuerberater Partnerschaftsgesellschaft mbB
Straße:       Bahnhofstr. 1
PLZ/Ort:      47574 Goch
E-Mail:       hubert.aymans@thielen-stb.de
Safe ID:      DE.BStBK.37fec9ed-3c2f-4cb3-8e6a-99b1173cff88.51b6
Bestelldatum: 22.04.2008
Kammer:       Steuerberaterkammer Düsseldorf
```

---

## 3. Finales Datenmodell

### 3.1 Tabelle: `kanzlei` (Steuerberaterkanzlei)

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| id | INTEGER PK | Auto-Increment |
| name | VARCHAR(255) NOT NULL | Kanzleiname / Firmenname |
| rechtsform_id | INTEGER FK | → rechtsform.id (GbR, PartG mbB, etc.) |
| strasse | VARCHAR(255) | Straße + Hausnummer |
| plz | VARCHAR(5) | Postleitzahl |
| ort | VARCHAR(100) | Stadt |
| telefon | VARCHAR(50) | Telefonnummer (Kanzlei) |
| fax | VARCHAR(50) | Faxnummer |
| email | VARCHAR(255) | Kanzlei-E-Mail (erkannt via Keywords) |
| website | VARCHAR(255) | Website-URL |
| kammer_id | INTEGER FK | → steuerberaterkammer.id |
| created_at | DATETIME | Erstellungsdatum |
| updated_at | DATETIME | Letzte Änderung |

**Unique Constraint:** `(name, plz)` - Kanzlei eindeutig pro Name+PLZ

### 3.1b Tabelle: `rechtsform`

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| id | INTEGER PK | Auto-Increment |
| kuerzel | VARCHAR(50) UNIQUE | z.B. "GbR", "PartG mbB", "GmbH" |
| bezeichnung | VARCHAR(255) | Voller Name der Rechtsform |

**Seed-Daten:**
- GbR (Gesellschaft bürgerlichen Rechts)
- PartG (Partnerschaftsgesellschaft)
- PartG mbB (Partnerschaftsgesellschaft mit beschränkter Berufshaftung)
- GmbH (Gesellschaft mit beschränkter Haftung)
- Einzelunternehmen

### 3.2 Tabelle: `steuerberater`

**Hinweis zur Safe ID:** Die Safe ID ist die eindeutige Identifikation des **Steuerberaters als natürliche Person** im beSt (besonderes elektronisches Steuerberaterpostfach) der Bundessteuerberaterkammer. Bei der Registrierung werden zwei Safe IDs erzeugt: eine für die Person, eine für die Kanzlei. Im Steuerberaterverzeichnis wird die **persönliche Safe ID** angezeigt.

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| id | INTEGER PK | Auto-Increment |
| safe_id | VARCHAR(100) UNIQUE | DE.BStBK.[UUID].[suffix] |
| titel | VARCHAR(50) | "Steuerberater" / "Steuerberaterin" |
| vorname | VARCHAR(100) | Vorname |
| nachname | VARCHAR(100) | Nachname |
| email | VARCHAR(255) | Persönliche E-Mail (wenn nicht Kanzlei-Keyword) |
| mobil | VARCHAR(50) | Mobilnummer |
| bestelldatum | DATE | Datum der Bestellung zum Steuerberater |
| kanzlei_id | INTEGER FK NOT NULL | → kanzlei.id |
| created_at | DATETIME | Erstellungsdatum |

### 3.3 Tabelle: `steuerberaterkammer`

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| id | INTEGER PK | Auto-Increment |
| name | VARCHAR(255) UNIQUE | z.B. "Steuerberaterkammer Düsseldorf" |
| strasse | VARCHAR(255) | Adresse |
| plz | VARCHAR(5) | PLZ |
| ort | VARCHAR(100) | Stadt |

### 3.4 Tabelle: `plz_scraper` (NEU - Generisches Tracking)

| Spalte | Typ | Beschreibung |
|--------|-----|--------------|
| id | INTEGER PK | Auto-Increment |
| plz | VARCHAR(5) NOT NULL | Postleitzahl |
| scraper_type | VARCHAR(20) NOT NULL | 'datev' oder 'bstbk' |
| processed_at | DATETIME | Verarbeitungszeitpunkt |
| result_count | INTEGER | Anzahl gefundener Einträge |
| error_message | TEXT | Fehlermeldung |
| created_at | DATETIME | Erstellungsdatum |

**Unique Constraint:** `(plz, scraper_type)` - Pro PLZ und Scraper nur ein Eintrag

---

## 3.5 Exkurs: Was ist die Safe ID?

Die **Safe ID** ist ein zentrales Element der Steuerberaterplattform der BStBK:

### Definition

- Eindeutige Identifikation im **beSt** (besonderes elektronisches Steuerberaterpostfach)
- Format: `DE.BStBK.[UUID].[suffix]`
- Dient der digitalen Berufsträger-Identität
- Ermöglicht Ende-zu-Ende-verschlüsselte Kommunikation

### Wichtig: Zwei Safe IDs werden erzeugt

Bei der Registrierung im beSt werden **zwei Safe IDs** erzeugt:
1. **Safe ID für die natürliche Person** (Steuerberater selbst)
2. **Safe ID für die Organisation/Kanzlei**

### Quellen

- [BStBK Steuerberaterplattform](https://www.bstbk.de/de/themen/steuerberaterplattform)
- [DATEV Community](https://www.datev-community.de/t5/Office-Management/BeSt-mit-mehreren-Beraternummern/td-p/331300)

---

## 3.6 HTML-Struktur und Parser-Logik

### Unterscheidung: Einzelperson vs. Gesellschaft

**Fall 1: Einzelner Steuerberater**

```html
<p id="beruf" class="beruf">Steuerberater</p>
<!-- Safe ID gehört zur Person -->
```

- `id="beruf"` vorhanden = Einzelperson
- Safe ID wird dem Steuerberater zugeordnet
- Kanzlei wird mit dem Namen des Steuerberaters erstellt

**Fall 2: Kanzlei/Gesellschaft**

```html
<p id="firmenname" class="name">
  Bellen sen., Johannes<br>
  Bellen jun., Johannes<br>
  Bellen, Lydia, Dipl.-Kauffrau
</p>
<p id="rechtsform">
  <span>Rechtsform:</span>
  <span class="text-wrap">GbR</span>
</p>
<!-- Keine Safe ID auf Gesellschafts-Ebene -->
```

- `id="beruf"` fehlt + `id="firmenname"` + `id="rechtsform"` = Gesellschaft
- Kanzlei wird erstellt mit Firmenname + Rechtsform
- Steuerberater werden aus dem Firmenname extrahiert (Namen durch `<br>` getrennt)

### Parser-Algorithmus

```python
def parse_detail_page(html):
    if has_element(html, "#beruf"):
        # Fall 1: Einzelperson
        steuerberater = extract_person_data(html)
        steuerberater.safe_id = extract_safe_id(html)
        kanzlei = create_kanzlei_from_person(steuerberater)
    else:
        # Fall 2: Gesellschaft
        kanzlei = extract_kanzlei_data(html)
        kanzlei.rechtsform = extract_rechtsform(html)
        namen = extract_namen_from_firmenname(html)
        steuerberater_list = [create_steuerberater(name, kanzlei) for name in namen]
```

---

## 4. Entscheidungen

### E-Mail-Zuordnung: Intelligente Keyword-Erkennung
**Logik:**
```python
KANZLEI_KEYWORDS = ['kanzlei', 'info', 'kontakt', 'office', 'mail', 'post']

def is_kanzlei_email(email: str) -> bool:
    local_part = email.split('@')[0].lower()
    return any(kw in local_part for kw in KANZLEI_KEYWORDS)
```

- `kanzlei@stb-auclair.de` → Kanzlei-E-Mail
- `info@thielen-stb.de` → Kanzlei-E-Mail
- `hubert.aymans@thielen-stb.de` → Steuerberater-E-Mail

### Einzelperson = Kanzlei: Immer Kanzlei erstellen
- Wolfgang Auclair → Kanzlei "Wolfgang Auclair" wird erstellt
- Steuerberater wird der Kanzlei zugeordnet
- Konsistentes Datenmodell

### Steuerberaterkammer: Eigene Tabelle
- Normalisiert, verhindert Redundanz
- Ermöglicht spätere Erweiterungen (Website, Kontaktdaten)

### PLZ-Tracking: Neue generische Tabelle `plz_scraper`
- Eine Tabelle für alle Scraper
- Spalte `scraper_type` ('datev', 'bstbk')
- Ermöglicht unabhängiges Tracking pro Scraper

### Telefon/Fax: Der Kanzlei zuordnen
- Telefon wird der Kanzlei zugeordnet (nicht dem Steuerberater)
- Mobilnummer (falls vorhanden) dem Steuerberater

---

## 5. Implementierungsplan

### 5.1 Neue Dateien

```
collector_datev/
├── src/
│   ├── scraper.py              # DATEV Scraper (bestehend, unverändert)
│   ├── scraper_bstbk.py        # NEU: BStBK Scraper Klasse
│   ├── parser_bstbk.py         # NEU: Parser für Detailseiten
│   └── email_classifier.py     # NEU: E-Mail Keyword-Erkennung
├── app/
│   ├── models/
│   │   ├── __init__.py         # ÄNDERN: Neue Models exportieren
│   │   ├── kanzlei.py          # NEU: Kanzlei Model
│   │   ├── steuerberater.py    # NEU: Steuerberater Model
│   │   ├── kammer.py           # NEU: Steuerberaterkammer Model
│   │   └── plz_scraper.py      # NEU: Generisches PLZ-Tracking
│   └── commands.py             # ÄNDERN: Neue CLI-Commands
├── main_bstbk.py               # NEU: Entry-Point für BStBK Scraper
└── docs/prd/
    └── 006-bstbk-scraper.md    # PRD-Dokument
```

### 5.2 Implementierungsreihenfolge

**Phase 1: Datenmodell (Models)**
1. `app/models/kammer.py` - Steuerberaterkammer Model
2. `app/models/rechtsform.py` - Rechtsform Model (NEU)
3. `app/models/kanzlei.py` - Kanzlei Model (FK → Kammer, FK → Rechtsform)
4. `app/models/steuerberater.py` - Steuerberater Model (FK → Kanzlei)
5. `app/models/plz_scraper.py` - Generisches PLZ-Tracking
6. `app/models/__init__.py` - Exports aktualisieren
7. `app/commands.py` - CLI: `flask seed-rechtsformen` (Seed-Daten)
8. `flask init-db` + `flask seed-rechtsformen` ausführen

**Phase 2: Parser & Utilities**
1. `src/email_classifier.py` - Keyword-basierte E-Mail-Erkennung
2. `src/parser_bstbk.py` - HTML-Parser für Detailseiten
   - `parse_detail_page(html: str) -> ParsedBStBKEntry`
   - Extraktion: Name, Kanzlei, Safe ID, Bestelldatum, etc.

**Phase 3: Scraper**
1. `src/scraper_bstbk.py` - BStBK Scraper Klasse
   - `scrape_plz(page, plz: str) -> list[ParsedBStBKEntry]`
   - Workflow: Formular → Trefferliste → Detailseiten
2. `main_bstbk.py` - CLI Entry-Point
   - Argumente: `--plz-filter`, `--headless`, `--dry-run`, `--max-plz`

**Phase 4: Integration**
1. `app/commands.py` - CLI-Commands hinzufügen
   - `flask init-plz-scraper` - PLZ-Tracking initialisieren
   - `flask stats-bstbk` - Statistiken anzeigen
2. `app/services/job_service.py` - Job-Typ `scraper_bstbk` hinzufügen

### 5.3 Scraper-Workflow (Detailliert)

```
1. PLZ laden aus plz_scraper (WHERE scraper_type='bstbk' AND processed_at IS NULL)
   - Falls leer: PLZ aus plz-Tabelle importieren

2. Für jede PLZ:
   a. Navigate zu https://steuerberaterverzeichnis.berufs-org.de/
   b. Fill input#plz-text mit PLZ
   c. Click submit button
   d. Wait for Ergebnisliste

3. Trefferliste parsen:
   a. Alle Links zu Detailseiten extrahieren
   b. Für jeden Link:
      i.   Navigate zu Detailseite
      ii.  HTML parsen → ParsedBStBKEntry
      iii. Steuerberaterkammer finden/erstellen
      iv.  Kanzlei finden/erstellen (Deduplikation: name+plz)
      v.   E-Mail klassifizieren (Kanzlei oder Steuerberater)
      vi.  Steuerberater erstellen (Safe ID als Unique Key)
      vii. Rate Limit (1-2 Sekunden)

4. PLZ als verarbeitet markieren (plz_scraper.processed_at)

5. Logging: Anzahl gefundener Steuerberater/Kanzleien
```

### 5.4 Job-Integration

Neuer Job-Typ: `scraper_bstbk`
```python
# job_service.py
elif job_type == "scraper_bstbk":
    cmd = ["uv", "run", "python", "main_bstbk.py"]
    if parameters.get("plz_filter"):
        cmd.extend(["--plz-filter", str(parameters["plz_filter"])])
    if parameters.get("headless"):
        cmd.append("--headless")
```

---

## 6. Nächste Schritte

1. PRD genehmigt
2. Implementierung starten
   - Phase 1: Models erstellen
   - Phase 2: Parser entwickeln
   - Phase 3: Scraper implementieren
   - Phase 4: Integration + Test

---

## Anhang: Bestehende Code-Architektur

### DATEV-Scraper Datenfluss (aktuell)
```
main.py
  → load_pending_locations() [plz_handler.py]
  → SteuerberaterScraper.scrape_plz_with_status() [scraper.py]
  → parse_entry() [parser.py]
  → Google Sheets [sheets_handler.py]
  → update_plz_status() [plz_handler.py]
```

### Bestehende Models
- `Plz` - PLZ-Tracking (processed_at, result_count, error_message)
- `Domain` - Blacklist-Domains
- `Job` - Job-Execution
- `LogEntry` - Job-Logs
- `Category` - Domain-Kategorien

