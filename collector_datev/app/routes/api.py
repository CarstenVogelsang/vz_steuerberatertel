"""API Blueprint.

REST endpoints for HTMX interactions and job management.
"""

from flask import Blueprint, jsonify, request

from app import db
from app.models import Domain, Job
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
    success = JobService.cancel_job(job_id)
    if success:
        return jsonify({"message": "Job abgebrochen"}), 200
    return jsonify({"error": "Job konnte nicht abgebrochen werden"}), 400


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
