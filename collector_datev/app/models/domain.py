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
    category = db.Column(db.String(50), default="unsortiert", index=True)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), default="system")

    # Valid categories
    CATEGORIES = [
        ("email-provider", "E-Mail Provider"),
        ("hosting", "Hosting Provider"),
        ("verzeichnis", "Steuerberater-Verzeichnisse"),
        ("unsortiert", "Unsortiert"),
    ]

    def __repr__(self) -> str:
        return f"<Domain {self.domain}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "domain": self.domain,
            "category": self.category,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }
