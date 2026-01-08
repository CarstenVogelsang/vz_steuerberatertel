"""OpenRouter API Client for AI-based Steuerberater-Kanzlei Matching.

This module provides a client for the OpenRouter API to query LLMs
for uncertain matching cases (Score = 1).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.models.steuerberater import Steuerberater
    from app.models.kanzlei import Kanzlei

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_AUTH_URL = "https://openrouter.ai/api/v1/auth/key"


@dataclass
class AIMatchResult:
    """Result of an AI matching query."""

    match: bool
    reason: str
    tokens_input: int
    tokens_output: int
    cost: float  # USD
    error: str | None = None


class OpenRouterClient:
    """Client for OpenRouter API."""

    def __init__(self, api_key: str, model: str):
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key
            model: Model ID (e.g., "anthropic/claude-3-haiku")
        """
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=30.0)

    def __del__(self):
        """Close the HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()

    def check_match(
        self,
        stb: "Steuerberater",
        target_kanzlei: "Kanzlei",
    ) -> AIMatchResult:
        """Ask the AI if a Steuerberater belongs to a Kanzlei.

        Args:
            stb: Steuerberater to check
            target_kanzlei: Potential target Gesellschafts-Kanzlei

        Returns:
            AIMatchResult with decision, reason, and usage stats
        """
        old_kanzlei = stb.kanzlei

        # Build the prompt
        prompt = self._build_prompt(stb, old_kanzlei, target_kanzlei)

        try:
            response = self._client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://steuerberater.tel",
                    "X-Title": "Steuerberater Collector",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.1,  # Low temperature for consistent decisions
                },
            )

            response.raise_for_status()
            data = response.json()

            # Extract usage
            usage = data.get("usage", {})
            tokens_input = usage.get("prompt_tokens", 0)
            tokens_output = usage.get("completion_tokens", 0)

            # Calculate cost (approximate, varies by model)
            # OpenRouter returns cost in generation_cost if available
            cost = data.get("generation_cost", 0.0)
            if not cost:
                # Fallback: estimate based on tokens
                cost = self._estimate_cost(tokens_input, tokens_output)

            # Parse the response
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            match, reason = self._parse_response(content)

            logger.debug(
                f"AI Match Check: {stb.full_name} → {target_kanzlei.name} = {match} "
                f"(tokens: {tokens_input}+{tokens_output}, cost: ${cost:.4f})"
            )

            return AIMatchResult(
                match=match,
                reason=reason,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost=cost,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API error: {e.response.status_code} - {e.response.text}")
            return AIMatchResult(
                match=False,
                reason="API-Fehler",
                tokens_input=0,
                tokens_output=0,
                cost=0.0,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"OpenRouter request failed: {e}")
            return AIMatchResult(
                match=False,
                reason="Anfrage fehlgeschlagen",
                tokens_input=0,
                tokens_output=0,
                cost=0.0,
                error=str(e),
            )

    def _build_prompt(
        self,
        stb: "Steuerberater",
        old_kanzlei: "Kanzlei",
        target_kanzlei: "Kanzlei",
    ) -> str:
        """Build the prompt for the AI."""
        return f"""Analysiere ob dieser Steuerberater zu der Gesellschafts-Kanzlei gehört.

STEUERBERATER:
- Name: {stb.vorname or ''} {stb.nachname}
- Titel: {stb.titel or '-'}
- E-Mail: {stb.email or '-'}
- Aktuell zugeordnet zu: "{old_kanzlei.name if old_kanzlei else '-'}"
- Adresse der aktuellen Kanzlei: {old_kanzlei.strasse or '-'}, {old_kanzlei.plz or ''} {old_kanzlei.ort or ''}

GESELLSCHAFTS-KANZLEI (potentielles Ziel):
- Name: {target_kanzlei.name}
- Adresse: {target_kanzlei.strasse or '-'}, {target_kanzlei.plz or ''} {target_kanzlei.ort or ''}
- E-Mail: {target_kanzlei.email or '-'}
- Website: {target_kanzlei.website or '-'}

Gehört der Steuerberater wahrscheinlich zu dieser Gesellschafts-Kanzlei?
Berücksichtige: Namensähnlichkeiten im Firmennamen, gleiche Adresse, E-Mail-Domain.

Antworte EXAKT in diesem JSON-Format:
{{"match": true, "reason": "kurze Begründung"}}
oder
{{"match": false, "reason": "kurze Begründung"}}"""

    def _parse_response(self, content: str) -> tuple[bool, str]:
        """Parse the AI response to extract match decision and reason."""
        try:
            # Try to extract JSON from the response
            content = content.strip()

            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            match = bool(data.get("match", False))
            reason = data.get("reason", "Keine Begründung")
            return match, reason

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse AI response: {content[:200]} - {e}")

            # Fallback: try to detect yes/no in text
            content_lower = content.lower()
            if "true" in content_lower or "ja" in content_lower or "gehört" in content_lower:
                return True, "KI-Antwort konnte nicht geparst werden, aber positiv interpretiert"
            return False, "KI-Antwort konnte nicht geparst werden"

    def _estimate_cost(self, tokens_input: int, tokens_output: int) -> float:
        """Estimate cost based on model and tokens.

        This is a rough estimate; OpenRouter should return actual cost.
        """
        # Approximate costs per 1M tokens (varies by model)
        cost_per_1m_input = 0.25  # Conservative estimate
        cost_per_1m_output = 0.50

        input_cost = (tokens_input / 1_000_000) * cost_per_1m_input
        output_cost = (tokens_output / 1_000_000) * cost_per_1m_output

        return input_cost + output_cost

    def get_credits(self) -> dict:
        """Get current account credits/limits from OpenRouter.

        Returns:
            Dict with credit information or empty dict on error
        """
        try:
            response = self._client.get(
                OPENROUTER_AUTH_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Failed to get OpenRouter credits: {e}")
            return {}

    def test_connection(self) -> tuple[bool, str]:
        """Test the API connection and key validity.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            credits = self.get_credits()
            if credits:
                limit = credits.get("limit", "unknown")
                usage = credits.get("usage", 0)
                return True, f"Verbindung OK. Limit: ${limit}, Verbraucht: ${usage:.4f}"
            return False, "Keine Daten von OpenRouter erhalten"
        except Exception as e:
            return False, f"Verbindungsfehler: {e}"
