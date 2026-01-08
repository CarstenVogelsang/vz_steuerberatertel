"""Job Service.

Manages subprocess execution for CLI tools with log streaming.
Includes robust process management, batch logging, and heartbeat monitoring.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from datetime import datetime

from flask import current_app, Flask

from app import db
from app.models import Job, LogEntry


def process_exists(pid: int) -> bool:
    """Check if a process with given PID exists.

    Args:
        pid: Process ID to check

    Returns:
        True if process exists, False otherwise
    """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)  # Signal 0 = just check
        return True
    except (OSError, ProcessLookupError):
        return False


class JobService:
    """Service for managing job execution."""

    # Active processes: job_id -> subprocess.Popen
    _processes: dict[int, subprocess.Popen] = {}

    # Batch logging
    _log_buffer: dict[int, list[LogEntry]] = {}
    _log_lock = threading.Lock()
    LOG_BUFFER_SIZE = 10  # Flush after N logs
    LOG_FLUSH_INTERVAL = 2.0  # Or after N seconds

    # Heartbeat monitoring
    _heartbeat_thread: threading.Thread | None = None
    _heartbeat_running = False
    HEARTBEAT_INTERVAL = 30  # Check every 30 seconds

    # ========================================================================
    # Job Lifecycle
    # ========================================================================

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
                    preexec_fn=os.setsid,  # Own process group for child processes
                )
                cls._processes[job_id] = process

                # Store PID in database for recovery after restart
                job = Job.query.get(job_id)
                job.pid = process.pid
                job.pgid = os.getpgid(process.pid)
                job.last_heartbeat = datetime.utcnow()
                db.session.commit()

                cls._add_log(job_id, "DEBUG", f"Prozess gestartet: PID={process.pid}, PGID={job.pgid}")

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
                job.pid = None  # Clear PID after completion
                job.pgid = None

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
                job.pid = None
                job.pgid = None
                cls._add_log(job_id, "ERROR", f"Exception: {e}")

            finally:
                cls._flush_logs(job_id)  # Flush remaining logs
                cls._processes.pop(job_id, None)
                db.session.commit()

    @classmethod
    def cancel_job(cls, job_id: int) -> bool:
        """Cancel a running job with robust termination.

        Tries SIGTERM first, then SIGKILL if process doesn't respond.
        Also kills entire process group to handle child processes (Playwright/Chromium).
        Falls back to PID from database if process object is not available (after restart).

        Returns:
            True if job was cancelled, False otherwise
        """
        job = Job.query.get(job_id)
        if not job:
            return False

        # Try process object first (in-memory)
        process = cls._processes.get(job_id)
        killed = False

        if process:
            # Process object available → use it for termination
            try:
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    process.terminate()

                try:
                    process.wait(timeout=5)
                    killed = True
                except subprocess.TimeoutExpired:
                    cls._add_log(job_id, "WARNING", "Prozess reagiert nicht, erzwinge Beendigung...")
                    try:
                        pgid = os.getpgid(process.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        process.kill()
                    process.wait(timeout=5)
                    killed = True

            except Exception as e:
                cls._add_log(job_id, "ERROR", f"Fehler beim Beenden: {e}")
                try:
                    process.kill()
                    killed = True
                except Exception:
                    pass

        elif job.pid:
            # Fallback: Use PID from database (after server restart)
            cls._add_log(job_id, "INFO", f"Verwende PID aus DB: {job.pid}")
            try:
                pgid = job.pgid or os.getpgid(job.pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(5)

                if process_exists(job.pid):
                    os.killpg(pgid, signal.SIGKILL)
                    time.sleep(1)

                killed = not process_exists(job.pid)

            except (ProcessLookupError, OSError) as e:
                # Process doesn't exist anymore
                cls._add_log(job_id, "INFO", f"Prozess existiert nicht mehr: {e}")
                killed = True

        else:
            # No process object and no PID
            cls._add_log(job_id, "WARNING", "Weder Prozess-Objekt noch PID verfügbar")
            # Mark as cancelled anyway since we can't do anything else
            killed = True

        # Update job status
        job.status = "cancelled"
        job.finished_at = datetime.utcnow()
        job.pid = None
        job.pgid = None
        db.session.commit()

        cls._add_log(job_id, "WARNING", "Job wurde abgebrochen")
        cls._flush_logs(job_id)
        cls._processes.pop(job_id, None)

        return killed

    # ========================================================================
    # Batch Logging
    # ========================================================================

    @classmethod
    def _add_log(cls, job_id: int, level: str, message: str):
        """Add a log entry for a job (buffered).

        Logs are batched for performance and flushed when:
        - Buffer reaches LOG_BUFFER_SIZE
        - Level is ERROR or SUCCESS
        - Job completes
        """
        log_entry = LogEntry(
            job_id=job_id,
            level=level,
            message=message,
        )

        with cls._log_lock:
            if job_id not in cls._log_buffer:
                cls._log_buffer[job_id] = []

            cls._log_buffer[job_id].append(log_entry)

            # Flush on buffer size or important levels
            should_flush = (
                len(cls._log_buffer[job_id]) >= cls.LOG_BUFFER_SIZE
                or level in ("ERROR", "SUCCESS", "WARNING")
            )

            if should_flush:
                cls._flush_logs_unlocked(job_id)

    @classmethod
    def _flush_logs(cls, job_id: int):
        """Flush buffered logs to database (with lock)."""
        with cls._log_lock:
            cls._flush_logs_unlocked(job_id)

    @classmethod
    def _flush_logs_unlocked(cls, job_id: int):
        """Flush buffered logs to database (without lock - caller must hold lock)."""
        if job_id not in cls._log_buffer or not cls._log_buffer[job_id]:
            return

        for log_entry in cls._log_buffer[job_id]:
            db.session.add(log_entry)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        cls._log_buffer[job_id] = []

    @classmethod
    def _flush_all_logs(cls):
        """Flush all buffered logs (for shutdown)."""
        with cls._log_lock:
            for job_id in list(cls._log_buffer.keys()):
                cls._flush_logs_unlocked(job_id)

    # ========================================================================
    # Heartbeat Monitor
    # ========================================================================

    @classmethod
    def start_heartbeat_monitor(cls, app: Flask):
        """Start background thread to monitor job health.

        Checks every HEARTBEAT_INTERVAL seconds if running jobs are still alive.
        Marks jobs as failed if their process has died.

        Args:
            app: Flask application instance
        """
        if cls._heartbeat_thread and cls._heartbeat_thread.is_alive():
            return  # Already running

        cls._heartbeat_running = True

        def monitor():
            while cls._heartbeat_running:
                time.sleep(cls.HEARTBEAT_INTERVAL)

                with app.app_context():
                    try:
                        cls._check_job_health()
                    except Exception as e:
                        app.logger.error(f"Heartbeat error: {e}")

        cls._heartbeat_thread = threading.Thread(target=monitor, daemon=True, name="job-heartbeat")
        cls._heartbeat_thread.start()
        app.logger.info("Job heartbeat monitor started")

    @classmethod
    def stop_heartbeat_monitor(cls):
        """Stop the heartbeat monitor."""
        cls._heartbeat_running = False

    @classmethod
    def _check_job_health(cls):
        """Check if running jobs are still alive.

        Called periodically by heartbeat monitor.
        """
        running_jobs = Job.query.filter_by(status="running").all()

        for job in running_jobs:
            if job.pid and not process_exists(job.pid):
                # Process is gone → mark as failed
                job.status = "failed"
                job.error_message = "Prozess unerwartet beendet"
                job.finished_at = datetime.utcnow()
                job.pid = None
                job.pgid = None

                cls._add_log(job.id, "ERROR", "Heartbeat: Prozess nicht mehr gefunden")
                cls._flush_logs(job.id)
                cls._processes.pop(job.id, None)

            elif job.pid:
                # Process still running → update heartbeat
                job.last_heartbeat = datetime.utcnow()

        db.session.commit()

    # ========================================================================
    # Startup Recovery
    # ========================================================================

    @classmethod
    def recover_orphaned_jobs(cls, app: Flask):
        """Recover orphaned jobs after server restart.

        Jobs that were running when the server stopped are either:
        - Killed and marked as cancelled (if process still exists)
        - Marked as failed (if process no longer exists)

        Args:
            app: Flask application instance
        """
        with app.app_context():
            running_jobs = Job.query.filter_by(status="running").all()

            recovered_count = 0
            for job in running_jobs:
                recovered_count += 1

                if job.pid and process_exists(job.pid):
                    # Process still running but we lost control → kill it
                    try:
                        pgid = job.pgid or os.getpgid(job.pid)
                        os.killpg(pgid, signal.SIGTERM)
                        time.sleep(2)
                        if process_exists(job.pid):
                            os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass

                    job.status = "cancelled"
                    job.error_message = "Nach Server-Restart abgebrochen"
                else:
                    # Process doesn't exist anymore
                    job.status = "failed"
                    job.error_message = "Prozess nach Restart nicht gefunden"

                job.finished_at = datetime.utcnow()
                job.pid = None
                job.pgid = None

            db.session.commit()

            if recovered_count > 0:
                app.logger.warning(f"Recovered {recovered_count} orphaned job(s)")

    # ========================================================================
    # Command Builder
    # ========================================================================

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

    # ========================================================================
    # Query Methods
    # ========================================================================

    @classmethod
    def get_running_job(cls) -> Job | None:
        """Get the currently running job (max 1)."""
        return Job.query.filter_by(status="running").first()

    @classmethod
    def get_recent_jobs(cls, limit: int = 10) -> list[Job]:
        """Get recent jobs."""
        return Job.query.order_by(Job.created_at.desc()).limit(limit).all()
