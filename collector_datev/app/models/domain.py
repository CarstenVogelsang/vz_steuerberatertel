"""Domain Model for Blacklist entries.

Stores domains that should be excluded from website enrichment
(e.g., email providers like gmail.com, hosting providers, etc.)
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Domain(db.Model):
    """Blacklist domain entry."""

    __tablename__ = "domains"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), default="system")

    # Relationship to category
    category_rel = db.relationship("Category", back_populates="domains")

    def __repr__(self) -> str:
        return f"<Domain {self.domain}>"

    @property
    def category_name(self) -> str:
        """Get category name or 'Unsortiert' if no category."""
        return self.category_rel.name if self.category_rel else "Unsortiert"

    @property
    def category_slug(self) -> str:
        """Get category slug or 'unsortiert' if no category."""
        return self.category_rel.slug if self.category_rel else "unsortiert"

    @property
    def category_color(self) -> str:
        """Get category badge color."""
        return self.category_rel.color if self.category_rel else "ghost"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "domain": self.domain,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "category_slug": self.category_slug,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }
