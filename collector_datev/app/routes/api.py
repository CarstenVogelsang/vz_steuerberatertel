"""API Blueprint.

REST endpoints for HTMX interactions and job management.
"""

from flask import Blueprint, jsonify, request

from app import db
from app.models import Domain, Job, PlzCollector
from app.services.job_service import JobService

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/jobs", methods=["POST"])
def create_job():
    """Start a new job."""
    # Check if a job is already running
    running_job = Job.query.filter_by(status="running").first()
    if running_job:
        return jsonify({
            "error": "Es läuft bereits ein Job",
            "running_job": running_job.to_dict(),
        }), 409

    data = request.get_json()
    job_type = data.get("job_type")
    parameters = data.get("parameters", {})

    if not job_type:
        return jsonify({"error": "job_type ist erforderlich"}), 400

    # Handle force_rescrape: Reset PLZ tracking for the filter
    if parameters.get("force_rescrape"):
        plz_filter = parameters.get("plz_filter", "")
        # Map job_type to collector_type
        collector_type = "bstbk" if job_type == "collector_bstbk" else "datev"
        reset_count = PlzCollector.reset_for_filter(plz_filter, collector_type)
        # Add reset info to parameters for logging
        parameters["_reset_count"] = reset_count

    # Start the job
    job = JobService.start_job(job_type, parameters)

    return jsonify(job.to_dict()), 201


@api_bp.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id: int):
    """Get job details."""
    job = Job.query.get_or_404(job_id)
    return jsonify(job.to_dict())


@api_bp.route("/jobs/<int:job_id>", methods=["DELETE"])
def cancel_job(job_id: int):
    """Cancel a running job."""
    job = Job.query.get_or_404(job_id)

    # Prüfen ob Job überhaupt läuft
    if job.status != "running":
        return jsonify({"error": f"Job läuft nicht (Status: {job.status})"}), 400

    success = JobService.cancel_job(job_id)
    if success:
        return jsonify({"message": "Job abgebrochen", "job_id": job_id}), 200
    return jsonify({"error": "Job konnte nicht abgebrochen werden"}), 400


@api_bp.route("/jobs/<int:job_id>/restart", methods=["POST"])
def restart_job(job_id: int):
    """Restart a failed or cancelled job with original parameters.

    The Excel checkpoint system ensures that already processed PLZ are skipped,
    so the job automatically continues where it left off.
    """
    job = Job.query.get_or_404(job_id)

    # Only failed or cancelled jobs can be restarted
    if job.status not in ("failed", "cancelled"):
        return jsonify({
            "error": "Nur fehlgeschlagene oder abgebrochene Jobs können neu gestartet werden"
        }), 400

    # Check if a job is already running
    if JobService.get_running_job():
        return jsonify({"error": "Es läuft bereits ein Job"}), 409

    # Start new job with same parameters
    new_job = JobService.start_job(job.job_type, job.parameters or {})

    return jsonify(new_job.to_dict()), 201


@api_bp.route("/jobs/plz-status", methods=["GET"])
def get_plz_status():
    """Get PLZ processing status for a filter.

    Query params:
        filter: PLZ prefix filter (e.g., '4' for PLZ 40000-49999)
        collector: Collector type ('datev' or 'bstbk'), defaults to 'bstbk'
    """
    plz_filter = request.args.get("filter", "")
    collector_type = request.args.get("collector", "bstbk")

    status = PlzCollector.get_status_for_filter(plz_filter, collector_type)
    return jsonify(status)


@api_bp.route("/jobs/<int:job_id>/logs", methods=["GET"])
def get_job_logs(job_id: int):
    """Get all logs for a job."""
    from app.models import LogEntry

    job = Job.query.get_or_404(job_id)
    logs = LogEntry.query.filter_by(job_id=job_id).order_by(LogEntry.timestamp).all()

    return jsonify({
        "job": job.to_dict(),
        "logs": [log.to_dict() for log in logs],
    })


@api_bp.route("/domains", methods=["GET"])
def list_domains():
    """List all blacklisted domains."""
    domains = Domain.query.order_by(Domain.category, Domain.domain).all()
    return jsonify([d.to_dict() for d in domains])


@api_bp.route("/domains", methods=["POST"])
def add_domain():
    """Add a domain to blacklist."""
    data = request.get_json()
    domain = data.get("domain", "").strip().lower()

    if not domain:
        return jsonify({"error": "domain ist erforderlich"}), 400

    existing = Domain.query.filter_by(domain=domain).first()
    if existing:
        return jsonify({"error": f"Domain '{domain}' existiert bereits"}), 409

    new_domain = Domain(
        domain=domain,
        category=data.get("category", "unsortiert"),
        reason=data.get("reason", ""),
        created_by="api",
    )
    db.session.add(new_domain)
    db.session.commit()

    return jsonify(new_domain.to_dict()), 201


@api_bp.route("/domains/<int:domain_id>", methods=["DELETE"])
def delete_domain(domain_id: int):
    """Delete a domain from blacklist."""
    domain = Domain.query.get_or_404(domain_id)
    db.session.delete(domain)
    db.session.commit()
    return jsonify({"message": "Domain gelöscht"}), 200


# ============================================================================
# Reset Endpoints
# ============================================================================


@api_bp.route("/reset/stats", methods=["GET"])
def get_reset_stats():
    """Get current data statistics for reset confirmation."""
    from app.services.reset_service import ResetService

    stats = ResetService.get_stats()
    return jsonify(stats)


@api_bp.route("/reset/full", methods=["POST"])
def full_reset():
    """Perform a full reset of BStBK collector data.

    Request body:
        archive: bool - If true, create backup before reset
    """
    from app.services.reset_service import ResetService

    data = request.get_json() or {}
    archive = data.get("archive", False)

    try:
        result = ResetService.full_reset(archive=archive)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
