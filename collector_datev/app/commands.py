"""Flask CLI Commands.

Custom commands for database initialization and blacklist management.
"""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from app import db
from app.models import Domain, Category


def register_commands(app: Flask):
    """Register all CLI commands with the Flask app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(import_blacklist_command)
    app.cli.add_command(export_blacklist_command)
    app.cli.add_command(seed_command)
    app.cli.add_command(seed_categories_command)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Initialize the database (create all tables)."""
    db.create_all()
    click.echo("Datenbank initialisiert.")


@click.command("seed-categories")
@with_appcontext
def seed_categories_command():
    """Create default categories if they don't exist."""
    count = Category.seed_defaults()
    if count > 0:
        click.echo(f"{count} Standard-Kategorien erstellt.")
    else:
        click.echo("Alle Standard-Kategorien existieren bereits.")


@click.command("import-blacklist")
@click.argument("filepath", default="data/domain_blacklist.txt")
@with_appcontext
def import_blacklist_command(filepath: str):
    """Import blacklist from TXT file.

    FILEPATH: Path to the blacklist file (default: data/domain_blacklist.txt)
    """
    from pathlib import Path
    from flask import current_app

    # Ensure categories exist first
    Category.seed_defaults()

    # Resolve path relative to project root
    if not filepath.startswith("/"):
        filepath = current_app.config["PROJECT_ROOT"] / filepath
    else:
        filepath = Path(filepath)

    if not filepath.exists():
        click.echo(f"Datei nicht gefunden: {filepath}")
        return

    count = 0
    current_category_slug = "unsortiert"

    # Category mapping for common names in TXT file
    category_mappings = {
        "email-provider": "email-provider",
        "e-mail provider": "email-provider",
        "hosting": "hosting",
        "hosting provider": "hosting",
        "verzeichnis": "verzeichnis",
        "verzeichnisse": "verzeichnis",
        "steuerberater-verzeichnisse": "verzeichnis",
        "social-media": "social-media",
        "unsortiert": "unsortiert",
    }

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Category header
            if line.startswith("#"):
                category_name = line[1:].strip().lower()
                current_category_slug = category_mappings.get(category_name, "unsortiert")
                continue

            # Domain line
            domain = line.lower()
            existing = Domain.query.filter_by(domain=domain).first()
            if not existing:
                # Find category by slug
                category = Category.query.filter_by(slug=current_category_slug).first()

                new_domain = Domain(
                    domain=domain,
                    category_id=category.id if category else None,
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

    # Get all domains ordered by category and domain name
    domains = (
        Domain.query
        .outerjoin(Category)
        .order_by(Category.sort_order, Domain.domain)
        .all()
    )

    with open(filepath, "w") as f:
        current_category_id = -1  # Sentinel to detect first category
        for domain in domains:
            cat_id = domain.category_id or 0
            if cat_id != current_category_id:
                if current_category_id != -1:
                    f.write("\n")
                category_name = domain.category_slug if domain.category_rel else "unsortiert"
                f.write(f"# {category_name}\n")
                current_category_id = cat_id
            f.write(f"{domain.domain}\n")

    click.echo(f"{len(domains)} Domains exportiert nach {filepath}.")


@click.command("seed")
@with_appcontext
def seed_command():
    """Seed the database with initial data (categories + existing blacklist)."""
    from pathlib import Path
    from flask import current_app

    # First, create default categories
    click.echo("Erstelle Standard-Kategorien...")
    count = Category.seed_defaults()
    click.echo(f"  {count} Kategorien erstellt.")

    # Import blacklist if it exists
    blacklist_path = current_app.config["PROJECT_ROOT"] / "data" / "domain_blacklist.txt"
    if blacklist_path.exists():
        click.echo("Importiere bestehende Blacklist...")
        # Use the import command logic inline
        import_blacklist_command.main(["data/domain_blacklist.txt"], standalone_mode=False)
    else:
        click.echo("Keine bestehende Blacklist gefunden.")

    click.echo("Seed abgeschlossen.")
