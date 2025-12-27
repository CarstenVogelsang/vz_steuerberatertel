"""Category Model for Domain classification.

Stores customizable categories for domain blacklist entries.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Category(db.Model):
    """Domain category for blacklist classification."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default="ghost")  # daisyUI badge color
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to domains
    domains = db.relationship("Domain", back_populates="category_rel", lazy="dynamic")

    # Default daisyUI badge colors
    BADGE_COLORS = [
        ("ghost", "Grau"),
        ("primary", "Blau"),
        ("secondary", "Violett"),
        ("accent", "Cyan"),
        ("info", "Hellblau"),
        ("success", "Grün"),
        ("warning", "Orange"),
        ("error", "Rot"),
    ]

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"

    @property
    def domain_count(self) -> int:
        """Number of domains in this category."""
        return self.domains.count()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "sort_order": self.sort_order,
            "domain_count": self.domain_count,
        }

    @classmethod
    def get_or_create_default(cls) -> "Category":
        """Get or create the 'unsortiert' default category."""
        default = cls.query.filter_by(slug="unsortiert").first()
        if not default:
            default = cls(
                slug="unsortiert",
                name="Unsortiert",
                description="Domains ohne Kategorie",
                color="ghost",
                sort_order=999,
            )
            db.session.add(default)
            db.session.commit()
        return default

    @classmethod
    def seed_defaults(cls) -> int:
        """Create default categories if they don't exist. Returns count created."""
        defaults = [
            ("email-provider", "E-Mail Provider", "Gmail, GMX, Web.de, etc.", "info", 10),
            ("hosting", "Hosting Provider", "Shared Hosting, Cloud Dienste", "warning", 20),
            ("verzeichnis", "Verzeichnisse", "Steuerberater-Verzeichnisse, Portale", "secondary", 30),
            ("social-media", "Social Media", "Facebook, LinkedIn, XING, etc.", "accent", 40),
            ("unsortiert", "Unsortiert", "Domains ohne Kategorie", "ghost", 999),
        ]

        count = 0
        for slug, name, description, color, sort_order in defaults:
            existing = cls.query.filter_by(slug=slug).first()
            if not existing:
                category = cls(
                    slug=slug,
                    name=name,
                    description=description,
                    color=color,
                    sort_order=sort_order,
                )
                db.session.add(category)
                count += 1

        if count > 0:
            db.session.commit()

        return count
