"""Blacklist Blueprint.

CRUD operations for domain blacklist management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import db
from app.models import Domain

blacklist_bp = Blueprint("blacklist", __name__, url_prefix="/blacklist")


@blacklist_bp.route("/")
def index():
    """List all blacklisted domains."""
    domains = Domain.query.order_by(Domain.category, Domain.domain).all()
    categories = Domain.CATEGORIES
    return render_template(
        "blacklist/index.html",
        domains=domains,
        categories=categories,
    )


@blacklist_bp.route("/add", methods=["POST"])
def add():
    """Add a new domain to the blacklist."""
    domain = request.form.get("domain", "").strip().lower()
    category = request.form.get("category", "unsortiert")
    reason = request.form.get("reason", "").strip()

    if not domain:
        flash("Domain darf nicht leer sein.", "error")
        return redirect(url_for("blacklist.index"))

    # Check if domain already exists
    existing = Domain.query.filter_by(domain=domain).first()
    if existing:
        flash(f"Domain '{domain}' existiert bereits.", "warning")
        return redirect(url_for("blacklist.index"))

    # Create new domain entry
    new_domain = Domain(
        domain=domain,
        category=category,
        reason=reason,
        created_by="web-ui",
    )
    db.session.add(new_domain)
    db.session.commit()

    # Export to TXT file
    _export_blacklist_to_txt()

    flash(f"Domain '{domain}' hinzugefügt.", "success")
    return redirect(url_for("blacklist.index"))


@blacklist_bp.route("/edit/<int:domain_id>", methods=["POST"])
def edit(domain_id: int):
    """Edit an existing domain entry."""
    domain_entry = Domain.query.get_or_404(domain_id)

    domain_entry.domain = request.form.get("domain", domain_entry.domain).strip().lower()
    domain_entry.category = request.form.get("category", domain_entry.category)
    domain_entry.reason = request.form.get("reason", "").strip()

    db.session.commit()

    # Export to TXT file
    _export_blacklist_to_txt()

    flash(f"Domain '{domain_entry.domain}' aktualisiert.", "success")
    return redirect(url_for("blacklist.index"))


@blacklist_bp.route("/delete/<int:domain_id>", methods=["POST"])
def delete(domain_id: int):
    """Delete a domain from the blacklist."""
    domain_entry = Domain.query.get_or_404(domain_id)
    domain_name = domain_entry.domain

    db.session.delete(domain_entry)
    db.session.commit()

    # Export to TXT file
    _export_blacklist_to_txt()

    flash(f"Domain '{domain_name}' gelöscht.", "success")
    return redirect(url_for("blacklist.index"))


def _export_blacklist_to_txt():
    """Export blacklist to domain_blacklist.txt after each change."""
    from pathlib import Path
    from flask import current_app

    data_dir = current_app.config["PROJECT_ROOT"] / "data"
    filepath = data_dir / "domain_blacklist.txt"

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
