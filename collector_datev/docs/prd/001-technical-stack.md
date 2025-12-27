# PRD-001: Technical Stack & Architektur

## Status

Draft | Version 1.0 | 2025-12-26

## Übersicht

Technische Grundlagen für die Flask + SQLite Erweiterung des collector_datev Projekts.

---

## 1. Tech Stack

### Backend

| Komponente | Technologie | Version | Begründung |
|------------|-------------|---------|------------|
| Web Framework | Flask | 3.0+ | Leichtgewichtig, pythonisch |
| Template Engine | Jinja2 | (inkl.) | Standard für Flask |
| Database | SQLite | 3.x | Keine Server-Installation nötig |
| ORM | SQLAlchemy | 2.0+ | Type-safe, Flask-SQLAlchemy Integration |
| Migrations | Alembic | 1.13+ | Schema-Versionierung |
| Task Queue | - | - | Nicht nötig (subprocess für Jobs) |

### Frontend

| Komponente | Technologie | Begründung |
|------------|-------------|------------|
| CSS Framework | Tailwind CSS 3.x | Utility-first, maximale Flexibilität |
| UI Components | daisyUI 4.x | Vorgefertigte Komponenten für Tailwind |
| Tabellen | Simple-DataTables | Sortierung, Suche, Pagination (Vanilla JS) |
| Interaktivität | HTMX | Partial Page Updates ohne JS-Framework |
| Realtime Output | Server-Sent Events (SSE) | Einfacher als WebSocket für Log-Streaming |
| Icons | Tabler Icons | 5.200+ Icons, konsistenter Stil |

### Bestehende Abhängigkeiten (bleiben erhalten)

- playwright, gspread, google-auth
- python-dotenv, requests
- duckduckgo-search, google-search-results

---

## 2. Architektur

### Komponenten-Diagramm

```text
┌─────────────────────────────────────────────────────────┐
│                    Flask Web App                        │
├─────────────────────────────────────────────────────────┤
│  Routes (Blueprints)                                    │
│  ├── /dashboard     - Statistiken, Status              │
│  ├── /blacklist     - CRUD für Domain-Blacklist        │
│  ├── /jobs          - Job-Management + Realtime Logs   │
│  └── /api           - REST Endpoints für HTMX          │
├─────────────────────────────────────────────────────────┤
│  Services                                               │
│  ├── JobService     - Subprocess-Management            │
│  ├── BlacklistService - Blacklist CRUD                 │
│  └── SheetsService  - Google Sheets Sync               │
├─────────────────────────────────────────────────────────┤
│  Models (SQLAlchemy)                                    │
│  ├── Domain         - Blacklist-Einträge               │
│  ├── Job            - Job-Ausführungen                 │
│  └── LogEntry       - Job-Logs                         │
└─────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
    ┌──────────┐                ┌─────────────────┐
    │  SQLite  │                │  Google Sheets  │
    │  (lokal) │                │    (Master)     │
    └──────────┘                └─────────────────┘
```

### Datenfluss

1. **Steuerberater-Daten**: Nur in Google Sheets (kein lokaler Cache)
2. **Blacklist**: SQLite (lokal bearbeitbar), Export nach `domain_blacklist.txt`
3. **Job-Status/Logs**: SQLite (für Dashboard-Anzeige)
4. **Konfiguration**: Weiterhin `.env` + `config.py`

---

## 3. Projektstruktur (erweitert)

```text
collector_datev/
├── app/                      # NEU: Flask Application
│   ├── __init__.py           # App Factory
│   ├── models/
│   │   ├── __init__.py
│   │   ├── domain.py         # Blacklist Model
│   │   ├── job.py            # Job Model
│   │   └── log_entry.py      # Log Model
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── dashboard.py      # Dashboard Blueprint
│   │   ├── blacklist.py      # Blacklist Blueprint
│   │   ├── jobs.py           # Jobs Blueprint
│   │   └── api.py            # API Blueprint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── job_service.py    # Job-Ausführung
│   │   ├── blacklist_service.py
│   │   └── sheets_service.py # Google Sheets Integration
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard/
│   │   ├── blacklist/
│   │   └── jobs/
│   └── static/
│       └── css/
├── src/                      # BESTEHEND: CLI-Tools (unverändert)
│   ├── scraper.py
│   ├── enrich_from_email.py
│   ├── enrich_from_search.py
│   └── ...
├── data/
│   ├── collector.db          # NEU: SQLite Datenbank
│   ├── domain_blacklist.txt  # BESTEHEND: wird aus DB exportiert
│   └── ...
├── docs/
│   └── prd/                  # NEU: PRD-Dokumente
├── migrations/               # NEU: Alembic Migrations
├── run.py                    # NEU: Flask Runner
└── requirements.txt          # ERWEITERT
```

---

## 4. Neue Dependencies

```text
# Web Framework
flask>=3.0.0
flask-sqlalchemy>=3.1.0

# Migrations (optional, aber empfohlen)
alembic>=1.13.0

# Frontend (via CDN oder npm)
# - Tailwind CSS 3.x (CDN für Entwicklung, Build für Production)
# - daisyUI 4.x (CDN)
# - Simple-DataTables (CDN)
# - HTMX (CDN)
# - Tabler Icons (CDN oder inline SVG)

# Für SSE (Server-Sent Events)
# Keine extra Dependency nötig - Flask kann das nativ
```

---

## 5. Konfiguration

### Neue ENV-Variablen

```env
# Flask
FLASK_SECRET_KEY=your-secret-key
FLASK_DEBUG=true

# Datenbank
DATABASE_URL=sqlite:///data/collector.db
```

### Config-Erweiterung (config.py)

```python
@dataclass
class FlaskConfig:
    secret_key: str = field(default_factory=lambda: os.getenv("FLASK_SECRET_KEY", "dev"))
    debug: bool = field(default_factory=lambda: os.getenv("FLASK_DEBUG", "true").lower() == "true")
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/collector.db"))
```

---

## 6. CLI vs. Web Koexistenz

| Funktion | CLI (bestehend) | Web (neu) |
|----------|-----------------|-----------|
| Scraping | `python -m src.scraper` | Jobs-Seite startet Subprocess |
| Enrichment | `python -m src.enrich_*` | Jobs-Seite startet Subprocess |
| Blacklist bearbeiten | Texteditor | Web-UI |
| Status prüfen | Logs lesen | Dashboard |

**Wichtig**: Die bestehenden CLI-Tools werden NICHT verändert. Das Web-Frontend ruft sie als Subprocesse auf.

---

## 7. Realtime Log-Streaming

### Technologie: Server-Sent Events (SSE)

```python
# Beispiel: Job-Output streamen
@jobs_bp.route('/stream/<int:job_id>')
def stream_job_output(job_id):
    def generate():
        process = subprocess.Popen(
            ['python', '-m', 'src.enrich_from_search', ...],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in iter(process.stdout.readline, ''):
            yield f"data: {line}\n\n"

    return Response(generate(), mimetype='text/event-stream')
```

### Frontend (HTMX + SSE)

```html
<div hx-ext="sse" sse-connect="/jobs/stream/1" sse-swap="message">
    <!-- Log-Ausgabe erscheint hier in Echtzeit -->
</div>
```

---

## 8. Nächste Schritte

Nach Genehmigung dieses PRDs:

1. PRD-002: Database Schema (SQLite Tabellen)
2. PRD-003: Dashboard UI
3. PRD-004: Blacklist Editor
4. PRD-005: Job Runner mit Realtime Output
