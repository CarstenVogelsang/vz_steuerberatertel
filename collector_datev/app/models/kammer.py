"""Steuerberaterkammer Model.

Represents the regional tax advisor chambers (Steuerberaterkammern) in Germany.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Kammer(db.Model):
    """Steuerberaterkammer (regional tax advisor chamber)."""

    __tablename__ = "kammer"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    strasse = db.Column(db.String(255))
    plz = db.Column(db.String(5))
    ort = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    kanzleien = db.relationship("Kanzlei", back_populates="kammer", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Kammer {self.name}>"

    @classmethod
    def get_or_create(cls, name: str, strasse: str = None, plz: str = None, ort: str = None) -> "Kammer":
        """Get existing Kammer by name or create a new one.

        Args:
            name: Name of the Kammer (e.g., "Steuerberaterkammer Düsseldorf")
            strasse: Street address
            plz: Postal code
            ort: City

        Returns:
            Kammer instance (existing or newly created)
        """
        kammer = cls.query.filter_by(name=name).first()
        if kammer is None:
            kammer = cls(name=name, strasse=strasse, plz=plz, ort=ort)
            db.session.add(kammer)
            db.session.flush()  # Get ID without committing
        return kammer
