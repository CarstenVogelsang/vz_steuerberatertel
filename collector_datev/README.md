# Steuerberater.tel - Scraper

Ein Playwright-basierter Scraper, der den bundesweiten Steuerberater-Suchdienst nach Postleitzahlen durchsucht und die Ergebnisse in Google Sheets schreibt.

## Voraussetzungen

- Python 3.10+
- Google Sheets Dokument (vorhanden)

## Setup

### 1) Abhaengigkeiten installieren

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 2) Google API einrichten (Service Account)

1. Google Cloud Console oeffnen: https://console.cloud.google.com/
2. Neues Projekt erstellen oder ein bestehendes auswaehlen.
3. APIs & Services -> Library -> **Google Sheets API** aktivieren.
4. APIs & Services -> Credentials -> **Create Credentials** -> **Service Account**.
5. Service Account erstellen und eine JSON-Datei herunterladen.
6. Datei als `data/credentials.json` speichern.
7. In Google Sheets das Ziel-Dokument fuer die Service-Account E-Mail freigeben.

### 3) Input-Datei

Die PLZ-Datei ist `data/postleitzahlen.csv` und enthaelt eine PLZ pro Zeile:

```csv
47574
45127
10115
80331
```

## Nutzung

```bash
python main.py
```

Optional:

```bash
python main.py --plz-file data/postleitzahlen.csv --sheet-url "https://docs.google.com/spreadsheets/d/1g4PlGQ0Wxdb4HLBdR_6pCzLzg08kB0GteiDoW7oCmyM/edit?gid=1770182680#gid=1770182680" --credentials data/credentials.json
python main.py --dry-run
```

## Konfiguration per ENV

- `PLZ_INPUT` (Default: `data/postleitzahlen.csv`)
- `SHEET_URL`
- `GOOGLE_CREDENTIALS` (Default: `data/credentials.json`)
- `HEADLESS` (Default: `false`)
- `TIMEOUT_MS` (Default: `30000`)
- `RATE_LIMIT_SEC` (Default: `2.5`)
- `MAX_RETRIES` (Default: `3`)
- `LOG_LEVEL` (Default: `INFO`)
- `MAX_PLZ` (optional)

## Tests

```bash
pytest
```

## Hinweise

- Das Ergebnislayout der Zielseite kann sich aendern. Falls keine Ergebnisse erkannt werden, pruefe die Selektoren in `src/scraper.py`.
- Durch Rate Limiting wird die Seite geschont.
