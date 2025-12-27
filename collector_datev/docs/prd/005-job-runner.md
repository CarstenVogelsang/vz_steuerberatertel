# PRD-005: Job Runner mit Realtime Output

## Status

Draft | Version 1.0 | 2025-12-27

## Übersicht

Web-Interface zum Starten und Überwachen von Jobs (Scraper, Enrichment) mit Echtzeit-Log-Ausgabe via Server-Sent Events (SSE).

---

## 1. Funktionsumfang

### 1.1 Kernfunktionen

| Funktion | Beschreibung |
|----------|--------------|
| Job starten | CLI-Tools als Subprocess ausführen |
| Parameter-Konfiguration | PLZ-Filter, Confidence-Level, Provider, etc. |
| Realtime-Logs | Log-Output live im Browser via SSE |
| Job-Status | Pending → Running → Completed/Failed |
| Job-Abbruch | Laufenden Job manuell stoppen |
| Job-Historie | Vergangene Jobs mit Logs einsehen |

### 1.2 Unterstützte Job-Typen

| Typ | CLI-Befehl | Parameter |
|-----|------------|-----------|
| `scraper` | `python -m src.scraper` | `--plz-filter`, `--headless` |
| `enrich_email` | `python -m src.enrich_from_email` | `--plz-filter`, `--dry-run` |
| `enrich_search` | `python -m src.enrich_from_search` | `--plz-filter`, `--confidence-filter`, `--search-provider`, `--headless` |
| `blacklist_sync` | (intern) | - |

---

## 2. UI-Wireframe

### 2.1 Job-Übersicht (`/jobs`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ JOBS                                                        [+ Neuer Job]   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─ LAUFENDER JOB ──────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  🔄 enrich_search                          Gestartet: 14:32:15       │  │
│  │     PLZ: 4*, Confidence: none,low          Laufzeit: 00:05:23        │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │ [LOG OUTPUT - Live Streaming]                                   │ │  │
│  │  │                                                                 │ │  │
│  │  │ 14:32:15 INFO  Starte Phase 2 Enrichment...                    │ │  │
│  │  │ 14:32:16 INFO  Lade Einträge für PLZ 4*...                     │ │  │
│  │  │ 14:32:18 INFO  127 Einträge gefunden                           │ │  │
│  │  │ 14:32:20 INFO  [1/127] Mustermann, Stefan                      │ │  │
│  │  │ 14:32:25 INFO  → Website gefunden: steuerberater-mustermann.de │ │  │
│  │  │ 14:32:26 INFO  [2/127] Beispiel GmbH                           │ │  │
│  │  │ 14:32:31 INFO  → Keine Website gefunden                        │ │  │
│  │  │ ...                                                  [Auto-Scroll] │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                       │  │
│  │                                                    [Abbrechen]        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ LETZTE JOBS ────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  Typ              Status      Gestartet    Dauer     Aktion          │  │
│  │  ─────────────────────────────────────────────────────────────────── │  │
│  │  enrich_email     ✅ Success  Heute 12:15  00:08:42  [Logs anzeigen] │  │
│  │  scraper          ✅ Success  Heute 10:30  00:45:12  [Logs anzeigen] │  │
│  │  enrich_search    ❌ Failed   Gestern      00:02:33  [Logs anzeigen] │  │
│  │  blacklist_sync   ✅ Success  Gestern      00:00:01  [Logs anzeigen] │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Neuer Job Modal

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ NEUEN JOB STARTEN                                                      [X] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Job-Typ:                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [▼] DATEV Scraper                                                   │   │
│  │     Phase 1: E-Mail-Domain Enrichment                               │   │
│  │     Phase 2: Websuche Enrichment                     ← ausgewählt   │   │
│  │     Blacklist Sync                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ─── Parameter für Phase 2 ─────────────────────────────────────────────   │
│                                                                             │
│  PLZ-Filter:           [4      ]  (leer = alle, "4" = PLZ 40000-49999)     │
│                                                                             │
│  Confidence-Level:     [☑] Keine Website (none)                            │
│                        [☑] Niedrig (low)                                   │
│                        [ ] Mittel (medium)                                 │
│                                                                             │
│  Such-Provider:        ( ) DuckDuckGo (kostenlos, instabil)                │
│                        (•) Serper (2.500 free/Monat, stabil)               │
│                        ( ) SerpAPI (kostenpflichtig)                       │
│                                                                             │
│  Optionen:             [☑] Headless Mode (unsichtbarer Browser)            │
│                        [ ] Dry Run (keine Änderungen speichern)            │
│                                                                             │
│                                           [Abbrechen]  [▶ Job starten]     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Job-Detail Modal (für vergangene Jobs)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ JOB #42 - enrich_search                                                [X] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Status:     ✅ Completed                                                   │
│  Gestartet:  2025-12-27 12:15:00                                           │
│  Beendet:    2025-12-27 12:23:42                                           │
│  Dauer:      00:08:42                                                       │
│  Exit-Code:  0                                                              │
│                                                                             │
│  Parameter:                                                                 │
│  • PLZ-Filter: 4*                                                          │
│  • Confidence: none, low                                                   │
│  • Provider: serper                                                        │
│  • Headless: true                                                          │
│                                                                             │
│  ─── Log-Ausgabe ───────────────────────────────────────────────────────   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 12:15:00 INFO  Starte Phase 2 Enrichment...                        │   │
│  │ 12:15:01 INFO  Lade Einträge für PLZ 4*...                         │   │
│  │ 12:15:03 INFO  127 Einträge gefunden                               │   │
│  │ ...                                                                 │   │
│  │ 12:23:40 INFO  Verarbeitung abgeschlossen                          │   │
│  │ 12:23:41 SUCCESS 89 Websites gefunden, 38 ohne Ergebnis            │   │
│  │ 12:23:42 INFO  Job beendet                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                                           [Log herunterladen]  [Schließen] │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technische Architektur

### 3.1 Subprocess-Management

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Browser     │────▶│  Flask App   │────▶│  Subprocess  │
│  (HTMX/SSE)  │◀────│  (JobService)│◀────│  (CLI-Tool)  │
└──────────────┘     └──────────────┘     └──────────────┘
      │                     │                     │
      │  SSE: log lines     │  stdout/stderr      │
      │◀────────────────────│◀────────────────────│
```

### 3.2 SSE-Flow

1. Browser startet Job via POST `/api/jobs`
2. Server erstellt Job-Eintrag (status=pending)
3. Server startet Subprocess asynchron
4. Server setzt Job-Status auf "running"
5. Browser verbindet sich zu SSE-Endpoint `/jobs/stream/<job_id>`
6. Server streamt stdout/stderr Zeile für Zeile
7. Bei Job-Ende: Status → completed/failed, SSE schließen

---

## 4. daisyUI-Komponenten

### 4.1 Job-Typ-Auswahl (Radio Cards)

```html
<div class="form-control">
    <label class="label cursor-pointer gap-4 border rounded-lg p-4 hover:bg-base-200">
        <div class="flex items-center gap-3">
            <input type="radio" name="job_type" value="scraper" class="radio radio-primary">
            <div>
                <span class="font-semibold">DATEV Scraper</span>
                <p class="text-sm text-base-content/70">Steuerberater von DATEV scrapen</p>
            </div>
        </div>
    </label>

    <label class="label cursor-pointer gap-4 border rounded-lg p-4 hover:bg-base-200 mt-2">
        <div class="flex items-center gap-3">
            <input type="radio" name="job_type" value="enrich_search" class="radio radio-primary" checked>
            <div>
                <span class="font-semibold">Phase 2: Websuche</span>
                <p class="text-sm text-base-content/70">Website-Enrichment via Suchmaschine</p>
            </div>
        </div>
    </label>
</div>
```

### 4.2 Log-Terminal

```html
<div class="mockup-code bg-base-300 text-base-content max-h-96 overflow-y-auto" id="log-output">
    <pre data-prefix="14:32:15"><code class="text-info">INFO  Starte Phase 2 Enrichment...</code></pre>
    <pre data-prefix="14:32:16"><code class="text-info">INFO  Lade Einträge für PLZ 4*...</code></pre>
    <pre data-prefix="14:32:18"><code class="text-info">INFO  127 Einträge gefunden</code></pre>
    <pre data-prefix="14:32:25"><code class="text-success">SUCCESS Website gefunden: example.de</code></pre>
    <pre data-prefix="14:32:31"><code class="text-warning">WARNING Keine Website gefunden</code></pre>
    <pre data-prefix="14:32:45"><code class="text-error">ERROR Timeout bei Suchanfrage</code></pre>
</div>
```

### 4.3 Status-Badge

```html
<!-- Pending -->
<span class="badge badge-ghost gap-1">
    <span class="loading loading-spinner loading-xs"></span>
    Pending
</span>

<!-- Running -->
<span class="badge badge-info gap-1">
    <span class="loading loading-spinner loading-xs"></span>
    Running
</span>

<!-- Completed -->
<span class="badge badge-success gap-1">
    <svg class="w-4 h-4"><!-- check icon --></svg>
    Completed
</span>

<!-- Failed -->
<span class="badge badge-error gap-1">
    <svg class="w-4 h-4"><!-- x icon --></svg>
    Failed
</span>
```

### 4.4 Progress-Indicator

```html
<div class="flex items-center gap-4">
    <progress class="progress progress-primary w-56" value="42" max="127"></progress>
    <span class="text-sm">42 / 127 Einträge</span>
</div>
```

---

## 5. API-Endpunkte

### 5.1 REST API

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `GET` | `/jobs` | Job-Übersicht (HTML) |
| `POST` | `/api/jobs` | Neuen Job starten |
| `GET` | `/api/jobs/<id>` | Job-Details (JSON) |
| `DELETE` | `/api/jobs/<id>` | Job abbrechen |
| `GET` | `/jobs/stream/<id>` | SSE Log-Stream |
| `GET` | `/api/jobs/<id>/logs` | Alle Logs (JSON) |
| `GET` | `/api/jobs/<id>/logs/download` | Logs als TXT |

### 5.2 Request/Response Beispiele

**POST `/api/jobs`** - Neuen Job starten:

```json
// Request
{
    "job_type": "enrich_search",
    "parameters": {
        "plz_filter": "4",
        "confidence_filter": ["none", "low"],
        "search_provider": "serper",
        "headless": true,
        "dry_run": false
    }
}

// Response
{
    "id": 42,
    "job_type": "enrich_search",
    "status": "pending",
    "created_at": "2025-12-27T14:32:15Z"
}
```

**GET `/api/jobs/42`** - Job-Status:

```json
{
    "id": 42,
    "job_type": "enrich_search",
    "status": "running",
    "parameters": { ... },
    "started_at": "2025-12-27T14:32:16Z",
    "finished_at": null,
    "duration_seconds": 312,
    "log_count": 156
}
```

---

## 6. Service-Implementierung

### 6.1 JobService

```python
# app/services/job_service.py
import subprocess
import threading
from datetime import datetime
from app import db
from app.models import Job, LogEntry

class JobService:
    # Aktive Prozesse (job_id -> subprocess.Popen)
    _processes: dict[int, subprocess.Popen] = {}

    @classmethod
    def start_job(cls, job_type: str, parameters: dict) -> Job:
        """Startet einen neuen Job als Subprocess."""
        job = Job(
            job_type=job_type,
            status='pending',
            parameters=parameters,
        )
        db.session.add(job)
        db.session.commit()

        # Subprocess in Thread starten
        thread = threading.Thread(
            target=cls._run_subprocess,
            args=(job.id, job_type, parameters),
            daemon=True
        )
        thread.start()

        return job

    @classmethod
    def _run_subprocess(cls, job_id: int, job_type: str, parameters: dict):
        """Führt den Subprocess aus und speichert Logs."""
        from flask import current_app

        # CLI-Befehl zusammenbauen
        cmd = cls._build_command(job_type, parameters)

        with current_app.app_context():
            job = Job.query.get(job_id)
            job.status = 'running'
            job.started_at = datetime.utcnow()
            db.session.commit()

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line-buffered
                    cwd=current_app.config['PROJECT_ROOT'],
                )
                cls._processes[job_id] = process

                # Logs speichern
                for line in iter(process.stdout.readline, ''):
                    line = line.rstrip()
                    if line:
                        log_entry = LogEntry(
                            job_id=job_id,
                            level=cls._parse_log_level(line),
                            message=line,
                        )
                        db.session.add(log_entry)
                        db.session.commit()

                process.wait()
                exit_code = process.returncode

                job.status = 'completed' if exit_code == 0 else 'failed'
                job.exit_code = exit_code
                job.finished_at = datetime.utcnow()

            except Exception as e:
                job.status = 'failed'
                job.error_message = str(e)
                job.finished_at = datetime.utcnow()

            finally:
                cls._processes.pop(job_id, None)
                db.session.commit()

    @classmethod
    def _build_command(cls, job_type: str, parameters: dict) -> list[str]:
        """Baut den CLI-Befehl aus Job-Typ und Parametern."""
        if job_type == 'scraper':
            cmd = ['uv', 'run', 'python', '-m', 'src.scraper']
            if parameters.get('plz_filter'):
                cmd.extend(['--plz-filter', parameters['plz_filter']])
            if parameters.get('headless'):
                cmd.append('--headless')

        elif job_type == 'enrich_email':
            cmd = ['uv', 'run', 'python', '-m', 'src.enrich_from_email']
            if parameters.get('plz_filter'):
                cmd.extend(['--plz-filter', parameters['plz_filter']])
            if parameters.get('dry_run'):
                cmd.append('--dry-run')

        elif job_type == 'enrich_search':
            cmd = ['uv', 'run', 'python', '-m', 'src.enrich_from_search']
            if parameters.get('plz_filter'):
                cmd.extend(['--plz-filter', parameters['plz_filter']])
            if parameters.get('confidence_filter'):
                for cf in parameters['confidence_filter']:
                    cmd.extend(['--confidence-filter', cf])
            if parameters.get('search_provider'):
                cmd.extend(['--search-provider', parameters['search_provider']])
            if parameters.get('headless'):
                cmd.append('--headless')
            if parameters.get('dry_run'):
                cmd.append('--dry-run')

        else:
            raise ValueError(f"Unbekannter Job-Typ: {job_type}")

        return cmd

    @classmethod
    def _parse_log_level(cls, line: str) -> str:
        """Extrahiert Log-Level aus Zeile."""
        line_upper = line.upper()
        if 'ERROR' in line_upper:
            return 'ERROR'
        elif 'WARNING' in line_upper or 'WARN' in line_upper:
            return 'WARNING'
        elif 'SUCCESS' in line_upper:
            return 'SUCCESS'
        elif 'DEBUG' in line_upper:
            return 'DEBUG'
        return 'INFO'

    @classmethod
    def cancel_job(cls, job_id: int) -> bool:
        """Bricht einen laufenden Job ab."""
        process = cls._processes.get(job_id)
        if process:
            process.terminate()
            job = Job.query.get(job_id)
            if job:
                job.status = 'cancelled'
                job.finished_at = datetime.utcnow()
                db.session.commit()
            return True
        return False

    @classmethod
    def get_running_job(cls) -> Job | None:
        """Gibt den aktuell laufenden Job zurück (max. 1)."""
        return Job.query.filter_by(status='running').first()

    @classmethod
    def get_recent_jobs(cls, limit: int = 10) -> list[Job]:
        """Gibt die letzten Jobs zurück."""
        return Job.query.order_by(Job.created_at.desc()).limit(limit).all()
```

### 6.2 SSE-Streaming Route

```python
# app/routes/jobs.py
from flask import Blueprint, Response, stream_with_context
from app.models import Job, LogEntry
import time

jobs_bp = Blueprint('jobs', __name__, url_prefix='/jobs')

@jobs_bp.route('/stream/<int:job_id>')
def stream_logs(job_id: int):
    """SSE-Endpoint für Live-Log-Streaming."""

    def generate():
        last_log_id = 0
        while True:
            job = Job.query.get(job_id)
            if not job:
                yield f"event: error\ndata: Job nicht gefunden\n\n"
                break

            # Neue Logs abrufen
            new_logs = LogEntry.query.filter(
                LogEntry.job_id == job_id,
                LogEntry.id > last_log_id
            ).order_by(LogEntry.id).all()

            for log in new_logs:
                data = {
                    'id': log.id,
                    'level': log.level,
                    'message': log.message,
                    'timestamp': log.timestamp.strftime('%H:%M:%S'),
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_log_id = log.id

            # Job beendet?
            if job.status in ('completed', 'failed', 'cancelled'):
                yield f"event: done\ndata: {job.status}\n\n"
                break

            time.sleep(0.5)  # Polling-Intervall

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Nginx buffering deaktivieren
        }
    )
```

---

## 7. Frontend JavaScript

### 7.1 SSE-Client

```javascript
// static/js/job-stream.js

class JobStreamClient {
    constructor(jobId, logContainer) {
        this.jobId = jobId;
        this.logContainer = logContainer;
        this.eventSource = null;
        this.autoScroll = true;
    }

    connect() {
        this.eventSource = new EventSource(`/jobs/stream/${this.jobId}`);

        this.eventSource.onmessage = (event) => {
            const log = JSON.parse(event.data);
            this.appendLog(log);
        };

        this.eventSource.addEventListener('done', (event) => {
            this.disconnect();
            this.onJobComplete(event.data);
        });

        this.eventSource.addEventListener('error', (event) => {
            console.error('SSE Error:', event);
            this.disconnect();
        });
    }

    appendLog(log) {
        const levelClass = {
            'INFO': 'text-info',
            'SUCCESS': 'text-success',
            'WARNING': 'text-warning',
            'ERROR': 'text-error',
            'DEBUG': 'text-base-content/50',
        }[log.level] || 'text-base-content';

        const pre = document.createElement('pre');
        pre.setAttribute('data-prefix', log.timestamp);
        pre.innerHTML = `<code class="${levelClass}">${this.escapeHtml(log.message)}</code>`;
        this.logContainer.appendChild(pre);

        if (this.autoScroll) {
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    onJobComplete(status) {
        // Override in consumer
        console.log('Job completed with status:', status);
    }
}
```

### 7.2 Job-Start Formular (HTMX)

```html
<form hx-post="/api/jobs"
      hx-target="#job-result"
      hx-swap="innerHTML"
      hx-indicator="#submit-spinner">

    <!-- Job-Typ Auswahl -->
    <select name="job_type" class="select select-bordered w-full"
            hx-get="/api/jobs/parameters"
            hx-target="#parameter-fields"
            hx-trigger="change">
        <option value="scraper">DATEV Scraper</option>
        <option value="enrich_email">Phase 1: E-Mail-Domain</option>
        <option value="enrich_search" selected>Phase 2: Websuche</option>
    </select>

    <!-- Dynamische Parameter -->
    <div id="parameter-fields">
        <!-- Wird via HTMX geladen -->
    </div>

    <button type="submit" class="btn btn-primary">
        <span class="loading loading-spinner htmx-indicator" id="submit-spinner"></span>
        Job starten
    </button>
</form>
```

---

## 8. Concurrent Jobs

### 8.1 Regel: Nur ein Job gleichzeitig

Da die CLI-Tools auf dieselbe Google Sheets Tabelle zugreifen, darf nur **ein Job gleichzeitig** laufen.

```python
@api_bp.route('/jobs', methods=['POST'])
def create_job():
    # Prüfen ob bereits ein Job läuft
    running_job = JobService.get_running_job()
    if running_job:
        return jsonify({
            'error': 'Es läuft bereits ein Job',
            'running_job': {
                'id': running_job.id,
                'job_type': running_job.job_type,
                'started_at': running_job.started_at.isoformat(),
            }
        }), 409  # Conflict

    # Job starten
    data = request.get_json()
    job = JobService.start_job(
        job_type=data['job_type'],
        parameters=data.get('parameters', {}),
    )

    return jsonify({
        'id': job.id,
        'job_type': job.job_type,
        'status': job.status,
    }), 201
```

---

## 9. Templates

### 9.1 Job-Übersicht

```html
<!-- templates/jobs/index.html -->
{% extends "base.html" %}

{% block content %}
<div class="flex justify-between items-center mb-6">
    <h1 class="text-2xl font-bold">Jobs</h1>
    <button class="btn btn-primary" onclick="new_job_modal.showModal()">
        <svg class="w-5 h-5"><!-- plus icon --></svg>
        Neuer Job
    </button>
</div>

<!-- Laufender Job -->
{% if running_job %}
<div class="card bg-base-100 shadow-xl mb-6">
    <div class="card-body">
        <div class="flex justify-between items-start">
            <div>
                <h2 class="card-title">
                    <span class="loading loading-spinner loading-sm"></span>
                    {{ running_job.job_type }}
                </h2>
                <p class="text-sm text-base-content/70">
                    Gestartet: {{ running_job.started_at.strftime('%H:%M:%S') }}
                </p>
            </div>
            <form hx-delete="/api/jobs/{{ running_job.id }}"
                  hx-confirm="Job wirklich abbrechen?">
                <button class="btn btn-outline btn-error btn-sm">
                    Abbrechen
                </button>
            </form>
        </div>

        <!-- Log-Output -->
        <div class="mockup-code bg-base-300 max-h-96 overflow-y-auto mt-4"
             id="live-log-output">
            <!-- Logs werden via SSE eingefügt -->
        </div>
    </div>
</div>

<script>
    const client = new JobStreamClient({{ running_job.id }}, document.getElementById('live-log-output'));
    client.connect();
    client.onJobComplete = (status) => {
        // Seite neu laden um Status zu aktualisieren
        htmx.ajax('GET', '/jobs', {target: 'body', swap: 'innerHTML'});
    };
</script>
{% endif %}

<!-- Job-Historie -->
<div class="card bg-base-100 shadow-xl">
    <div class="card-body">
        <h2 class="card-title">Letzte Jobs</h2>
        <div class="overflow-x-auto">
            <table class="table" id="jobs-table">
                <thead>
                    <tr>
                        <th>Typ</th>
                        <th>Status</th>
                        <th>Gestartet</th>
                        <th>Dauer</th>
                        <th>Aktion</th>
                    </tr>
                </thead>
                <tbody>
                    {% for job in recent_jobs %}
                    <tr>
                        <td>{{ job.job_type }}</td>
                        <td>
                            {% if job.status == 'completed' %}
                            <span class="badge badge-success">Erfolgreich</span>
                            {% elif job.status == 'failed' %}
                            <span class="badge badge-error">Fehlgeschlagen</span>
                            {% elif job.status == 'cancelled' %}
                            <span class="badge badge-warning">Abgebrochen</span>
                            {% endif %}
                        </td>
                        <td>{{ job.started_at.strftime('%d.%m.%Y %H:%M') if job.started_at else '-' }}</td>
                        <td>{{ job.duration | format_duration if job.duration else '-' }}</td>
                        <td>
                            <button class="btn btn-ghost btn-sm"
                                    hx-get="/api/jobs/{{ job.id }}/modal"
                                    hx-target="#job-detail-modal">
                                Logs
                            </button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- Neuer Job Modal -->
<dialog id="new_job_modal" class="modal">
    <div class="modal-box w-11/12 max-w-2xl">
        <h3 class="font-bold text-lg mb-4">Neuen Job starten</h3>
        <!-- Formular hier -->
        <form method="dialog">
            <button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2">✕</button>
        </form>
    </div>
</dialog>

<!-- Job-Detail Modal (dynamisch) -->
<div id="job-detail-modal"></div>

{% endblock %}
```

---

## 10. Fehlerbehandlung

### 10.1 Subprocess-Fehler

| Fehler | Handling |
|--------|----------|
| Exit-Code ≠ 0 | Status → "failed", Exit-Code speichern |
| Timeout | Nach 1h automatisch abbrechen |
| Exception | Status → "failed", Error-Message speichern |
| Manueller Abbruch | Status → "cancelled" |

### 10.2 SSE-Fehler

| Fehler | Handling |
|--------|----------|
| Verbindungsabbruch | Auto-Reconnect nach 3s |
| Job nicht gefunden | Error-Event senden, Stream schließen |
| Server-Neustart | Client erhält Error, kann manuell neu verbinden |

---

## 11. Konfiguration

```python
# app/config.py

class Config:
    # Job-Timeouts
    JOB_TIMEOUT_SECONDS = 3600  # 1 Stunde
    JOB_POLL_INTERVAL = 0.5     # SSE Polling

    # Projekt-Root für Subprocess
    PROJECT_ROOT = Path(__file__).parent.parent
```

---

## 12. Nächste Schritte

Nach Genehmigung aller PRDs:

1. Flask-App Grundgerüst erstellen
2. SQLite Schema implementieren (PRD-002)
3. Dashboard implementieren (PRD-003)
4. Blacklist-Editor implementieren (PRD-004)
5. Job-Runner implementieren (PRD-005)
6. Integration-Tests

---

## Anhang: Job-Parameter je Typ

### Scraper

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `plz_filter` | string | PLZ-Präfix (z.B. "4" für 40000-49999) |
| `headless` | boolean | Browser unsichtbar ausführen |

### Enrich Email (Phase 1)

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `plz_filter` | string | PLZ-Präfix |
| `dry_run` | boolean | Keine Änderungen speichern |

### Enrich Search (Phase 2)

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `plz_filter` | string | PLZ-Präfix |
| `confidence_filter` | array | ["none", "low", "medium"] |
| `search_provider` | string | "serper", "duckduckgo", "serpapi" |
| `headless` | boolean | Browser unsichtbar |
| `dry_run` | boolean | Keine Änderungen speichern |
