"""Steuerberater Model.

Represents individual tax advisors (Steuerberater).
"""

from __future__ import annotations

from datetime import datetime, date

from app import db


class Steuerberater(db.Model):
    """Steuerberater (tax advisor - natural person)."""

    __tablename__ = "steuerberater"

    id = db.Column(db.Integer, primary_key=True)
    safe_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    titel = db.Column(db.String(50))  # "Steuerberater" / "Steuerberaterin"
    vorname = db.Column(db.String(100))
    nachname = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(255))
    mobil = db.Column(db.String(50))
    bestelldatum = db.Column(db.Date)  # Date when appointed as Steuerberater
    kanzlei_id = db.Column(db.Integer, db.ForeignKey("kanzlei.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    kanzlei = db.relationship("Kanzlei", back_populates="steuerberater")

    def __repr__(self) -> str:
        name = f"{self.vorname} {self.nachname}" if self.vorname else self.nachname
        return f"<Steuerberater {name}>"

    @property
    def full_name(self) -> str:
        """Return full name as string."""
        if self.vorname:
            return f"{self.vorname} {self.nachname}"
        return self.nachname

    @classmethod
    def get_by_safe_id(cls, safe_id: str) -> "Steuerberater | None":
        """Get Steuerberater by Safe ID.

        Args:
            safe_id: The BStBK Safe ID (e.g., "DE.BStBK.xxx.xxx")

        Returns:
            Steuerberater instance or None
        """
        if not safe_id:
            return None
        return cls.query.filter_by(safe_id=safe_id).first()

    @classmethod
    def create_or_update(
        cls,
        safe_id: str | None,
        nachname: str,
        kanzlei_id: int,
        vorname: str = None,
        titel: str = None,
        email: str = None,
        mobil: str = None,
        bestelldatum: date = None,
    ) -> tuple["Steuerberater", bool]:
        """Create new Steuerberater or update existing by Safe ID.

        If safe_id is provided and exists, updates the record.
        Otherwise, creates a new record.

        Args:
            safe_id: BStBK Safe ID (unique identifier)
            nachname: Last name
            kanzlei_id: Foreign key to Kanzlei
            vorname: First name
            titel: Title (Steuerberater/Steuerberaterin)
            email: Personal email address
            mobil: Mobile phone number
            bestelldatum: Date of appointment

        Returns:
            Tuple of (Steuerberater instance, created: bool)
        """
        steuerberater = None
        created = False

        # Try to find by Safe ID if provided
        if safe_id:
            steuerberater = cls.get_by_safe_id(safe_id)

        if steuerberater:
            # Update existing record
            steuerberater.nachname = nachname
            steuerberater.vorname = vorname
            steuerberater.titel = titel
            steuerberater.kanzlei_id = kanzlei_id
            if email:
                steuerberater.email = email
            if mobil:
                steuerberater.mobil = mobil
            if bestelldatum:
                steuerberater.bestelldatum = bestelldatum
        else:
            # Create new record
            steuerberater = cls(
                safe_id=safe_id,
                nachname=nachname,
                vorname=vorname,
                titel=titel,
                email=email,
                mobil=mobil,
                bestelldatum=bestelldatum,
                kanzlei_id=kanzlei_id,
            )
            db.session.add(steuerberater)
            created = True

        db.session.flush()
        return steuerberater, created
