# PRD-002: Database Schema

## Status

Draft | Version 1.0 | 2025-12-26

## Übersicht

SQLite-Datenbankschema für die Flask-Erweiterung. Speichert nur Kontrolldaten - Steuerberater-Stammdaten bleiben in Google Sheets.

---

## 1. Tabellen-Übersicht

| Tabelle | Zweck | Anzahl Einträge (geschätzt) |
|---------|-------|----------------------------|
| `domains` | Blacklist-Domains | ~200-500 |
| `jobs` | Job-Ausführungen | ~100-1000 |
| `log_entries` | Job-Logs | ~10.000-100.000 |

---

## 2. Schema-Definition

### 2.1 Tabelle: `domains` (Blacklist)

Speichert die Domain-Blacklist für E-Mail-Provider und generische Domains.

```sql
CREATE TABLE domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(50) DEFAULT 'unsortiert',
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system'
);

CREATE INDEX idx_domains_domain ON domains(domain);
CREATE INDEX idx_domains_category ON domains(category);
```

**Felder:**

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER | Auto-Increment Primary Key |
| `domain` | VARCHAR(255) | Domain ohne Protokoll (z.B. "gmail.com") |
| `category` | VARCHAR(50) | Kategorie: "email-provider", "hosting", "unsortiert" |
| `reason` | TEXT | Optionale Begründung |
| `created_at` | TIMESTAMP | Erstellungszeitpunkt |
| `created_by` | VARCHAR(100) | Ersteller: "system", "import", "web-ui" |

**Kategorien:**

| Kategorie | Beschreibung |
|-----------|--------------|
| `email-provider` | GMX, Web.de, Gmail, etc. |
| `hosting` | Strato, 1und1, etc. |
| `verzeichnis` | Steuerberater-Verzeichnisse |
| `unsortiert` | Noch nicht kategorisiert |

---

### 2.2 Tabelle: `jobs` (Job-Ausführungen)

Speichert Informationen über gestartete Jobs.

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    parameters JSON,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_job_type ON jobs(job_type);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
```

**Felder:**

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER | Auto-Increment Primary Key |
| `job_type` | VARCHAR(50) | Job-Typ (siehe unten) |
| `status` | VARCHAR(20) | Status des Jobs |
| `parameters` | JSON | Job-Parameter als JSON |
| `started_at` | TIMESTAMP | Startzeit |
| `finished_at` | TIMESTAMP | Endzeit |
| `exit_code` | INTEGER | Exit-Code des Subprocesses |
| `error_message` | TEXT | Fehlermeldung bei Abbruch |
| `created_at` | TIMESTAMP | Erstellungszeitpunkt |

**Job-Typen:**

| Typ | CLI-Befehl | Beschreibung |
|-----|------------|--------------|
| `scraper` | `python -m src.scraper` | DATEV-Scraping |
| `enrich_email` | `python -m src.enrich_from_email` | Phase 1: E-Mail-Domain |
| `enrich_search` | `python -m src.enrich_from_search` | Phase 2: Websuche |
| `blacklist_sync` | - | Blacklist aus TXT importieren |

**Status-Werte:**

| Status | Beschreibung |
|--------|--------------|
| `pending` | Job erstellt, noch nicht gestartet |
| `running` | Job läuft gerade |
| `completed` | Job erfolgreich beendet |
| `failed` | Job mit Fehler beendet |
| `cancelled` | Job abgebrochen |

**Beispiel-Parameter (JSON):**

```json
{
    "plz_filter": "4",
    "confidence_filter": ["none", "low"],
    "search_provider": "brave",
    "headless": true,
    "dry_run": false
}
```

---

### 2.3 Tabelle: `log_entries` (Job-Logs)

Speichert Log-Einträge für jeden Job.

```sql
CREATE TABLE log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    level VARCHAR(10) NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_log_entries_job_id ON log_entries(job_id);
CREATE INDEX idx_log_entries_timestamp ON log_entries(timestamp DESC);
CREATE INDEX idx_log_entries_level ON log_entries(level);
```

**Felder:**

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER | Auto-Increment Primary Key |
| `job_id` | INTEGER | Foreign Key zu `jobs.id` |
| `level` | VARCHAR(10) | Log-Level |
| `message` | TEXT | Log-Nachricht |
| `timestamp` | TIMESTAMP | Zeitstempel |

**Log-Level:**

| Level | Beschreibung |
|-------|--------------|
| `DEBUG` | Debug-Informationen |
| `INFO` | Normale Informationen |
| `WARNING` | Warnungen |
| `ERROR` | Fehler |
| `SUCCESS` | Erfolgsmeldung (custom) |

---

## 3. SQLAlchemy Models

### 3.1 Domain Model

```python
# app/models/domain.py
from datetime import datetime
from app import db

class Domain(db.Model):
    __tablename__ = 'domains'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False)
    category = db.Column(db.String(50), default='unsortiert')
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), default='system')

    def __repr__(self):
        return f'<Domain {self.domain}>'
```

### 3.2 Job Model

```python
# app/models/job.py
from datetime import datetime
from app import db

class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    parameters = db.Column(db.JSON)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    exit_code = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    log_entries = db.relationship('LogEntry', backref='job', lazy='dynamic',
                                   cascade='all, delete-orphan')

    @property
    def duration(self):
        """Berechne Job-Dauer in Sekunden."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def __repr__(self):
        return f'<Job {self.id} {self.job_type} [{self.status}]>'
```

### 3.3 LogEntry Model

```python
# app/models/log_entry.py
from datetime import datetime
from app import db

class LogEntry(db.Model):
    __tablename__ = 'log_entries'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False, default='INFO')
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LogEntry {self.level}: {self.message[:50]}>'
```

---

## 4. Migrations

### 4.1 Initiale Migration

```bash
# Alembic initialisieren
flask db init

# Erste Migration erstellen
flask db migrate -m "Initial schema: domains, jobs, log_entries"

# Migration anwenden
flask db upgrade
```

### 4.2 Flask-CLI Commands

```python
# app/commands.py
import click
from flask.cli import with_appcontext
from app import db
from app.models import Domain

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Datenbank initialisieren."""
    db.create_all()
    click.echo('Datenbank initialisiert.')

@click.command('import-blacklist')
@click.argument('filepath', default='data/domain_blacklist.txt')
@with_appcontext
def import_blacklist_command(filepath):
    """Blacklist aus TXT-Datei importieren."""
    from pathlib import Path

    path = Path(filepath)
    if not path.exists():
        click.echo(f'Datei nicht gefunden: {filepath}')
        return

    count = 0
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                existing = Domain.query.filter_by(domain=line.lower()).first()
                if not existing:
                    domain = Domain(domain=line.lower(), created_by='import')
                    db.session.add(domain)
                    count += 1

    db.session.commit()
    click.echo(f'{count} Domains importiert.')

@click.command('export-blacklist')
@click.argument('filepath', default='data/domain_blacklist.txt')
@with_appcontext
def export_blacklist_command(filepath):
    """Blacklist nach TXT-Datei exportieren."""
    domains = Domain.query.order_by(Domain.category, Domain.domain).all()

    with open(filepath, 'w') as f:
        current_category = None
        for domain in domains:
            if domain.category != current_category:
                if current_category is not None:
                    f.write('\n')
                f.write(f'# {domain.category.title()}\n')
                current_category = domain.category
            f.write(f'{domain.domain}\n')

    click.echo(f'{len(domains)} Domains exportiert nach {filepath}.')
```

---

## 5. Datenmigration

### 5.1 Bestehende Blacklist importieren

Bei der ersten Initialisierung wird die bestehende `domain_blacklist.txt` in die Datenbank importiert:

```bash
flask import-blacklist data/domain_blacklist.txt
```

### 5.2 Bidirektionale Sync-Strategie

| Richtung | Trigger | Aktion |
|----------|---------|--------|
| TXT → DB | Manuell oder beim App-Start | `flask import-blacklist` |
| DB → TXT | Nach jeder Änderung im Web-UI | Automatischer Export |

---

## 6. Datenbank-Pfad

**Speicherort:** `collector_datev/data/collector.db`

```python
# app/__init__.py
import os
from pathlib import Path

def create_app():
    app = Flask(__name__)

    # Datenbank-Pfad
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{data_dir}/collector.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ...
```

---

## 7. Nächste Schritte

Nach Genehmigung dieses PRDs:

1. PRD-003: Dashboard UI (Statistiken, Job-Übersicht)
2. PRD-004: Blacklist Editor (CRUD-Operationen)
3. PRD-005: Job Runner mit Realtime Output
