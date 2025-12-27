# PRD-004: Blacklist Editor

## Status

Draft | Version 1.0 | 2025-12-27

## Übersicht

Der Blacklist Editor ermöglicht die Verwaltung der Domain-Blacklist über eine Web-Oberfläche. Domains in der Blacklist werden bei der Website-Erkennung (Phase 1 + 2) übersprungen.

---

## 1. User Stories

| ID | Als... | möchte ich... | damit ich... |
|----|--------|---------------|--------------|
| B-1 | Benutzer | alle Blacklist-Domains sehen | einen Überblick habe |
| B-2 | Benutzer | Domains suchen/filtern | schnell finde was ich suche |
| B-3 | Benutzer | neue Domains hinzufügen | E-Mail-Provider blockieren kann |
| B-4 | Benutzer | Domains bearbeiten | Kategorie/Grund anpassen kann |
| B-5 | Benutzer | Domains löschen | Fehler korrigieren kann |
| B-6 | Benutzer | nach Kategorie filtern | nur bestimmte Typen sehe |
| B-7 | Benutzer | die Blacklist exportieren | sie als TXT-Datei nutzen kann |
| B-8 | Benutzer | eine TXT importieren | bestehende Listen übernehmen kann |

---

## 2. Wireframe

### 2.1 Listenansicht

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  COLLECTOR DATEV                          [Blacklist] [Jobs] [Dashboard]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  📋 DOMAIN BLACKLIST                                      [+ Hinzufügen]│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ 🔍 [Suche...]              [Alle ▾] [Email ▾] [Hosting ▾] [Verz. ▾]││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Domain           │ Kategorie      │ Grund              │ Aktionen  ││
│  ├──────────────────┼────────────────┼────────────────────┼───────────┤│
│  │ gmail.com        │ 📧 Email       │ Google Mail        │ [✏️] [🗑️] ││
│  │ gmx.de           │ 📧 Email       │ GMX Freemail       │ [✏️] [🗑️] ││
│  │ web.de           │ 📧 Email       │ Web.de Freemail    │ [✏️] [🗑️] ││
│  │ t-online.de      │ 📧 Email       │ Telekom            │ [✏️] [🗑️] ││
│  │ strato.de        │ 🏠 Hosting     │ Hosting Provider   │ [✏️] [🗑️] ││
│  │ 1und1.de         │ 🏠 Hosting     │ Hosting Provider   │ [✏️] [🗑️] ││
│  │ steuerberater.de │ 📚 Verzeichnis │ Verzeichnisdienst  │ [✏️] [🗑️] ││
│  │ ...              │                │                    │           ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  Zeige 1-25 von 203 Einträgen          [◀ Zurück] [1] [2] [3] [Weiter ▶]│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ [📥 TXT Importieren]                            [📤 TXT Exportieren]││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Hinzufügen/Bearbeiten Modal

```text
┌───────────────────────────────────────────┐
│  Domain hinzufügen                    [X] │
├───────────────────────────────────────────┤
│                                           │
│  Domain *                                 │
│  ┌─────────────────────────────────────┐  │
│  │ beispiel.de                         │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  Kategorie                                │
│  ┌─────────────────────────────────────┐  │
│  │ Email-Provider               ▾      │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  Grund (optional)                         │
│  ┌─────────────────────────────────────┐  │
│  │                                     │  │
│  └─────────────────────────────────────┘  │
│                                           │
│           [Abbrechen]  [Speichern]        │
│                                           │
└───────────────────────────────────────────┘
```

---

## 3. Komponenten

### 3.1 Tabelle mit Simple-DataTables

Die Haupttabelle nutzt Simple-DataTables für:
- **Sortierung** (Klick auf Spaltenheader)
- **Suche** (Volltextsuche)
- **Pagination** (25 Einträge pro Seite)

```html
<table id="blacklist-table" class="table table-zebra w-full">
  <thead>
    <tr>
      <th>Domain</th>
      <th>Kategorie</th>
      <th>Grund</th>
      <th>Aktionen</th>
    </tr>
  </thead>
  <tbody>
    {% for domain in domains %}
    <tr>
      <td>{{ domain.domain }}</td>
      <td>
        <span class="badge badge-{{ domain.category | category_color }}">
          {{ domain.category }}
        </span>
      </td>
      <td>{{ domain.reason or '-' }}</td>
      <td>
        <button class="btn btn-xs btn-ghost"
                hx-get="/blacklist/{{ domain.id }}/edit"
                hx-target="#modal-container">
          <svg><!-- Edit Icon --></svg>
        </button>
        <button class="btn btn-xs btn-ghost text-error"
                hx-delete="/blacklist/{{ domain.id }}"
                hx-confirm="Domain '{{ domain.domain }}' wirklich löschen?"
                hx-target="closest tr"
                hx-swap="outerHTML swap:1s">
          <svg><!-- Delete Icon --></svg>
        </button>
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<script>
  new simpleDatatables.DataTable("#blacklist-table", {
    searchable: true,
    sortable: true,
    perPage: 25,
    labels: {
      placeholder: "Suchen...",
      perPage: "Einträge pro Seite",
      noRows: "Keine Domains gefunden",
      info: "Zeige {start} bis {end} von {rows} Einträgen"
    }
  });
</script>
```

### 3.2 Kategorie-Filter

Schnellfilter als Toggle-Buttons:

```html
<div class="btn-group">
  <button class="btn btn-sm"
          hx-get="/blacklist?category=all"
          hx-target="#table-container"
          hx-push-url="true">
    Alle
  </button>
  <button class="btn btn-sm btn-outline"
          hx-get="/blacklist?category=email-provider"
          hx-target="#table-container">
    📧 Email
  </button>
  <button class="btn btn-sm btn-outline"
          hx-get="/blacklist?category=hosting"
          hx-target="#table-container">
    🏠 Hosting
  </button>
  <button class="btn btn-sm btn-outline"
          hx-get="/blacklist?category=verzeichnis"
          hx-target="#table-container">
    📚 Verzeichnis
  </button>
</div>
```

### 3.3 Modal (daisyUI)

```html
<dialog id="domain-modal" class="modal">
  <div class="modal-box">
    <h3 class="font-bold text-lg">Domain hinzufügen</h3>
    <form hx-post="/blacklist"
          hx-target="#table-container"
          hx-on::after-request="document.getElementById('domain-modal').close()">

      <div class="form-control w-full">
        <label class="label">
          <span class="label-text">Domain *</span>
        </label>
        <input type="text" name="domain" required
               placeholder="beispiel.de"
               class="input input-bordered w-full" />
      </div>

      <div class="form-control w-full mt-4">
        <label class="label">
          <span class="label-text">Kategorie</span>
        </label>
        <select name="category" class="select select-bordered w-full">
          <option value="unsortiert">Unsortiert</option>
          <option value="email-provider">Email-Provider</option>
          <option value="hosting">Hosting</option>
          <option value="verzeichnis">Verzeichnis</option>
        </select>
      </div>

      <div class="form-control w-full mt-4">
        <label class="label">
          <span class="label-text">Grund (optional)</span>
        </label>
        <input type="text" name="reason"
               class="input input-bordered w-full" />
      </div>

      <div class="modal-action">
        <button type="button" class="btn" onclick="domain_modal.close()">
          Abbrechen
        </button>
        <button type="submit" class="btn btn-primary">
          Speichern
        </button>
      </div>
    </form>
  </div>
  <form method="dialog" class="modal-backdrop">
    <button>close</button>
  </form>
</dialog>
```

---

## 4. API-Endpoints

### 4.1 REST-Endpoints

| Methode | Endpoint | Beschreibung |
|---------|----------|--------------|
| GET | `/blacklist` | Liste aller Domains (mit Filter) |
| GET | `/blacklist/<id>` | Einzelne Domain |
| GET | `/blacklist/<id>/edit` | Edit-Modal (HTMX Partial) |
| POST | `/blacklist` | Domain hinzufügen |
| PUT | `/blacklist/<id>` | Domain aktualisieren |
| DELETE | `/blacklist/<id>` | Domain löschen |
| GET | `/blacklist/export` | TXT-Export |
| POST | `/blacklist/import` | TXT-Import |

### 4.2 Route-Implementierung

```python
# app/routes/blacklist.py
from flask import Blueprint, render_template, request, jsonify, Response
from app.models import Domain
from app import db

blacklist_bp = Blueprint('blacklist', __name__, url_prefix='/blacklist')

@blacklist_bp.route('/')
def index():
    """Blacklist-Übersicht."""
    category = request.args.get('category', 'all')

    query = Domain.query
    if category != 'all':
        query = query.filter_by(category=category)

    domains = query.order_by(Domain.domain).all()

    # HTMX Partial oder Full Page
    if request.headers.get('HX-Request'):
        return render_template('blacklist/partials/table.html', domains=domains)

    return render_template('blacklist/index.html',
                           domains=domains,
                           current_category=category)


@blacklist_bp.route('/', methods=['POST'])
def create():
    """Domain hinzufügen."""
    domain = request.form.get('domain', '').strip().lower()
    category = request.form.get('category', 'unsortiert')
    reason = request.form.get('reason', '').strip()

    # Validierung
    if not domain:
        return '<div class="alert alert-error">Domain ist erforderlich</div>', 400

    # Duplikat-Check
    existing = Domain.query.filter_by(domain=domain).first()
    if existing:
        return f'<div class="alert alert-warning">Domain "{domain}" existiert bereits</div>', 400

    # Erstellen
    new_domain = Domain(
        domain=domain,
        category=category,
        reason=reason or None,
        created_by='web-ui'
    )
    db.session.add(new_domain)
    db.session.commit()

    # Automatischer TXT-Export
    export_blacklist_to_file()

    # Tabelle neu laden
    domains = Domain.query.order_by(Domain.domain).all()
    return render_template('blacklist/partials/table.html', domains=domains)


@blacklist_bp.route('/<int:id>', methods=['DELETE'])
def delete(id):
    """Domain löschen."""
    domain = Domain.query.get_or_404(id)
    db.session.delete(domain)
    db.session.commit()

    # Automatischer TXT-Export
    export_blacklist_to_file()

    # Leere Response = Zeile wird entfernt (hx-swap="outerHTML")
    return ''


@blacklist_bp.route('/<int:id>/edit')
def edit_modal(id):
    """Edit-Modal als Partial."""
    domain = Domain.query.get_or_404(id)
    return render_template('blacklist/partials/edit_modal.html', domain=domain)


@blacklist_bp.route('/<int:id>', methods=['PUT'])
def update(id):
    """Domain aktualisieren."""
    domain = Domain.query.get_or_404(id)

    domain.category = request.form.get('category', domain.category)
    domain.reason = request.form.get('reason', '').strip() or None

    db.session.commit()

    # Automatischer TXT-Export
    export_blacklist_to_file()

    # Aktualisierte Zeile zurückgeben
    return render_template('blacklist/partials/table_row.html', domain=domain)


@blacklist_bp.route('/export')
def export():
    """TXT-Export."""
    domains = Domain.query.order_by(Domain.category, Domain.domain).all()

    lines = []
    current_category = None

    for domain in domains:
        if domain.category != current_category:
            if current_category is not None:
                lines.append('')
            lines.append(f'# {domain.category.title()}')
            current_category = domain.category
        lines.append(domain.domain)

    content = '\n'.join(lines)

    return Response(
        content,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=domain_blacklist.txt'}
    )


@blacklist_bp.route('/import', methods=['POST'])
def import_file():
    """TXT-Import."""
    if 'file' not in request.files:
        return '<div class="alert alert-error">Keine Datei ausgewählt</div>', 400

    file = request.files['file']
    if file.filename == '':
        return '<div class="alert alert-error">Keine Datei ausgewählt</div>', 400

    content = file.read().decode('utf-8')
    imported = 0
    skipped = 0

    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            existing = Domain.query.filter_by(domain=line.lower()).first()
            if not existing:
                new_domain = Domain(
                    domain=line.lower(),
                    created_by='import'
                )
                db.session.add(new_domain)
                imported += 1
            else:
                skipped += 1

    db.session.commit()

    # Automatischer TXT-Export
    export_blacklist_to_file()

    return f'''
        <div class="alert alert-success">
            Import abgeschlossen: {imported} hinzugefügt, {skipped} übersprungen
        </div>
    '''
```

---

## 5. Service-Funktionen

```python
# app/services/blacklist_service.py
from pathlib import Path
from app.models import Domain
from app import db

BLACKLIST_PATH = Path(__file__).parent.parent.parent / 'data' / 'domain_blacklist.txt'


def export_blacklist_to_file():
    """Exportiert die Blacklist in die TXT-Datei.

    Wird automatisch nach jeder Änderung aufgerufen.
    """
    domains = Domain.query.order_by(Domain.category, Domain.domain).all()

    lines = []
    current_category = None

    for domain in domains:
        if domain.category != current_category:
            if current_category is not None:
                lines.append('')
            lines.append(f'# {domain.category.title()}')
            current_category = domain.category
        lines.append(domain.domain)

    BLACKLIST_PATH.write_text('\n'.join(lines), encoding='utf-8')


def import_blacklist_from_file():
    """Importiert die Blacklist aus der TXT-Datei.

    Wird beim App-Start aufgerufen, falls DB leer ist.
    """
    if not BLACKLIST_PATH.exists():
        return 0

    if Domain.query.count() > 0:
        return 0  # DB ist nicht leer

    content = BLACKLIST_PATH.read_text(encoding='utf-8')
    current_category = 'unsortiert'
    imported = 0

    for line in content.splitlines():
        line = line.strip()

        if line.startswith('#'):
            # Kategorie-Header
            category = line[1:].strip().lower()
            if category in ['email-provider', 'hosting', 'verzeichnis', 'unsortiert']:
                current_category = category
            continue

        if line:
            new_domain = Domain(
                domain=line.lower(),
                category=current_category,
                created_by='import'
            )
            db.session.add(new_domain)
            imported += 1

    db.session.commit()
    return imported
```

---

## 6. Validierung

### 6.1 Domain-Format

```python
import re

def validate_domain(domain: str) -> tuple[bool, str]:
    """Validiert ein Domain-Format.

    Returns:
        Tuple (is_valid, error_message)
    """
    domain = domain.strip().lower()

    # Leere Domain
    if not domain:
        return False, "Domain darf nicht leer sein"

    # Protokoll entfernen
    if domain.startswith(('http://', 'https://')):
        return False, "Bitte nur die Domain ohne http:// eingeben"

    # www. entfernen
    if domain.startswith('www.'):
        domain = domain[4:]

    # Pfad entfernen
    if '/' in domain:
        return False, "Bitte nur die Domain ohne Pfad eingeben"

    # Domain-Pattern
    pattern = r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z]{2,})+$'
    if not re.match(pattern, domain):
        return False, "Ungültiges Domain-Format"

    return True, ""
```

---

## 7. Toast-Benachrichtigungen

Feedback via daisyUI Toast (unten rechts):

```html
<!-- Toast Container -->
<div id="toast-container" class="toast toast-end toast-bottom z-50">
  <!-- Toasts werden hier via HTMX eingefügt -->
</div>

<!-- Beispiel Toast -->
<div class="alert alert-success" hx-swap-oob="beforeend:#toast-container">
  <span>Domain erfolgreich hinzugefügt</span>
</div>
```

```python
# In Route nach erfolgreicher Aktion:
response = make_response(render_template(...))
response.headers['HX-Trigger'] = json.dumps({
    'showToast': {'message': 'Domain hinzugefügt', 'type': 'success'}
})
return response
```

---

## 8. Kategorie-Farben

| Kategorie | Badge-Klasse | Farbe |
|-----------|--------------|-------|
| email-provider | `badge-info` | Blau |
| hosting | `badge-warning` | Orange |
| verzeichnis | `badge-secondary` | Grau |
| unsortiert | `badge-ghost` | Transparent |

```python
# Jinja2 Filter
@app.template_filter('category_color')
def category_color(category):
    colors = {
        'email-provider': 'info',
        'hosting': 'warning',
        'verzeichnis': 'secondary',
        'unsortiert': 'ghost',
    }
    return colors.get(category, 'ghost')
```

---

## 9. Template-Struktur

```text
app/templates/blacklist/
├── index.html              # Hauptseite
└── partials/
    ├── table.html          # Tabelle (für HTMX-Refresh)
    ├── table_row.html      # Einzelne Zeile (für Update)
    ├── add_modal.html      # Hinzufügen-Modal
    ├── edit_modal.html     # Bearbeiten-Modal
    └── import_form.html    # Import-Formular
```

---

## 10. Automatische Synchronisation

### 10.1 TXT-Export nach Änderung

Nach jeder CRUD-Operation wird `export_blacklist_to_file()` aufgerufen:
- Die CLI-Tools (`enrich_from_email`, `enrich_from_search`) lesen weiterhin aus `domain_blacklist.txt`
- Die Web-UI ist Single Source of Truth
- Änderungen in der TXT-Datei werden beim nächsten Import übernommen

### 10.2 Import beim App-Start

```python
# app/__init__.py
def create_app():
    app = Flask(__name__)
    # ... config ...

    with app.app_context():
        db.create_all()

        # Initial-Import falls DB leer
        from app.services.blacklist_service import import_blacklist_from_file
        imported = import_blacklist_from_file()
        if imported > 0:
            app.logger.info(f'{imported} Domains aus TXT importiert')

    return app
```

---

## 11. Nächste Schritte

Nach Genehmigung dieses PRDs:

1. PRD-005: Job Runner mit Realtime Output
