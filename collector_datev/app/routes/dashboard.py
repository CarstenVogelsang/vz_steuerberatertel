"""Dashboard Blueprint.

Main landing page with statistics and status overview.
"""

from flask import Blueprint, render_template

from app import db
from app.models import Domain, Job

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Dashboard home page with statistics."""
    # Get statistics
    stats = {
        "blacklist_count": Domain.query.count(),
        "jobs_total": Job.query.count(),
        "jobs_completed": Job.query.filter_by(status="completed").count(),
        "jobs_failed": Job.query.filter_by(status="failed").count(),
    }

    # Get running job (if any)
    running_job = Job.query.filter_by(status="running").first()

    # Get recent jobs
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard/index.html",
        stats=stats,
        running_job=running_job,
        recent_jobs=recent_jobs,
    )
