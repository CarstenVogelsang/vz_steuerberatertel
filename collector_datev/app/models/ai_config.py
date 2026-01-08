"""AI Configuration Model.

Stores OpenRouter API configuration including encrypted API key,
model selection, and budget tracking.
"""

from __future__ import annotations

import os
from base64 import b64decode, b64encode
from datetime import datetime

from cryptography.fernet import Fernet

from app import db


def _get_encryption_key() -> bytes:
    """Get or generate encryption key for API key storage.

    Uses FLASK_SECRET_KEY as base for Fernet key generation.
    """
    secret = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    # Pad/truncate to 32 bytes for Fernet
    key_bytes = secret.encode()[:32].ljust(32, b"0")
    return b64encode(key_bytes)


def _encrypt(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return ""
    f = Fernet(_get_encryption_key())
    return f.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    """Decrypt a string value."""
    if not value:
        return ""
    try:
        f = Fernet(_get_encryption_key())
        return f.decrypt(value.encode()).decode()
    except Exception:
        return ""


# Available models for OpenRouter (sorted by cost)
AVAILABLE_MODELS = [
    {
        "id": "mistralai/mistral-7b-instruct",
        "name": "Mistral 7B Instruct",
        "cost_per_1m": 0.05,
    },
    {
        "id": "google/gemini-flash-1.5",
        "name": "Gemini Flash 1.5",
        "cost_per_1m": 0.075,
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o Mini",
        "cost_per_1m": 0.15,
    },
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "cost_per_1m": 0.25,
    },
    {
        "id": "anthropic/claude-3.5-sonnet",
        "name": "Claude 3.5 Sonnet",
        "cost_per_1m": 3.0,
    },
]


class AIConfig(db.Model):
    """AI Configuration for OpenRouter integration."""

    __tablename__ = "ai_config"

    id = db.Column(db.Integer, primary_key=True)
    _api_key_encrypted = db.Column("api_key", db.String(500))
    model = db.Column(db.String(100), default="anthropic/claude-3-haiku")
    custom_model = db.Column(db.String(100))  # For custom model IDs
    budget_limit = db.Column(db.Float, default=10.0)  # USD
    budget_used = db.Column(db.Float, default=0.0)  # USD
    total_requests = db.Column(db.Integer, default=0)
    total_tokens_input = db.Column(db.Integer, default=0)
    total_tokens_output = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def api_key(self) -> str:
        """Decrypt and return API key."""
        return _decrypt(self._api_key_encrypted or "")

    @api_key.setter
    def api_key(self, value: str):
        """Encrypt and store API key."""
        self._api_key_encrypted = _encrypt(value) if value else None

    @property
    def api_key_masked(self) -> str:
        """Return masked API key for display."""
        key = self.api_key
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    @property
    def effective_model(self) -> str:
        """Return the effective model ID (custom or selected)."""
        if self.custom_model:
            return self.custom_model
        return self.model

    @property
    def budget_remaining(self) -> float:
        """Return remaining budget in USD."""
        return max(0.0, self.budget_limit - self.budget_used)

    @property
    def budget_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return self.budget_used >= self.budget_limit

    @property
    def is_configured(self) -> bool:
        """Check if AI is properly configured."""
        return bool(self.api_key) and self.enabled

    def add_usage(self, tokens_input: int, tokens_output: int, cost: float):
        """Add usage statistics.

        Args:
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens
            cost: Cost in USD
        """
        self.total_requests += 1
        self.total_tokens_input += tokens_input
        self.total_tokens_output += tokens_output
        self.budget_used += cost

    def reset_budget(self):
        """Reset budget usage (keeps statistics)."""
        self.budget_used = 0.0

    def reset_all_stats(self):
        """Reset all statistics including budget."""
        self.budget_used = 0.0
        self.total_requests = 0
        self.total_tokens_input = 0
        self.total_tokens_output = 0

    @classmethod
    def get_config(cls) -> "AIConfig":
        """Get the singleton AI config, creating if needed."""
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config

    def __repr__(self) -> str:
        return f"<AIConfig model={self.effective_model} enabled={self.enabled}>"
