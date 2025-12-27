"""LogEntry Model for job logs.

Stores individual log lines from job executions for
display in the web interface.
"""

from __future__ import annotations

from datetime import datetime

from app import db


class LogEntry(db.Model):
    """Log entry for a job."""

    __tablename__ = "log_entries"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    level = db.Column(db.String(10), nullable=False, default="INFO", index=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Log levels
    LEVELS = [
        ("DEBUG", "Debug"),
        ("INFO", "Info"),
        ("WARNING", "Warnung"),
        ("ERROR", "Fehler"),
        ("SUCCESS", "Erfolg"),
    ]

    def __repr__(self) -> str:
        return f"<LogEntry {self.level}: {self.message[:50]}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "level": self.level,
            "message": self.message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
