"""Kanzlei Model.

Represents tax advisor firms (Steuerberaterkanzleien).
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Kanzlei(db.Model):
    """Steuerberaterkanzlei (tax advisor firm)."""

    __tablename__ = "kanzlei"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    rechtsform_id = db.Column(db.Integer, db.ForeignKey("rechtsform.id"), nullable=True)
    strasse = db.Column(db.String(255))
    plz = db.Column(db.String(5), index=True)
    ort = db.Column(db.String(100))
    telefon = db.Column(db.String(50))
    fax = db.Column(db.String(50))
    email = db.Column(db.String(255))
    website = db.Column(db.String(255))
    kammer_id = db.Column(db.Integer, db.ForeignKey("kammer.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: name + plz
    __table_args__ = (
        db.UniqueConstraint("name", "plz", name="uq_kanzlei_name_plz"),
    )

    # Relationships
    rechtsform = db.relationship("Rechtsform", back_populates="kanzleien")
    kammer = db.relationship("Kammer", back_populates="kanzleien")
    steuerberater = db.relationship(
        "Steuerberater",
        back_populates="kanzlei",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Kanzlei {self.name} ({self.plz} {self.ort})>"

    @classmethod
    def get_or_create(
        cls,
        name: str,
        plz: str,
        ort: str = None,
        strasse: str = None,
        telefon: str = None,
        fax: str = None,
        email: str = None,
        website: str = None,
        rechtsform_id: int = None,
        kammer_id: int = None,
    ) -> tuple["Kanzlei", bool]:
        """Get existing Kanzlei by name+plz or create a new one.

        Args:
            name: Name of the Kanzlei
            plz: Postal code (used for unique constraint)
            ort: City
            strasse: Street address
            telefon: Phone number
            fax: Fax number
            email: Email address (only if Kanzlei-type email)
            website: Website URL
            rechtsform_id: Foreign key to Rechtsform
            kammer_id: Foreign key to Kammer

        Returns:
            Tuple of (Kanzlei instance, created: bool)
        """
        kanzlei = cls.query.filter_by(name=name, plz=plz).first()
        created = False

        if kanzlei is None:
            kanzlei = cls(
                name=name,
                plz=plz,
                ort=ort,
                strasse=strasse,
                telefon=telefon,
                fax=fax,
                email=email,
                website=website,
                rechtsform_id=rechtsform_id,
                kammer_id=kammer_id,
            )
            db.session.add(kanzlei)
            db.session.flush()
            created = True

        return kanzlei, created

    @property
    def full_address(self) -> str:
        """Return full address as string."""
        parts = []
        if self.strasse:
            parts.append(self.strasse)
        if self.plz and self.ort:
            parts.append(f"{self.plz} {self.ort}")
        elif self.plz:
            parts.append(self.plz)
        elif self.ort:
            parts.append(self.ort)
        return ", ".join(parts)
