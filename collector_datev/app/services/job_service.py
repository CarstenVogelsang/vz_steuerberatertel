"""Job Service.

Manages subprocess execution for CLI tools with log streaming.
"""

from __future__ import annotations

import subprocess
import threading
from datetime import datetime

from flask import current_app

from app import db
from app.models import Job, LogEntry


class JobService:
    """Service for managing job execution."""

    # Active processes: job_id -> subprocess.Popen
    _processes: dict[int, subprocess.Popen] = {}

    @classmethod
    def start_job(cls, job_type: str, parameters: dict) -> Job:
        """Start a new job as subprocess.

        Args:
            job_type: Type of job (scraper, enrich_email, enrich_search)
            parameters: Job parameters

        Returns:
            Created Job instance
        """
        job = Job(
            job_type=job_type,
            status="pending",
            parameters=parameters,
        )
        db.session.add(job)
        db.session.commit()

        # Start subprocess in background thread
        # We need to capture the app for the thread context
        app = current_app._get_current_object()

        thread = threading.Thread(
            target=cls._run_subprocess,
            args=(app, job.id, job_type, parameters),
            daemon=True,
        )
        thread.start()

        return job

    @classmethod
    def _run_subprocess(cls, app, job_id: int, job_type: str, parameters: dict):
        """Execute the subprocess and capture logs.

        This runs in a background thread.
        """
        with app.app_context():
            job = Job.query.get(job_id)
            if not job:
                return

            job.status = "running"
            job.started_at = datetime.utcnow()
            db.session.commit()

            try:
                # Build command
                cmd = cls._build_command(job_type, parameters, app.config["PROJECT_ROOT"])

                # Add initial log entry
                cls._add_log(job_id, "INFO", f"Starte Job: {' '.join(cmd)}")

                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line-buffered
                    cwd=str(app.config["PROJECT_ROOT"]),
                )
                cls._processes[job_id] = process

                # Read output line by line
                for line in iter(process.stdout.readline, ""):
                    line = line.rstrip()
                    if line:
                        level = cls._parse_log_level(line)
                        cls._add_log(job_id, level, line)

                # Wait for process to complete
                process.wait()
                exit_code = process.returncode

                # Update job status
                job = Job.query.get(job_id)
                job.status = "completed" if exit_code == 0 else "failed"
                job.exit_code = exit_code
                job.finished_at = datetime.utcnow()

                # Add final log entry
                if exit_code == 0:
                    cls._add_log(job_id, "SUCCESS", "Job erfolgreich abgeschlossen")
                else:
                    cls._add_log(job_id, "ERROR", f"Job fehlgeschlagen (Exit-Code: {exit_code})")

            except Exception as e:
                job = Job.query.get(job_id)
                job.status = "failed"
                job.error_message = str(e)
                job.finished_at = datetime.utcnow()
                cls._add_log(job_id, "ERROR", f"Exception: {e}")

            finally:
                cls._processes.pop(job_id, None)
                db.session.commit()

    @classmethod
    def _build_command(cls, job_type: str, parameters: dict, project_root) -> list[str]:
        """Build CLI command from job type and parameters."""
        # Use uv run for proper virtual environment handling
        base_cmd = ["uv", "run", "python", "-m"]

        if job_type == "scraper":
            cmd = base_cmd + ["src.scraper"]
            if parameters.get("plz_filter"):
                cmd.extend(["--plz-filter", str(parameters["plz_filter"])])
            if parameters.get("headless"):
                cmd.append("--headless")

        elif job_type == "enrich_email":
            cmd = base_cmd + ["src.enrich_from_email"]
            if parameters.get("plz_filter"):
                cmd.extend(["--plz-filter", str(parameters["plz_filter"])])
            if parameters.get("dry_run"):
                cmd.append("--dry-run")

        elif job_type == "enrich_search":
            cmd = base_cmd + ["src.enrich_from_search"]
            if parameters.get("plz_filter"):
                cmd.extend(["--plz-filter", str(parameters["plz_filter"])])
            if parameters.get("confidence_filter"):
                for cf in parameters["confidence_filter"]:
                    cmd.extend(["--confidence-filter", cf])
            if parameters.get("search_provider"):
                cmd.extend(["--search-provider", parameters["search_provider"]])
            if parameters.get("headless"):
                cmd.append("--headless")
            if parameters.get("dry_run"):
                cmd.append("--dry-run")

        else:
            raise ValueError(f"Unbekannter Job-Typ: {job_type}")

        return cmd

    @classmethod
    def _parse_log_level(cls, line: str) -> str:
        """Extract log level from log line."""
        line_upper = line.upper()
        if "ERROR" in line_upper:
            return "ERROR"
        elif "WARNING" in line_upper or "WARN" in line_upper:
            return "WARNING"
        elif "SUCCESS" in line_upper:
            return "SUCCESS"
        elif "DEBUG" in line_upper:
            return "DEBUG"
        return "INFO"

    @classmethod
    def _add_log(cls, job_id: int, level: str, message: str):
        """Add a log entry for a job."""
        log_entry = LogEntry(
            job_id=job_id,
            level=level,
            message=message,
        )
        db.session.add(log_entry)
        db.session.commit()

    @classmethod
    def cancel_job(cls, job_id: int) -> bool:
        """Cancel a running job.

        Returns:
            True if job was cancelled, False otherwise
        """
        process = cls._processes.get(job_id)
        if process:
            process.terminate()
            job = Job.query.get(job_id)
            if job:
                job.status = "cancelled"
                job.finished_at = datetime.utcnow()
                db.session.commit()
                cls._add_log(job_id, "WARNING", "Job wurde abgebrochen")
            return True
        return False

    @classmethod
    def get_running_job(cls) -> Job | None:
        """Get the currently running job (max 1)."""
        return Job.query.filter_by(status="running").first()

    @classmethod
    def get_recent_jobs(cls, limit: int = 10) -> list[Job]:
        """Get recent jobs."""
        return Job.query.order_by(Job.created_at.desc()).limit(limit).all()
