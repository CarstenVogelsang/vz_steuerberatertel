"""PLZ Collector Model.

Generic PLZ tracking for multiple collector types.
Replaces the specific tracking in the `plz` table for DATEV.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class PlzCollector(db.Model):
    """Generic PLZ tracking for different collector types."""

    __tablename__ = "plz_collector"

    id = db.Column(db.Integer, primary_key=True)
    plz = db.Column(db.String(5), nullable=False, index=True)
    collector_type = db.Column(db.String(20), nullable=False, index=True)  # 'datev' or 'bstbk'
    processed_at = db.Column(db.DateTime, nullable=True)  # NULL = not yet processed
    result_count = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: plz + collector_type
    __table_args__ = (
        db.UniqueConstraint("plz", "collector_type", name="uq_plz_collector_type"),
    )

    def __repr__(self) -> str:
        status = "processed" if self.processed_at else "pending"
        return f"<PlzCollector {self.plz} ({self.collector_type}) - {status}>"

    @property
    def is_processed(self) -> bool:
        """Check if this PLZ has been processed for this collector type."""
        return self.processed_at is not None

    @classmethod
    def get_or_create(cls, plz: str, collector_type: str) -> "PlzCollector":
        """Get or create a PLZ entry for a collector type.

        Args:
            plz: The postal code
            collector_type: The collector type ('datev' or 'bstbk')

        Returns:
            PlzCollector instance
        """
        entry = cls.query.filter_by(plz=plz, collector_type=collector_type).first()

        if not entry:
            entry = cls(plz=plz, collector_type=collector_type)
            db.session.add(entry)
            db.session.flush()

        return entry

    @classmethod
    def get_pending(cls, collector_type: str, plz_filter: str = None, limit: int = None) -> list["PlzCollector"]:
        """Get pending (unprocessed) PLZ entries for a collector type.

        Args:
            collector_type: The collector type ('datev' or 'bstbk')
            plz_filter: Optional PLZ prefix filter (e.g., '4' for all PLZ starting with 4)
            limit: Optional limit on number of results

        Returns:
            List of PlzCollector instances
        """
        query = cls.query.filter(
            cls.collector_type == collector_type,
            cls.processed_at.is_(None),
        )

        if plz_filter:
            query = query.filter(cls.plz.startswith(plz_filter))

        query = query.order_by(cls.plz)

        if limit:
            query = query.limit(limit)

        return query.all()

    @classmethod
    def mark_processed(
        cls,
        plz: str,
        collector_type: str,
        result_count: int = 0,
        error_message: str = None,
    ) -> "PlzCollector":
        """Mark a PLZ as processed for a collector type.

        Args:
            plz: The postal code
            collector_type: The collector type ('datev' or 'bstbk')
            result_count: Number of results found
            error_message: Optional error message

        Returns:
            Updated PlzCollector instance
        """
        entry = cls.query.filter_by(plz=plz, collector_type=collector_type).first()

        if entry:
            entry.processed_at = datetime.utcnow()
            entry.result_count = result_count
            entry.error_message = error_message
        else:
            # Create new entry if it doesn't exist
            entry = cls(
                plz=plz,
                collector_type=collector_type,
                processed_at=datetime.utcnow(),
                result_count=result_count,
                error_message=error_message,
            )
            db.session.add(entry)

        db.session.flush()
        return entry

    @classmethod
    def get_stats(cls, collector_type: str) -> dict[str, int]:
        """Get statistics for a collector type.

        Args:
            collector_type: The collector type ('datev' or 'bstbk')

        Returns:
            Dictionary with total, processed, pending, errors counts
        """
        total = cls.query.filter_by(collector_type=collector_type).count()
        processed = cls.query.filter(
            cls.collector_type == collector_type,
            cls.processed_at.isnot(None),
        ).count()
        errors = cls.query.filter(
            cls.collector_type == collector_type,
            cls.error_message.isnot(None),
        ).count()

        return {
            "total": total,
            "processed": processed,
            "pending": total - processed,
            "errors": errors,
        }

    @classmethod
    def init_from_plz_table(cls, collector_type: str) -> int:
        """Initialize PlzCollector entries from the existing plz table.

        Args:
            collector_type: The collector type to initialize

        Returns:
            Number of entries created
        """
        from app.models import Plz

        # Get all PLZ that don't have an entry for this collector_type
        existing_plz = db.session.query(cls.plz).filter_by(collector_type=collector_type).subquery()
        new_plz = Plz.query.filter(~Plz.plz.in_(db.session.query(existing_plz.c.plz))).all()

        count = 0
        for plz_entry in new_plz:
            entry = cls(plz=plz_entry.plz, collector_type=collector_type)
            db.session.add(entry)
            count += 1

        db.session.flush()
        return count
