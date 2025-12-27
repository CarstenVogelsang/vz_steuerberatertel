"""Jobs Blueprint.

Job management and real-time log streaming via SSE.
"""

import json
import time

from flask import Blueprint, render_template, request, Response, stream_with_context

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
        last_log_id = 0
        while True:
            job = Job.query.get(job_id)
            if not job:
                yield f"event: error\ndata: Job nicht gefunden\n\n"
                break

            # Get new log entries
            new_logs = LogEntry.query.filter(
                LogEntry.job_id == job_id,
                LogEntry.id > last_log_id,
            ).order_by(LogEntry.id).all()

            for log in new_logs:
                data = {
                    "id": log.id,
                    "level": log.level,
                    "message": log.message,
                    "timestamp": log.timestamp.strftime("%H:%M:%S"),
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_log_id = log.id

            # Check if job is done
            if job.status in ("completed", "failed", "cancelled"):
                yield f"event: done\ndata: {job.status}\n\n"
                break

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
