"""Blacklist Blueprint.

CRUD operations for domain blacklist and category management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import db
from app.models import Domain, Category

blacklist_bp = Blueprint("blacklist", __name__, url_prefix="/blacklist")


# ============================================================================
# Domain Routes
# ============================================================================

@blacklist_bp.route("/")
def index():
    """List all blacklisted domains."""
    domains = (
        Domain.query
        .outerjoin(Category)
        .order_by(Category.sort_order, Domain.domain)
        .all()
    )
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template(
        "blacklist/index.html",
        domains=domains,
        categories=categories,
    )


@blacklist_bp.route("/add", methods=["POST"])
def add():
    """Add a new domain to the blacklist."""
    domain = request.form.get("domain", "").strip().lower()
    category_id = request.form.get("category_id", type=int)
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
        category_id=category_id,
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
    domain_entry.category_id = request.form.get("category_id", type=int)
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


# ============================================================================
# Category Routes
# ============================================================================

@blacklist_bp.route("/categories")
def categories():
    """List all categories."""
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template(
        "blacklist/categories.html",
        categories=categories,
        badge_colors=Category.BADGE_COLORS,
    )


@blacklist_bp.route("/categories/add", methods=["POST"])
def add_category():
    """Add a new category."""
    slug = request.form.get("slug", "").strip().lower().replace(" ", "-")
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    color = request.form.get("color", "ghost")
    sort_order = request.form.get("sort_order", 0, type=int)

    if not slug or not name:
        flash("Slug und Name sind Pflichtfelder.", "error")
        return redirect(url_for("blacklist.categories"))

    # Check if slug already exists
    existing = Category.query.filter_by(slug=slug).first()
    if existing:
        flash(f"Kategorie mit Slug '{slug}' existiert bereits.", "warning")
        return redirect(url_for("blacklist.categories"))

    new_category = Category(
        slug=slug,
        name=name,
        description=description,
        color=color,
        sort_order=sort_order,
    )
    db.session.add(new_category)
    db.session.commit()

    flash(f"Kategorie '{name}' erstellt.", "success")
    return redirect(url_for("blacklist.categories"))


@blacklist_bp.route("/categories/edit/<int:category_id>", methods=["POST"])
def edit_category(category_id: int):
    """Edit an existing category."""
    category = Category.query.get_or_404(category_id)

    category.slug = request.form.get("slug", category.slug).strip().lower().replace(" ", "-")
    category.name = request.form.get("name", category.name).strip()
    category.description = request.form.get("description", "").strip()
    category.color = request.form.get("color", category.color)
    category.sort_order = request.form.get("sort_order", category.sort_order, type=int)

    db.session.commit()

    # Re-export blacklist with updated category names
    _export_blacklist_to_txt()

    flash(f"Kategorie '{category.name}' aktualisiert.", "success")
    return redirect(url_for("blacklist.categories"))


@blacklist_bp.route("/categories/delete/<int:category_id>", methods=["POST"])
def delete_category(category_id: int):
    """Delete a category and move its domains to 'unsortiert'."""
    category = Category.query.get_or_404(category_id)

    if category.slug == "unsortiert":
        flash("Die Kategorie 'Unsortiert' kann nicht gelöscht werden.", "error")
        return redirect(url_for("blacklist.categories"))

    category_name = category.name

    # Move all domains to unsortiert (or null)
    Domain.query.filter_by(category_id=category.id).update({"category_id": None})

    db.session.delete(category)
    db.session.commit()

    # Re-export blacklist
    _export_blacklist_to_txt()

    flash(f"Kategorie '{category_name}' gelöscht. Domains wurden zu 'Unsortiert' verschoben.", "success")
    return redirect(url_for("blacklist.categories"))


# ============================================================================
# Helper Functions
# ============================================================================

def _export_blacklist_to_txt():
    """Export blacklist to domain_blacklist.txt after each change."""
    from pathlib import Path
    from flask import current_app

    data_dir = current_app.config["PROJECT_ROOT"] / "data"
    filepath = data_dir / "domain_blacklist.txt"

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
