"""Rechtsform Model.

Represents legal forms (Rechtsformen) for tax advisor firms.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Rechtsform(db.Model):
    """Rechtsform (legal form) of a Kanzlei."""

    __tablename__ = "rechtsform"

    id = db.Column(db.Integer, primary_key=True)
    kuerzel = db.Column(db.String(50), unique=True, nullable=False, index=True)
    bezeichnung = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    kanzleien = db.relationship("Kanzlei", back_populates="rechtsform", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Rechtsform {self.kuerzel}>"

    @classmethod
    def get_or_create(cls, kuerzel: str, bezeichnung: str = None) -> "Rechtsform":
        """Get existing Rechtsform by kuerzel or create a new one.

        Args:
            kuerzel: Short form (e.g., "GbR", "PartG mbB")
            bezeichnung: Full name of the legal form

        Returns:
            Rechtsform instance (existing or newly created)
        """
        rechtsform = cls.query.filter_by(kuerzel=kuerzel).first()
        if rechtsform is None:
            rechtsform = cls(kuerzel=kuerzel, bezeichnung=bezeichnung)
            db.session.add(rechtsform)
            db.session.flush()
        return rechtsform

    @classmethod
    def seed_defaults(cls) -> int:
        """Create default Rechtsformen if they don't exist.

        Returns:
            Number of Rechtsformen created
        """
        count = 0
        for kuerzel, bezeichnung in RECHTSFORMEN_SEED:
            existing = cls.query.filter_by(kuerzel=kuerzel).first()
            if not existing:
                rechtsform = cls(kuerzel=kuerzel, bezeichnung=bezeichnung)
                db.session.add(rechtsform)
                count += 1
        db.session.commit()
        return count


# Seed data for common legal forms
RECHTSFORMEN_SEED = [
    ("Einzelunternehmen", "Einzelunternehmen"),
    ("GbR", "Gesellschaft bürgerlichen Rechts"),
    ("PartG", "Partnerschaftsgesellschaft"),
    ("PartG mbB", "Partnerschaftsgesellschaft mit beschränkter Berufshaftung"),
    ("GmbH", "Gesellschaft mit beschränkter Haftung"),
    ("UG", "Unternehmergesellschaft (haftungsbeschränkt)"),
    ("AG", "Aktiengesellschaft"),
    ("KG", "Kommanditgesellschaft"),
    ("OHG", "Offene Handelsgesellschaft"),
    ("e.K.", "eingetragener Kaufmann"),
]
