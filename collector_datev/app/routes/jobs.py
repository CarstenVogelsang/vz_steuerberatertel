"""Jobs Blueprint.

Job management and real-time log streaming via SSE.
"""

import time
from html import escape as html_escape

from flask import Blueprint, render_template, Response, stream_with_context

from app import db
from app.models import Job, LogEntry

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@jobs_bp.route("/")
def index():
    """Jobs overview page."""
    # Get running job (if any)
    running_job = Job.query.filter_by(status="running").first()

    # Get recent jobs
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(20).all()

    return render_template(
        "jobs/index.html",
        running_job=running_job,
        recent_jobs=recent_jobs,
        job_types=Job.JOB_TYPES,
    )


@jobs_bp.route("/stream/<int:job_id>")
def stream_logs(job_id: int):
    """SSE endpoint for live log streaming."""

    def generate():
        # CSS classes for log levels (daisyUI)
        level_classes = {
            "INFO": "text-info",
            "SUCCESS": "text-success",
            "WARNING": "text-warning",
            "ERROR": "text-error",
            "DEBUG": "text-base-content/50",
        }

        last_log_id = 0
        heartbeat_counter = 0

        while True:
            job = Job.query.get(job_id)
            if not job:
                html = '<pre data-prefix="!"><code class="text-error">Job nicht gefunden</code></pre>'
                yield f"data: {html}\n\n"
                break

            # Get new log entries
            new_logs = LogEntry.query.filter(
                LogEntry.job_id == job_id,
                LogEntry.id > last_log_id,
            ).order_by(LogEntry.id).all()

            for log in new_logs:
                level_class = level_classes.get(log.level, "")
                timestamp = log.timestamp.strftime("%H:%M:%S")
                message = html_escape(log.message)

                # Send HTML that HTMX can directly insert
                html = f'<pre data-prefix="{timestamp}"><code class="{level_class}">{message}</code></pre>'
                yield f"data: {html}\n\n"
                last_log_id = log.id
                heartbeat_counter = 0  # Reset counter after sending data

            # Check if job is done
            if job.status in ("completed", "failed", "cancelled"):
                # Send final status message
                status_class = "text-success" if job.status == "completed" else "text-error"
                status_text = {"completed": "✓ Abgeschlossen", "failed": "✗ Fehlgeschlagen", "cancelled": "⊘ Abgebrochen"}.get(job.status, job.status)
                html = f'<pre data-prefix="→"><code class="{status_class}">{status_text}</code></pre>'
                yield f"data: {html}\n\n"
                break

            # Heartbeat every 15 seconds (30 * 0.5s) to keep connection alive
            heartbeat_counter += 1
            if heartbeat_counter >= 30:
                yield ": heartbeat\n\n"  # SSE comment = keepalive signal
                heartbeat_counter = 0

            time.sleep(0.5)  # Polling interval

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@jobs_bp.route("/<int:job_id>")
def detail(job_id: int):
    """Job detail page with logs."""
    job = Job.query.get_or_404(job_id)
    logs = LogEntry.query.filter_by(job_id=job_id).order_by(LogEntry.timestamp).all()

    return render_template(
        "jobs/detail.html",
        job=job,
        logs=logs,
    )
