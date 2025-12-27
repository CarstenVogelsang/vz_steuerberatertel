"""Job Model for tracking job executions.

Stores information about scraper/enrichment jobs including
status, parameters, timing, and exit codes.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class Job(db.Model):
    """Job execution record."""

    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    parameters = db.Column(db.JSON)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    exit_code = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationship to log entries
    log_entries = db.relationship(
        "LogEntry",
        backref="job",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # Job types
    JOB_TYPES = [
        ("scraper", "DATEV Scraper"),
        ("enrich_email", "Phase 1: E-Mail-Domain"),
        ("enrich_search", "Phase 2: Websuche"),
        ("blacklist_sync", "Blacklist Sync"),
    ]

    # Status values
    STATUSES = [
        ("pending", "Wartend"),
        ("running", "Läuft"),
        ("completed", "Abgeschlossen"),
        ("failed", "Fehlgeschlagen"),
        ("cancelled", "Abgebrochen"),
    ]

    @property
    def duration(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    @property
    def duration_formatted(self) -> str:
        """Format duration as HH:MM:SS."""
        if self.duration is None:
            return "-"
        seconds = int(self.duration)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def __repr__(self) -> str:
        return f"<Job {self.id} {self.job_type} [{self.status}]>"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "parameters": self.parameters,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration": self.duration,
            "duration_formatted": self.duration_formatted,
            "exit_code": self.exit_code,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
