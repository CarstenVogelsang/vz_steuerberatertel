"""Kanzleien & Steuerberater Listenansicht.

Read-only view showing all Kanzleien with their associated Steuerberater
in a grouped table format.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app import db
from app.models import Kanzlei, Plz, Steuerberater

kanzleien_bp = Blueprint("kanzleien", __name__, url_prefix="/kanzleien")


@kanzleien_bp.route("/")
def index():
    """Kanzleien & Steuerberater Listenansicht.

    Query Parameters:
        plz: Filter by PLZ prefix (e.g., "475" finds all PLZ starting with 475)
        q: Search in Kanzlei name or Steuerberater name
    """
    plz_filter = request.args.get("plz", "").strip()
    name_filter = request.args.get("q", "").strip()

    query = Kanzlei.query.order_by(Kanzlei.plz, Kanzlei.name)

    if plz_filter:
        query = query.filter(Kanzlei.plz.startswith(plz_filter))

    if name_filter:
        # Search in Kanzlei name OR Steuerberater name
        query = (
            query.outerjoin(Steuerberater)
            .filter(
                db.or_(
                    Kanzlei.name.ilike(f"%{name_filter}%"),
                    Steuerberater.nachname.ilike(f"%{name_filter}%"),
                    Steuerberater.vorname.ilike(f"%{name_filter}%"),
                )
            )
            .distinct()
        )

    kanzleien = query.all()

    # Get available PLZ for autocomplete (only PLZ that have Kanzleien)
    available_plz = (
        db.session.query(Kanzlei.plz)
        .distinct()
        .order_by(Kanzlei.plz)
        .all()
    )
    available_plz = [p[0] for p in available_plz if p[0]]

    return render_template(
        "kanzleien/index.html",
        kanzleien=kanzleien,
        available_plz=available_plz,
        plz_filter=plz_filter,
        name_filter=name_filter,
    )
