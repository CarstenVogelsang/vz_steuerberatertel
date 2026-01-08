"""Settings Route for AI Configuration.

Provides UI for configuring OpenRouter API settings including
API key, model selection, and budget management.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import db
from app.models import AIConfig, AVAILABLE_MODELS

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/")
def index():
    """Settings overview page."""
    config = AIConfig.get_config()

    return render_template(
        "settings/index.html",
        config=config,
        available_models=AVAILABLE_MODELS,
    )


@settings_bp.route("/ai", methods=["POST"])
def update_ai():
    """Update AI configuration."""
    config = AIConfig.get_config()

    # Update API key if provided (not masked value)
    new_api_key = request.form.get("api_key", "").strip()
    if new_api_key and not new_api_key.startswith("****"):
        config.api_key = new_api_key

    # Update model
    config.model = request.form.get("model", "anthropic/claude-3-haiku")

    # Update custom model (optional)
    custom_model = request.form.get("custom_model", "").strip()
    config.custom_model = custom_model if custom_model else None

    # Update budget limit
    try:
        budget_limit = float(request.form.get("budget_limit", 10.0))
        config.budget_limit = max(0.0, budget_limit)
    except ValueError:
        pass

    # Update enabled status
    config.enabled = request.form.get("enabled") == "on"

    db.session.commit()

    flash("KI-Einstellungen gespeichert.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/ai/reset-budget", methods=["POST"])
def reset_budget():
    """Reset AI budget usage."""
    config = AIConfig.get_config()
    config.reset_budget()
    db.session.commit()

    flash("Budget-Verbrauch zurückgesetzt.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/ai/reset-stats", methods=["POST"])
def reset_stats():
    """Reset all AI statistics."""
    config = AIConfig.get_config()
    config.reset_all_stats()
    db.session.commit()

    flash("Alle KI-Statistiken zurückgesetzt.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/ai/test", methods=["POST"])
def test_connection():
    """Test OpenRouter API connection."""
    config = AIConfig.get_config()

    if not config.api_key:
        flash("Bitte zuerst einen API-Key eingeben.", "error")
        return redirect(url_for("settings.index"))

    from src.openrouter_client import OpenRouterClient

    client = OpenRouterClient(config.api_key, config.effective_model)
    success, message = client.test_connection()

    if success:
        flash(f"Verbindung erfolgreich: {message}", "success")
    else:
        flash(f"Verbindung fehlgeschlagen: {message}", "error")

    return redirect(url_for("settings.index"))
