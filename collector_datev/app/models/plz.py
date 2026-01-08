"""PLZ Model for tracking scraping progress.

Stores German postal codes with their processing status,
replacing the previous Excel-based checkpoint system.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Plz(db.Model):
    """PLZ entry for scraping progress tracking."""

    __tablename__ = "plz"

    id = db.Column(db.Integer, primary_key=True)
    plz = db.Column(db.String(5), nullable=False, unique=True, index=True)
    city = db.Column(db.String(100), nullable=False)
    processed_at = db.Column(db.DateTime)  # None = noch nicht verarbeitet
    result_count = db.Column(db.Integer)  # Anzahl gefundener Steuerberater
    error_message = db.Column(db.Text)  # Fehlermeldung falls aufgetreten

    @property
    def is_processed(self) -> bool:
        """Check if this PLZ has been processed."""
        return self.processed_at is not None

    def __repr__(self) -> str:
        status = "✓" if self.is_processed else "○"
        return f"<Plz {self.plz} {self.city} [{status}]>"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "plz": self.plz,
            "city": self.city,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "result_count": self.result_count,
            "error_message": self.error_message,
            "is_processed": self.is_processed,
        }
