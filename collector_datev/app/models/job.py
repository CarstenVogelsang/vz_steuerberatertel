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

    # Process tracking (for robust job management)
    pid = db.Column(db.Integer)  # Process ID
    pgid = db.Column(db.Integer)  # Process Group ID
    last_heartbeat = db.Column(db.DateTime)  # Last health check

    # AI Matching Statistics
    ai_requests = db.Column(db.Integer, default=0)
    ai_tokens_input = db.Column(db.Integer, default=0)
    ai_tokens_output = db.Column(db.Integer, default=0)
    ai_cost = db.Column(db.Float, default=0.0)  # USD
    ai_budget_exhausted = db.Column(db.Boolean, default=False)

    # Relationship to log entries
    log_entries = db.relationship(
        "LogEntry",
        backref="job",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # Job types
    JOB_TYPES = [
        ("scraper", "DATEV Collector"),
        ("collector_bstbk", "BStBK Collector"),
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

    @property
    def ai_cost_formatted(self) -> str:
        """Format AI cost as USD string."""
        if self.ai_cost is None or self.ai_cost == 0:
            return "-"
        return f"${self.ai_cost:.4f}"

    @property
    def has_ai_usage(self) -> bool:
        """Check if this job used AI matching."""
        return self.ai_requests > 0

    def add_ai_usage(self, tokens_input: int, tokens_output: int, cost: float):
        """Add AI usage statistics to this job.

        Args:
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens
            cost: Cost in USD
        """
        self.ai_requests = (self.ai_requests or 0) + 1
        self.ai_tokens_input = (self.ai_tokens_input or 0) + tokens_input
        self.ai_tokens_output = (self.ai_tokens_output or 0) + tokens_output
        self.ai_cost = (self.ai_cost or 0.0) + cost

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
            "pid": self.pid,
            "pgid": self.pgid,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "ai_requests": self.ai_requests,
            "ai_tokens_input": self.ai_tokens_input,
            "ai_tokens_output": self.ai_tokens_output,
            "ai_cost": self.ai_cost,
            "ai_cost_formatted": self.ai_cost_formatted,
            "ai_budget_exhausted": self.ai_budget_exhausted,
        }
