"""PLZ Handler - SQLite-based progress tracking.

Replaces the previous Excel-based checkpoint system (excel_handler.py)
with SQLite database queries for better reliability and performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app import db
from app.models import Plz

from .plz_filter import PlzFilter


@dataclass
class PlzEntry:
    """Represents a single PLZ entry from the database."""

    row_number: int  # Actually the database ID, kept for compatibility
    plz: str
    city: str


@dataclass
class LocationGroup:
    """A group of PLZ entries for the same city."""

    city: str
    entries: list[PlzEntry]


def load_pending_locations(plz_filter: PlzFilter | None = None) -> list[LocationGroup]:
    """Load all unprocessed PLZ entries grouped by city.

    Only returns entries where processed_at is NULL.

    Args:
        plz_filter: If specified, only load PLZ matching the filter
    """
    query = Plz.query.filter(Plz.processed_at.is_(None))

    # Apply PLZ filter
    if plz_filter is not None:
        if plz_filter.prefix:
            query = query.filter(Plz.plz.startswith(plz_filter.prefix))
        elif plz_filter.range_start and plz_filter.range_end:
            query = query.filter(
                Plz.plz >= plz_filter.range_start,
                Plz.plz <= plz_filter.range_end,
            )

    entries = query.order_by(Plz.plz).all()

    # Group by city
    city_groups: dict[str, list[PlzEntry]] = {}
    for entry in entries:
        if entry.city not in city_groups:
            city_groups[entry.city] = []
        city_groups[entry.city].append(
            PlzEntry(row_number=entry.id, plz=entry.plz, city=entry.city)
        )

    return [LocationGroup(city=city, entries=entries) for city, entries in city_groups.items()]


def update_plz_status(
    plz_id: int,
    count: int,
    error: str | None = None,
) -> None:
    """Update the status for a PLZ entry.

    Args:
        plz_id: The database ID of the PLZ entry
        count: Number of Steuerberater found
        error: Error message if any
    """
    entry = db.session.get(Plz, plz_id)
    if entry:
        entry.processed_at = datetime.utcnow()
        entry.result_count = count
        entry.error_message = error
        db.session.commit()


def get_progress_stats() -> dict[str, int]:
    """Get statistics about processing progress."""
    total = Plz.query.count()
    processed = Plz.query.filter(Plz.processed_at.isnot(None)).count()
    errors = Plz.query.filter(Plz.error_message.isnot(None)).count()

    return {
        "total": total,
        "processed": processed,
        "pending": total - processed,
        "errors": errors,
    }
