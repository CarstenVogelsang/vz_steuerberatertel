"""Flask Application Factory.

Creates and configures the Flask application using the factory pattern.
This allows for multiple instances (testing, development, production).
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy without app (will be bound in create_app)
db = SQLAlchemy()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: Configuration name ('development', 'testing', 'production')
                    If None, uses FLASK_ENV or defaults to 'development'

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    _configure_app(app, config_name)

    # Initialize extensions
    db.init_app(app)

    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)

    # Register blueprints
    _register_blueprints(app)

    # Register CLI commands
    _register_cli_commands(app)

    # Create database tables
    with app.app_context():
        db.create_all()

    # Initialize job management (recovery + heartbeat)
    _init_job_management(app)

    return app


def _init_job_management(app: Flask) -> None:
    """Initialize job management: recover orphaned jobs and start heartbeat.

    Only runs in the main process (not in Flask reloader subprocess).
    """
    from app.services.job_service import JobService

    # Check if we're in the main process (not reloader)
    # In debug mode, Flask runs the reloader which spawns another process
    is_main_process = (
        not app.debug
        or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    )

    if not is_main_process:
        return

    # Recover orphaned jobs from previous server run
    JobService.recover_orphaned_jobs(app)

    # Start heartbeat monitor for job health checks
    JobService.start_heartbeat_monitor(app)


def _configure_app(app: Flask, config_name: str | None) -> None:
    """Configure the Flask application."""
    # Determine configuration
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    # Base configuration
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

    # Database configuration
    db_path = DATA_DIR / "collector.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Environment-specific configuration
    if config_name == "development":
        app.config["DEBUG"] = True
    elif config_name == "testing":
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    elif config_name == "production":
        app.config["DEBUG"] = False
        # In production, SECRET_KEY must be set via environment
        if app.config["SECRET_KEY"] == "dev-secret-key-change-in-production":
            raise ValueError("FLASK_SECRET_KEY must be set in production!")

    # Store project root for subprocess calls
    app.config["PROJECT_ROOT"] = PROJECT_ROOT


def _register_blueprints(app: Flask) -> None:
    """Register Flask blueprints."""
    from app.routes.dashboard import dashboard_bp
    from app.routes.blacklist import blacklist_bp
    from app.routes.jobs import jobs_bp
    from app.routes.api import api_bp
    from app.routes.kanzleien import kanzleien_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(blacklist_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(kanzleien_bp)
    app.register_blueprint(settings_bp)


def _register_cli_commands(app: Flask) -> None:
    """Register Flask CLI commands."""
    from app.commands import register_commands
    register_commands(app)
