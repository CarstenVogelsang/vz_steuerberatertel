# PRD-003: Dashboard UI

## Status

Draft | Version 1.0 | 2025-12-27

## Übersicht

Das Dashboard ist die Startseite der Flask-Anwendung und bietet einen schnellen Überblick über den Zustand des Systems: Statistiken, laufende Jobs und letzte Aktivitäten.

---

## 1. User Stories

| ID | Als... | möchte ich... | damit ich... |
|----|--------|---------------|--------------|
| D-1 | Benutzer | Statistiken auf einen Blick sehen | den Fortschritt des Projekts verfolgen kann |
| D-2 | Benutzer | laufende Jobs sehen | weiß, was gerade passiert |
| D-3 | Benutzer | letzte Job-Ergebnisse sehen | Erfolge und Fehler schnell erkenne |
| D-4 | Benutzer | zur Blacklist/Jobs navigieren | schnell zwischen Funktionen wechseln kann |

---

## 2. Wireframe

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  COLLECTOR DATEV                          [Blacklist] [Jobs] [Dashboard]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │   📊 1.247  │ │   ✅ 892    │ │   ⚠️ 203    │ │   🚫 152    │       │
│  │   Gesamt    │ │   Website   │ │   Niedrig   │ │   Keine     │       │
│  │   Einträge  │ │   gefunden  │ │   Konfidenz │ │   Website   │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
│                                                                         │
│  ┌─────────────────────────────────┐ ┌─────────────────────────────────┐│
│  │  🔄 LAUFENDE JOBS               │ │  📋 LETZTE JOBS                 ││
│  ├─────────────────────────────────┤ ├─────────────────────────────────┤│
│  │  ▶ enrich_search (PLZ 4)        │ │  ✅ enrich_email    12:34  45s  ││
│  │    ████████░░ 80%  seit 2:34    │ │  ✅ scraper         11:20  2m   ││
│  │                                 │ │  ❌ enrich_search   10:15  Error││
│  │  (keine weiteren)               │ │  ✅ enrich_email    09:00  1m   ││
│  │                                 │ │                                 ││
│  │  [Neuen Job starten →]          │ │  [Alle Jobs anzeigen →]         ││
│  └─────────────────────────────────┘ └─────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  📊 KONFIDENZ-VERTEILUNG (PLZ 4)                                    ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │  Hoch     ████████████████████████████████████████  456 (36%)       ││
│  │  Mittel   ██████████████████████                    278 (22%)       ││
│  │  Niedrig  ████████████████                          203 (16%)       ││
│  │  Keine    ████████████                              152 (12%)       ││
│  │  Baustelle████████                                  102 (8%)        ││
│  │  Offen    ██████                                     56 (4%)        ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Komponenten

### 3.1 Statistik-Karten (Stats Cards)

Vier Karten mit Hauptmetriken:

| Karte | Wert | Icon | Farbe |
|-------|------|------|-------|
| Gesamt Einträge | Anzahl aller Zeilen in Google Sheets | `chart-bar` | Blau |
| Website gefunden | Einträge mit Website (Spalte K) | `check-circle` | Grün |
| Niedrige Konfidenz | Konfidenz = "niedrig" oder "mittel" | `alert-triangle` | Orange |
| Keine Website | Spalte K leer + Konfidenz "keine" | `x-circle` | Rot |

**daisyUI-Komponente:** `stat` in `stats` Container

```html
<div class="stats shadow">
  <div class="stat">
    <div class="stat-figure text-primary">
      <svg><!-- Tabler Icon --></svg>
    </div>
    <div class="stat-title">Gesamt Einträge</div>
    <div class="stat-value text-primary">1.247</div>
    <div class="stat-desc">PLZ-Bereich 4xxxx</div>
  </div>
  <!-- weitere stats -->
</div>
```

---

### 3.2 Laufende Jobs (Running Jobs)

Zeigt aktuell laufende Jobs mit Fortschritt:

| Feld | Beschreibung |
|------|--------------|
| Job-Typ | Icon + Name (z.B. "enrich_search") |
| Parameter | Wichtigste Parameter (z.B. "PLZ 4") |
| Fortschritt | Prozentbalken (falls verfügbar) |
| Laufzeit | "seit X:XX" |
| Aktionen | [Abbrechen] Button |

**daisyUI-Komponente:** `card` mit `progress`

```html
<div class="card bg-base-100 shadow">
  <div class="card-body">
    <h2 class="card-title">
      <span class="badge badge-info">Läuft</span>
      enrich_search
    </h2>
    <p class="text-sm text-base-content/70">PLZ-Filter: 4</p>
    <progress class="progress progress-primary" value="80" max="100"></progress>
    <div class="flex justify-between text-sm">
      <span>80%</span>
      <span>seit 2:34</span>
    </div>
  </div>
</div>
```

---

### 3.3 Letzte Jobs (Recent Jobs)

Tabelle der letzten 5-10 abgeschlossenen Jobs:

| Spalte | Beschreibung |
|--------|--------------|
| Status | Icon (✅/❌/⚠️) |
| Typ | Job-Typ |
| Parameter | Kurzform der Parameter |
| Zeit | Startzeit (HH:MM) |
| Dauer | Sekunden/Minuten |
| Aktionen | [Logs] Button |

**daisyUI-Komponente:** `table` mit `table-zebra`

```html
<table class="table table-zebra">
  <thead>
    <tr>
      <th>Status</th>
      <th>Job</th>
      <th>Zeit</th>
      <th>Dauer</th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge badge-success">✓</span></td>
      <td>enrich_email</td>
      <td>12:34</td>
      <td>45s</td>
      <td><button class="btn btn-xs btn-ghost">Logs</button></td>
    </tr>
  </tbody>
</table>
```

---

### 3.4 Konfidenz-Verteilung (Chart)

Horizontales Balkendiagramm der Website-Konfidenz-Verteilung:

| Konfidenz | Farbe | Beschreibung |
|-----------|-------|--------------|
| Hoch | Grün | Name in Title/H1 |
| Mittel | Hellgrün | Name im Body |
| Niedrig | Orange | Seite erreichbar, Name nicht gefunden |
| Baustelle | Gelb | Under Construction erkannt |
| Keine | Rot | Keine Website gefunden |
| Offen | Grau | Noch nicht geprüft |

**Implementierung:** Pure CSS mit Tailwind (kein Chart.js nötig)

```html
<div class="space-y-2">
  <div class="flex items-center gap-2">
    <span class="w-20 text-sm">Hoch</span>
    <div class="flex-1 bg-base-200 rounded-full h-4">
      <div class="bg-success h-4 rounded-full" style="width: 36%"></div>
    </div>
    <span class="w-16 text-sm text-right">456 (36%)</span>
  </div>
  <!-- weitere Balken -->
</div>
```

---

## 4. Datenquellen

### 4.1 Statistik-Karten

**Quelle:** Google Sheets API (via bestehender `sheets_handler.py`)

```python
# app/services/stats_service.py
from src.sheets_handler import get_client, open_sheet_by_plz_group

def get_sheet_stats(plz_group: int) -> dict:
    """Hole Statistiken aus Google Sheets."""
    client = get_client(config.credentials_path)
    worksheet = open_sheet_by_plz_group(client, config.sheet_url, plz_group)

    all_values = worksheet.get_all_values()[1:]  # Skip header

    total = len(all_values)
    with_website = sum(1 for row in all_values if len(row) > 10 and row[10])
    low_confidence = sum(1 for row in all_values
                         if len(row) > 12 and row[12].lower() in ['niedrig', 'mittel'])
    no_website = sum(1 for row in all_values
                     if len(row) > 10 and not row[10]
                     and (len(row) <= 12 or row[12].lower() == 'keine'))

    return {
        'total': total,
        'with_website': with_website,
        'low_confidence': low_confidence,
        'no_website': no_website,
    }
```

### 4.2 Job-Daten

**Quelle:** SQLite Datenbank (via SQLAlchemy Models aus PRD-002)

```python
# app/services/job_service.py
from app.models import Job

def get_running_jobs() -> list[Job]:
    """Hole alle laufenden Jobs."""
    return Job.query.filter_by(status='running').all()

def get_recent_jobs(limit: int = 10) -> list[Job]:
    """Hole die letzten abgeschlossenen Jobs."""
    return Job.query.filter(
        Job.status.in_(['completed', 'failed', 'cancelled'])
    ).order_by(Job.finished_at.desc()).limit(limit).all()
```

### 4.3 Konfidenz-Verteilung

**Quelle:** Google Sheets API (aggregiert)

```python
def get_confidence_distribution(plz_group: int) -> dict:
    """Hole Konfidenz-Verteilung aus Google Sheets."""
    # ... worksheet laden ...

    distribution = {
        'hoch': 0,
        'mittel': 0,
        'niedrig': 0,
        'baustelle': 0,
        'keine': 0,
        'offen': 0,
    }

    for row in all_values:
        website = row[10] if len(row) > 10 else ''
        confidence = row[12].lower() if len(row) > 12 else ''

        if not website and not confidence:
            distribution['offen'] += 1
        elif confidence in distribution:
            distribution[confidence] += 1

    return distribution
```

---

## 5. Route & Template

### 5.1 Route

```python
# app/routes/dashboard.py
from flask import Blueprint, render_template
from app.services import stats_service, job_service

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    """Dashboard-Startseite."""
    # Standard: PLZ-Gruppe 4
    plz_group = 4

    stats = stats_service.get_sheet_stats(plz_group)
    running_jobs = job_service.get_running_jobs()
    recent_jobs = job_service.get_recent_jobs(limit=5)
    distribution = stats_service.get_confidence_distribution(plz_group)

    return render_template('dashboard/index.html',
                           stats=stats,
                           running_jobs=running_jobs,
                           recent_jobs=recent_jobs,
                           distribution=distribution,
                           plz_group=plz_group)
```

### 5.2 Template-Struktur

```text
app/templates/
├── base.html                 # Layout mit Navigation
└── dashboard/
    ├── index.html            # Dashboard-Seite
    └── partials/
        ├── stats_cards.html  # Statistik-Karten
        ├── running_jobs.html # Laufende Jobs
        ├── recent_jobs.html  # Letzte Jobs
        └── distribution.html # Konfidenz-Verteilung
```

---

## 6. HTMX-Integration

### 6.1 Auto-Refresh für laufende Jobs

```html
<!-- Aktualisiert alle 5 Sekunden -->
<div hx-get="/api/running-jobs"
     hx-trigger="every 5s"
     hx-swap="innerHTML">
  {% include 'dashboard/partials/running_jobs.html' %}
</div>
```

### 6.2 PLZ-Gruppe wechseln

```html
<select name="plz_group"
        hx-get="/dashboard"
        hx-target="#main-content"
        hx-push-url="true"
        class="select select-bordered">
  <option value="0">PLZ 0xxxx</option>
  <option value="1">PLZ 1xxxx</option>
  <!-- ... -->
  <option value="4" selected>PLZ 4xxxx</option>
  <!-- ... -->
</select>
```

---

## 7. API-Endpoints für HTMX

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/running-jobs` | GET | Partial: Laufende Jobs |
| `/api/recent-jobs` | GET | Partial: Letzte Jobs |
| `/api/stats/<plz_group>` | GET | Partial: Statistik-Karten |

```python
# app/routes/api.py
from flask import Blueprint, render_template

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/running-jobs')
def running_jobs():
    """HTMX Partial: Laufende Jobs."""
    jobs = job_service.get_running_jobs()
    return render_template('dashboard/partials/running_jobs.html',
                           running_jobs=jobs)
```

---

## 8. Responsive Design

### Breakpoints (Tailwind)

| Breakpoint | Layout |
|------------|--------|
| `sm` (640px) | Stats: 2x2 Grid |
| `md` (768px) | Stats: 4x1, Jobs nebeneinander |
| `lg` (1024px) | Volle Breite |

```html
<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
  <!-- Stats Cards -->
</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
  <!-- Running Jobs | Recent Jobs -->
</div>
```

---

## 9. Performance-Optimierung

### 9.1 Caching

Google Sheets API-Aufrufe werden gecacht:

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=10)
def get_sheet_stats_cached(plz_group: int, cache_key: str) -> dict:
    """Gecachte Statistiken (5 Minuten TTL)."""
    return get_sheet_stats(plz_group)

def get_stats_with_cache(plz_group: int) -> dict:
    # Cache-Key basiert auf 5-Minuten-Intervall
    cache_key = datetime.now().strftime('%Y%m%d%H') + str(datetime.now().minute // 5)
    return get_sheet_stats_cached(plz_group, cache_key)
```

### 9.2 Lazy Loading

Konfidenz-Verteilung wird erst nach Seitenload via HTMX nachgeladen:

```html
<div hx-get="/api/distribution/4"
     hx-trigger="load"
     hx-swap="innerHTML">
  <div class="skeleton h-32 w-full"></div>
</div>
```

---

## 10. Nächste Schritte

Nach Genehmigung dieses PRDs:

1. PRD-004: Blacklist Editor (CRUD-Operationen)
2. PRD-005: Job Runner mit Realtime Output
