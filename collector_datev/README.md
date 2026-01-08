# Steuerberater.tel - Data Collector

Ein Tool-Set zum Sammeln von Steuerberater-Daten aus verschiedenen Quellen (DATEV, BStBK) mit Web-Frontend zur Verwaltung.

## Schnellstart

```bash
# 1. In das Projektverzeichnis wechseln
cd collector_datev

# 2. Dependencies installieren (mit uv)
uv sync

# 3. Playwright Browser installieren
uv run playwright install chromium

# 4. Web-Frontend starten
uv run flask run
```

**Web-Frontend URL:** http://127.0.0.1:5444

---

## Inhaltsverzeichnis

1. [Voraussetzungen](#voraussetzungen)
2. [Setup](#setup)
3. [Web-Frontend (Flask)](#web-frontend-flask)
4. [CLI-Tools](#cli-tools)
5. [Datenbank](#datenbank)
6. [Konfiguration](#konfiguration)
7. [Troubleshooting](#troubleshooting)

---

## Voraussetzungen

- **Python 3.10+**
- **uv** (Package Manager) - [Installation](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Sheets API** (nur fuer DATEV-Scraper)

---

## Setup

### 1. Dependencies installieren

```bash
cd collector_datev

# Mit uv (empfohlen)
uv sync

# Oder mit pip
pip install -r requirements.txt
```

### 2. Playwright Browser installieren

```bash
uv run playwright install chromium
```

### 3. Google API einrichten (nur fuer DATEV-Scraper)

1. **Google Cloud Console** oeffnen: https://console.cloud.google.com/
2. Neues Projekt erstellen oder bestehendes auswaehlen
3. **APIs & Services** → **Library** → **Google Sheets API** aktivieren
4. **APIs & Services** → **Credentials** → **Create Credentials** → **Service Account**
5. Service Account erstellen und JSON-Datei herunterladen
6. Datei als `data/credentials.json` speichern
7. Im Google Sheets Dokument die Service-Account E-Mail als Editor freigeben

---

## Web-Frontend (Flask)

Das Web-Frontend bietet eine UI zum Starten und Verwalten von Collector-Jobs.

### Starten

```bash
cd collector_datev

# Empfohlen: Mit Flask CLI (nutzt .flaskenv Konfiguration)
uv run flask run

# Alternativ: Direkt mit Python
uv run python run.py
```

### URLs

| URL | Beschreibung |
|-----|--------------|
| http://127.0.0.1:5444 | Startseite (redirect zu /jobs/) |
| http://127.0.0.1:5444/jobs/ | **Job-Runner** - Jobs starten/ueberwachen |
| http://127.0.0.1:5444/jobs/3 | Job-Details (Beispiel: Job #3) |
| http://127.0.0.1:5444/blacklist/ | **Blacklist-Editor** - Domain-Blacklist verwalten |
| http://127.0.0.1:5444/kanzleien/ | Kanzleien-Liste (BStBK-Daten) |
| http://127.0.0.1:5444/settings/ | Einstellungen |

### Port aendern

Der Port ist in `.flaskenv` konfiguriert:

```ini
# .flaskenv
FLASK_APP=run.py
FLASK_DEBUG=1
FLASK_RUN_PORT=5444
FLASK_RUN_HOST=127.0.0.1
```

---

## CLI-Tools

### 1. BStBK Collector (Bundessteuerberaterkammer)

Scrapt das offizielle Steuerberaterverzeichnis der Bundessteuerberaterkammer und speichert in SQLite.

**Quelle:** https://steuerberaterverzeichnis.berufs-org.de/

```bash
cd collector_datev

# Alle PLZ scrapen (dauert sehr lange!)
uv run python main_bstbk.py

# Nur PLZ beginnend mit "4" (NRW-Bereich)
uv run python main_bstbk.py --plz-filter 4

# Headless-Modus (ohne Browser-Fenster)
uv run python main_bstbk.py --plz-filter 47 --headless

# Dry-Run (keine Speicherung)
uv run python main_bstbk.py --plz-filter 47 --dry-run

# Maximale Anzahl PLZ begrenzen
uv run python main_bstbk.py --plz-filter 4 --max-plz 10

# Force Re-Scrape (bereits verarbeitete PLZ erneut scrapen)
uv run python main_bstbk.py --plz-filter 47 --force
```

**Optionen:**

| Option | Beschreibung |
|--------|--------------|
| `--plz-filter TEXT` | Nur PLZ mit diesem Prefix (z.B. "4", "47", "475") |
| `--headless` | Browser ohne GUI |
| `--dry-run` | Keine Speicherung in DB |
| `--max-plz INT` | Maximal X PLZ verarbeiten |
| `--force` | Bereits gescrapte PLZ erneut verarbeiten |
| `--update-mode` | `add_only` (default), `update_all`, `smart` |
| `--verbose` | Debug-Logging |

### 2. DATEV Scraper (Google Sheets Export)

Scrapt den DATEV Steuerberater-Suchdienst und exportiert nach Google Sheets.

**Quelle:** https://www.datev.de/kasus/First/Start?KammerId=BuKa&Suffix1=BuKaY&Suffix2=BuKaXY&Truncation=42

```bash
cd collector_datev

# Standard-Aufruf (nutzt Defaults)
uv run python main.py

# Mit allen Parametern
uv run python main.py \
    --plz-file data/postleitzahlen.csv \
    --sheet-url "https://docs.google.com/spreadsheets/d/1g4PlGQ0Wxdb4HLBdR_6pCzLzg08kB0GteiDoW7oCmyM/edit" \
    --credentials data/credentials.json

# Nur bestimmte PLZ
uv run python main.py --plz-filter 47

# Dry-Run
uv run python main.py --dry-run
```

**Optionen:**

| Option | Beschreibung |
|--------|--------------|
| `--plz-file PATH` | Input-Datei mit PLZ (Default: `data/postleitzahlen.csv`) |
| `--sheet-url URL` | Google Sheets URL |
| `--credentials PATH` | Google API Credentials (Default: `data/credentials.json`) |
| `--plz-filter TEXT` | Nur PLZ mit diesem Prefix |
| `--dry-run` | Keine Speicherung |
| `--headless` | Browser ohne GUI |

---

## Datenbank

### SQLite-Datenbank

Die Datenbank liegt unter `data/collector.db`.

```bash
# Datenbank oeffnen
sqlite3 data/collector.db

# Tabellen anzeigen
.tables

# Schema einer Tabelle
.schema kanzlei

# Beispiel-Abfragen
SELECT COUNT(*) FROM kanzlei;
SELECT COUNT(*) FROM steuerberater;
SELECT * FROM jobs ORDER BY created_at DESC LIMIT 5;
```

### Wichtige Tabellen

| Tabelle | Beschreibung |
|---------|--------------|
| `kanzlei` | Kanzlei-Stammdaten (Name, Adresse, Kontakt) |
| `steuerberater` | Einzelne Steuerberater mit Kanzlei-Zuordnung |
| `kammer` | Steuerberaterkammern |
| `rechtsform` | Rechtsformen (GmbH, PartG, etc.) |
| `plz` | Deutsche Postleitzahlen |
| `plz_collector` | Fortschritt pro PLZ und Collector |
| `jobs` | Job-Historie |
| `log_entries` | Job-Logs |
| `domains` | Domain-Blacklist |

### Datenbank zuruecksetzen

```bash
# Ueber Web-UI
# http://127.0.0.1:5444/settings/ -> "Daten zuruecksetzen"

# Oder manuell
rm data/collector.db
uv run flask db-init
```

---

## Konfiguration

### Umgebungsvariablen (.env)

```bash
# .env (im collector_datev Verzeichnis)
BRAVE_API_KEY="dein-api-key"    # Fuer Web-Suche (optional)
```

### Flask-Konfiguration (.flaskenv)

```ini
# .flaskenv
FLASK_APP=run.py
FLASK_DEBUG=1
FLASK_RUN_PORT=5444
FLASK_RUN_HOST=127.0.0.1
```

### DATEV-Scraper Umgebungsvariablen

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `PLZ_INPUT` | `data/postleitzahlen.csv` | Input-Datei |
| `SHEET_URL` | - | Google Sheets URL |
| `GOOGLE_CREDENTIALS` | `data/credentials.json` | API Credentials |
| `HEADLESS` | `false` | Headless-Modus |
| `TIMEOUT_MS` | `30000` | Playwright Timeout |
| `RATE_LIMIT_SEC` | `2.5` | Pause zwischen Anfragen |
| `MAX_RETRIES` | `3` | Wiederholungen bei Fehler |
| `LOG_LEVEL` | `INFO` | Log-Level |
| `MAX_PLZ` | - | Max. Anzahl PLZ |

---

## Troubleshooting

### Browser/Playwright Probleme

```bash
# Playwright neu installieren
uv run playwright install chromium --force

# Browser-Cache loeschen
rm -rf ~/Library/Caches/ms-playwright/
uv run playwright install chromium
```

### Job haengt / laesst sich nicht abbrechen

Wenn ein Job nach Server-Neustart haengt:

```bash
# Haengende Prozesse finden
ps aux | grep main_bstbk

# Prozess killen
pkill -f main_bstbk.py

# Job-Status in DB korrigieren
sqlite3 data/collector.db "UPDATE jobs SET status='cancelled' WHERE status='running';"
```

### Port bereits belegt

```bash
# Prozess auf Port finden
lsof -i :5444

# Flask-Prozesse beenden
pkill -f "flask run"
```

### Google Sheets Authentifizierung

1. Pruefe ob `data/credentials.json` existiert
2. Pruefe ob die Service-Account E-Mail Zugriff auf das Sheet hat
3. Pruefe ob die Google Sheets API aktiviert ist

---

## Projektstruktur

```
collector_datev/
├── app/                    # Flask Application
│   ├── __init__.py        # App Factory
│   ├── models/            # SQLAlchemy Models
│   ├── routes/            # Blueprints (jobs, blacklist, api, ...)
│   ├── services/          # Business Logic
│   └── templates/         # Jinja2 Templates
├── data/
│   ├── collector.db       # SQLite Datenbank
│   ├── credentials.json   # Google API (nicht committet)
│   ├── domain_blacklist.txt
│   └── plz_de.xlsx        # Deutsche PLZ
├── docs/
│   └── prd/              # Product Requirements Documents
├── src/
│   ├── scraper.py        # DATEV Scraper
│   ├── collector_bstbk.py # BStBK Collector
│   ├── parser_bstbk.py   # BStBK Parser
│   └── ...
├── main.py               # DATEV CLI Entry Point
├── main_bstbk.py         # BStBK CLI Entry Point
├── run.py                # Flask Entry Point
├── .env                  # Secrets (nicht committet)
├── .flaskenv             # Flask Konfiguration
└── requirements.txt
```

---

## Hinweise

- **Rate Limiting:** Die Scraper halten respektvolle Pausen zwischen Anfragen ein
- **Checkpoint-System:** Bei Abbruch wird der Fortschritt gespeichert, Restart setzt fort
- **Nur oeffentliche Daten:** Es werden nur oeffentlich zugaengliche Daten gesammelt
