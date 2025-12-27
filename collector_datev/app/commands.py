"""Flask CLI Commands.

Custom commands for database initialization and blacklist management.
"""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from app import db
from app.models import Domain


def register_commands(app: Flask):
    """Register all CLI commands with the Flask app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(import_blacklist_command)
    app.cli.add_command(export_blacklist_command)
    app.cli.add_command(seed_command)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Initialize the database (create all tables)."""
    db.create_all()
    click.echo("Datenbank initialisiert.")


@click.command("import-blacklist")
@click.argument("filepath", default="data/domain_blacklist.txt")
@with_appcontext
def import_blacklist_command(filepath: str):
    """Import blacklist from TXT file.

    FILEPATH: Path to the blacklist file (default: data/domain_blacklist.txt)
    """
    from pathlib import Path
    from flask import current_app

    # Resolve path relative to project root
    if not filepath.startswith("/"):
        filepath = current_app.config["PROJECT_ROOT"] / filepath
    else:
        filepath = Path(filepath)

    if not filepath.exists():
        click.echo(f"Datei nicht gefunden: {filepath}")
        return

    count = 0
    current_category = "unsortiert"

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Category header
            if line.startswith("#"):
                category = line[1:].strip().lower()
                # Map common category names
                if category in ("email-provider", "e-mail provider"):
                    current_category = "email-provider"
                elif category in ("hosting", "hosting provider"):
                    current_category = "hosting"
                elif category in ("verzeichnis", "steuerberater-verzeichnisse"):
                    current_category = "verzeichnis"
                else:
                    current_category = "unsortiert"
                continue

            # Domain line
            domain = line.lower()
            existing = Domain.query.filter_by(domain=domain).first()
            if not existing:
                new_domain = Domain(
                    domain=domain,
                    category=current_category,
                    created_by="import",
                )
                db.session.add(new_domain)
                count += 1

    db.session.commit()
    click.echo(f"{count} Domains importiert.")


@click.command("export-blacklist")
@click.argument("filepath", default="data/domain_blacklist.txt")
@with_appcontext
def export_blacklist_command(filepath: str):
    """Export blacklist to TXT file.

    FILEPATH: Path to the output file (default: data/domain_blacklist.txt)
    """
    from pathlib import Path
    from flask import current_app

    # Resolve path relative to project root
    if not filepath.startswith("/"):
        filepath = current_app.config["PROJECT_ROOT"] / filepath
    else:
        filepath = Path(filepath)

    domains = Domain.query.order_by(Domain.category, Domain.domain).all()

    with open(filepath, "w") as f:
        current_category = None
        for domain in domains:
            if domain.category != current_category:
                if current_category is not None:
                    f.write("\n")
                f.write(f"# {domain.category.title()}\n")
                current_category = domain.category
            f.write(f"{domain.domain}\n")

    click.echo(f"{len(domains)} Domains exportiert nach {filepath}.")


@click.command("seed")
@with_appcontext
def seed_command():
    """Seed the database with initial data (import existing blacklist)."""
    from pathlib import Path
    from flask import current_app

    # Import blacklist if it exists
    blacklist_path = current_app.config["PROJECT_ROOT"] / "data" / "domain_blacklist.txt"
    if blacklist_path.exists():
        click.echo("Importiere bestehende Blacklist...")
        # Use the import command logic
        import_blacklist_command.main(["data/domain_blacklist.txt"], standalone_mode=False)
    else:
        click.echo("Keine bestehende Blacklist gefunden.")

    click.echo("Seed abgeschlossen.")
