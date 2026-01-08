"""CollectResult Model.

Tracks individual detail page URLs from search results for better traceability.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class CollectResult(db.Model):
    """Tracks individual detail page URLs from search results."""

    __tablename__ = "collect_result"

    id = db.Column(db.Integer, primary_key=True)
    plz_collector_id = db.Column(
        db.Integer, db.ForeignKey("plz_collector.id"), nullable=False, index=True
    )
    url = db.Column(db.String(500), nullable=False)
    status = db.Column(
        db.String(20), default="pending", index=True
    )  # pending, success, failed, retry
    kanzlei_id = db.Column(
        db.Integer, db.ForeignKey("kanzlei.id"), nullable=True
    )  # NULL wenn nicht gescraped
    steuerberater_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    scraped_at = db.Column(db.DateTime, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    plz_collector = db.relationship("PlzCollector", backref="results")
    kanzlei = db.relationship("Kanzlei", backref="collect_results")

    # Status constants
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_RETRY = "retry"

    MAX_RETRIES = 3

    def __repr__(self) -> str:
        return f"<CollectResult {self.id} [{self.status}] {self.url[:50]}...>"

    @classmethod
    def create_for_urls(cls, plz_collector_id: int, urls: list[str]) -> list["CollectResult"]:
        """Create CollectResult entries for a list of URLs.

        Args:
            plz_collector_id: Foreign key to PlzCollector
            urls: List of detail page URLs

        Returns:
            List of created CollectResult instances
        """
        results = []
        for url in urls:
            # Check if URL already exists for this PLZ
            existing = cls.query.filter_by(
                plz_collector_id=plz_collector_id, url=url
            ).first()
            if existing:
                results.append(existing)
            else:
                result = cls(plz_collector_id=plz_collector_id, url=url)
                db.session.add(result)
                results.append(result)
        db.session.flush()
        return results

    def mark_success(self, kanzlei_id: int, steuerberater_count: int):
        """Mark this result as successfully scraped.

        Args:
            kanzlei_id: ID of the created/updated Kanzlei
            steuerberater_count: Number of Steuerberater created
        """
        self.status = self.STATUS_SUCCESS
        self.kanzlei_id = kanzlei_id
        self.steuerberater_count = steuerberater_count
        self.scraped_at = datetime.utcnow()
        self.error_message = None

    def mark_failed(self, error_message: str):
        """Mark this result as failed.

        Args:
            error_message: Description of the error
        """
        self.retry_count += 1
        if self.retry_count >= self.MAX_RETRIES:
            self.status = self.STATUS_FAILED
        else:
            self.status = self.STATUS_RETRY
        self.error_message = error_message
        self.scraped_at = datetime.utcnow()

    @classmethod
    def get_pending(cls, plz_collector_id: int) -> list["CollectResult"]:
        """Get all pending URLs for a PLZ.

        Args:
            plz_collector_id: Foreign key to PlzCollector

        Returns:
            List of CollectResult with status pending or retry
        """
        return cls.query.filter(
            cls.plz_collector_id == plz_collector_id,
            cls.status.in_([cls.STATUS_PENDING, cls.STATUS_RETRY]),
        ).all()

    @classmethod
    def get_stats(cls, plz_collector_id: int) -> dict[str, int]:
        """Get statistics for a PLZ collector run.

        Args:
            plz_collector_id: Foreign key to PlzCollector

        Returns:
            Dictionary with total, success, failed, pending counts
        """
        total = cls.query.filter_by(plz_collector_id=plz_collector_id).count()
        success = cls.query.filter_by(
            plz_collector_id=plz_collector_id, status=cls.STATUS_SUCCESS
        ).count()
        failed = cls.query.filter_by(
            plz_collector_id=plz_collector_id, status=cls.STATUS_FAILED
        ).count()
        retry = cls.query.filter_by(
            plz_collector_id=plz_collector_id, status=cls.STATUS_RETRY
        ).count()
        pending = cls.query.filter_by(
            plz_collector_id=plz_collector_id, status=cls.STATUS_PENDING
        ).count()

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "retry": retry,
            "pending": pending,
        }
