"""Job Service.

Manages subprocess execution for CLI tools with log streaming.
"""

from __future__ import annotations

import os
import signal
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

                # Start process with own process group (for clean termination)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line-buffered
                    cwd=str(app.config["PROJECT_ROOT"]),
                    preexec_fn=os.setsid,  # Eigene Prozessgruppe für Child-Prozesse
                )
                cls._processes[job_id] = process

                # Read output line by line with process status check
                # This is more robust for asyncio processes like Playwright
                while True:
                    line = process.stdout.readline()
                    if line:
                        line = line.rstrip()
                        if line:
                            level = cls._parse_log_level(line)
                            cls._add_log(job_id, level, line)
                    elif process.poll() is not None:
                        # Process has terminated and no more output
                        break

                # Wait for process to complete (should be instant now)
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
            # Scraper CLI is in main.py - now uses SQLite for progress tracking
            cmd = ["uv", "run", "python", "main.py"]
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

        elif job_type == "collector_bstbk":
            # BStBK Collector - Bundessteuerberaterkammer Steuerberaterverzeichnis
            cmd = ["uv", "run", "python", "main_bstbk.py"]
            if parameters.get("plz_filter"):
                cmd.extend(["--plz-filter", str(parameters["plz_filter"])])
            if parameters.get("headless"):
                cmd.append("--headless")
            if parameters.get("max_plz"):
                cmd.extend(["--max-plz", str(parameters["max_plz"])])
            if parameters.get("dry_run"):
                cmd.append("--dry-run")
            # Note: force_rescrape is handled in api.py (reset before job starts)
            # but we still pass --force for direct CLI invocation awareness
            if parameters.get("force_rescrape"):
                cmd.append("--force")
            if parameters.get("update_mode"):
                cmd.extend(["--update-mode", str(parameters["update_mode"])])

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
        """Cancel a running job with robust termination.

        Tries SIGTERM first, then SIGKILL if process doesn't respond.
        Also kills entire process group to handle child processes (Playwright/Chromium).

        Returns:
            True if job was cancelled, False otherwise
        """
        process = cls._processes.get(job_id)
        if not process:
            return False

        try:
            # Versuche sanften Abbruch (SIGTERM) auf Prozessgruppe
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                # Prozess existiert nicht mehr oder keine Berechtigung
                process.terminate()

            # Warte max 5 Sekunden auf Beendigung
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # SIGTERM hat nicht funktioniert → SIGKILL
                cls._add_log(job_id, "WARNING", "Prozess reagiert nicht, erzwinge Beendigung...")
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    process.kill()
                process.wait(timeout=5)

        except Exception as e:
            # Letzter Fallback
            cls._add_log(job_id, "ERROR", f"Fehler beim Beenden: {e}")
            try:
                process.kill()
            except Exception:
                pass

        # Status aktualisieren
        job = Job.query.get(job_id)
        if job:
            job.status = "cancelled"
            job.finished_at = datetime.utcnow()
            db.session.commit()
            cls._add_log(job_id, "WARNING", "Job wurde abgebrochen")

        cls._processes.pop(job_id, None)
        return True

    @classmethod
    def get_running_job(cls) -> Job | None:
        """Get the currently running job (max 1)."""
        return Job.query.filter_by(status="running").first()

    @classmethod
    def get_recent_jobs(cls, limit: int = 10) -> list[Job]:
        """Get recent jobs."""
        return Job.query.order_by(Job.created_at.desc()).limit(limit).all()
