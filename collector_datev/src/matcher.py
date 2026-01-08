"""Steuerberater-Kanzlei Matching nach PLZ-Durchlauf.

Dieses Modul implementiert einen Algorithmus, der nach dem Sammeln aller
Einträge einer PLZ Steuerberater ihren korrekten Gesellschafts-Kanzleien
zuordnet.

Problem:
    Steuerberater werden oft als Einzelperson gefunden → eigene Kanzlei erstellt.
    Später wird die echte Gesellschafts-Kanzlei gefunden, aber der Steuerberater
    bleibt falsch zugeordnet.

Lösung:
    Nach jedem PLZ-Durchlauf werden Steuerberater mit Einzelperson-Kanzlei
    gegen Gesellschafts-Kanzleien der gleichen PLZ geprüft. Bei ausreichender
    Übereinstimmung (Score >= 2) wird der Steuerberater umgehängt.

    Bei Score = 1 (unsicher) kann optional eine KI via OpenRouter befragt werden.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.kanzlei import Kanzlei
    from app.models.steuerberater import Steuerberater

logger = logging.getLogger(__name__)


# Minimum score required for automatic matching
MATCH_THRESHOLD = 2


@dataclass
class MatchResult:
    """Result of the matching process for a PLZ."""

    matched: int = 0
    deleted_kanzleien: int = 0
    details: list[str] = None
    # AI statistics
    ai_requests: int = 0
    ai_matches: int = 0
    ai_tokens_input: int = 0
    ai_tokens_output: int = 0
    ai_cost: float = 0.0
    ai_budget_exhausted: bool = False

    def __post_init__(self):
        if self.details is None:
            self.details = []


def get_email_domain(email: str | None) -> str | None:
    """Extract domain from email address.

    Args:
        email: Email address (e.g., "info@kanzlei-bellen.de")

    Returns:
        Domain part (e.g., "kanzlei-bellen.de") or None
    """
    if not email:
        return None

    # Simple regex to extract domain
    match = re.search(r"@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})$", email.strip())
    if match:
        return match.group(1).lower()
    return None


def normalize_street(strasse: str | None) -> str | None:
    """Normalize street address for comparison.

    Args:
        strasse: Street address

    Returns:
        Normalized street string or None
    """
    if not strasse:
        return None

    # Lowercase and strip
    s = strasse.lower().strip()

    # Common abbreviations → full form
    replacements = [
        (r"\bstr\.", "straße"),
        (r"\bstr\b", "straße"),
        (r"\bstraße\b", "straße"),
        (r"\bstrasse\b", "straße"),
        (r"\s+", " "),  # Multiple spaces → single
    ]

    for pattern, replacement in replacements:
        s = re.sub(pattern, replacement, s)

    return s


def calculate_match_score(stb: "Steuerberater", target_kanzlei: "Kanzlei") -> tuple[int, list[str]]:
    """Calculate match score between a Steuerberater and a potential Kanzlei.

    Indicators (each worth 1 point):
    1. Nachname appears in Kanzlei name
    2. Same street address
    3. Same email domain

    Args:
        stb: Steuerberater to check
        target_kanzlei: Target Gesellschafts-Kanzlei

    Returns:
        Tuple of (score, list of matched indicators)
    """
    score = 0
    indicators: list[str] = []

    old_kanzlei = stb.kanzlei

    # 1. Nachname im Kanzlei-Namen
    if stb.nachname and target_kanzlei.name:
        nachname_lower = stb.nachname.lower()
        kanzlei_name_lower = target_kanzlei.name.lower()

        if nachname_lower in kanzlei_name_lower:
            score += 1
            indicators.append(f"Name '{stb.nachname}' im Firmennamen")

    # 2. Gleiche Straße
    old_street = normalize_street(old_kanzlei.strasse if old_kanzlei else None)
    target_street = normalize_street(target_kanzlei.strasse)

    if old_street and target_street and old_street == target_street:
        score += 1
        indicators.append(f"Gleiche Adresse '{target_kanzlei.strasse}'")

    # 3. Gleiche E-Mail-Domain
    # Check both personal StB email and old Kanzlei email
    stb_domain = get_email_domain(stb.email) or get_email_domain(
        old_kanzlei.email if old_kanzlei else None
    )
    target_domain = get_email_domain(target_kanzlei.email)

    if stb_domain and target_domain and stb_domain == target_domain:
        score += 1
        indicators.append(f"Gleiche E-Mail-Domain '@{target_domain}'")

    return score, indicators


def match_steuerberater_to_kanzleien(
    plz: str,
    use_ai: bool = False,
    job_id: int | None = None,
) -> MatchResult:
    """Match Steuerberater zu Gesellschafts-Kanzleien einer PLZ.

    Nach dem Sammeln aller Einträge einer PLZ wird geprüft, ob
    Steuerberater mit Einzelperson-Kanzleien zu Gesellschafts-Kanzleien
    gehören sollten.

    Bei Score >= 2: Automatisches Match (regelbasiert)
    Bei Score = 1 und use_ai=True: KI-Abfrage via OpenRouter
    Bei Score = 0: Kein Match

    Args:
        plz: Postleitzahl für die das Matching durchgeführt werden soll
        use_ai: Wenn True, wird bei Score = 1 die KI befragt
        job_id: Optional Job-ID für AI-Usage-Tracking

    Returns:
        MatchResult mit Statistiken und Details
    """
    # Import here to avoid circular imports and ensure app context
    from app import db
    from app.models.kanzlei import Kanzlei
    from app.models.steuerberater import Steuerberater

    result = MatchResult()

    # AI client setup (only if use_ai=True)
    ai_client = None
    ai_config = None
    job = None

    if use_ai:
        from app.models import AIConfig
        from src.openrouter_client import OpenRouterClient

        ai_config = AIConfig.get_config()

        # Load job for tracking (if provided)
        if job_id:
            from app.models.job import Job
            job = Job.query.get(job_id)

        # Check if AI is enabled and configured
        if ai_config.enabled and ai_config.api_key:
            # Check budget
            if ai_config.budget_exhausted:
                logger.warning(f"PLZ {plz}: AI-Budget erschöpft, nur regelbasiertes Matching")
                result.ai_budget_exhausted = True
                use_ai = False  # Disable AI for this run
            else:
                ai_client = OpenRouterClient(ai_config.api_key, ai_config.effective_model)
                logger.debug(f"PLZ {plz}: AI-Matching aktiviert mit Modell {ai_config.effective_model}")
        else:
            logger.debug(f"PLZ {plz}: AI nicht konfiguriert oder deaktiviert")
            use_ai = False

    # 1. Finde alle Gesellschafts-Kanzleien der PLZ
    #    (haben eine Rechtsform = sind Gesellschaften)
    gesellschafts_kanzleien = Kanzlei.query.filter(
        Kanzlei.plz == plz,
        Kanzlei.rechtsform_id.isnot(None),
    ).all()

    if not gesellschafts_kanzleien:
        logger.debug(f"PLZ {plz}: Keine Gesellschafts-Kanzleien gefunden")
        return result

    logger.debug(
        f"PLZ {plz}: {len(gesellschafts_kanzleien)} Gesellschafts-Kanzleien gefunden"
    )

    # 2. Finde alle Steuerberater mit Einzelperson-Kanzlei in dieser PLZ
    #    (Kanzlei ohne Rechtsform = Einzelperson)
    kandidaten = (
        Steuerberater.query.join(Kanzlei)
        .filter(
            Kanzlei.plz == plz,
            Kanzlei.rechtsform_id.is_(None),
        )
        .all()
    )

    if not kandidaten:
        logger.debug(f"PLZ {plz}: Keine Einzelperson-Steuerberater gefunden")
        return result

    logger.debug(f"PLZ {plz}: {len(kandidaten)} Einzelperson-Steuerberater gefunden")

    # Track orphaned Kanzleien to delete
    kanzleien_to_check: set[int] = set()

    # 3. Für jeden Kandidaten: Prüfe Match gegen alle Gesellschafts-Kanzleien
    for stb in kandidaten:
        old_kanzlei = stb.kanzlei
        best_match: tuple[Kanzlei, float, list[str]] | None = None

        for kanzlei in gesellschafts_kanzleien:
            score, indicators = calculate_match_score(stb, kanzlei)

            if score >= MATCH_THRESHOLD:
                # Take best match (highest score)
                if best_match is None or score > best_match[1]:
                    best_match = (kanzlei, score, indicators)

            elif score == 1 and use_ai and ai_client:
                # Score = 1: Unsicher → KI befragen
                # Check budget before each AI call
                if ai_config.budget_exhausted:
                    result.ai_budget_exhausted = True
                    logger.warning(f"AI-Budget erschöpft bei StB '{stb.full_name}'")
                    continue

                logger.info(f"KI-Abfrage für '{stb.full_name}' → '{kanzlei.name}'")

                try:
                    ai_result = ai_client.check_match(stb, kanzlei)

                    # Track AI usage
                    result.ai_requests += 1
                    result.ai_tokens_input += ai_result.tokens_input
                    result.ai_tokens_output += ai_result.tokens_output
                    result.ai_cost += ai_result.cost

                    # Update global AI config budget
                    ai_config.add_usage(
                        tokens_input=ai_result.tokens_input,
                        tokens_output=ai_result.tokens_output,
                        cost=ai_result.cost,
                    )

                    # Update job tracking (if provided)
                    if job:
                        job.add_ai_usage(
                            tokens_input=ai_result.tokens_input,
                            tokens_output=ai_result.tokens_output,
                            cost=ai_result.cost,
                        )

                    if ai_result.match:
                        # KI bestätigt Match
                        result.ai_matches += 1
                        ai_indicators = indicators + [f"KI: {ai_result.reason}"]
                        # Treat AI-confirmed match as score 1.5 (better than plain 1, worse than 2)
                        if best_match is None or best_match[1] < 1.5:
                            best_match = (kanzlei, 1.5, ai_indicators)
                        logger.info(f"KI bestätigt Match: {ai_result.reason}")
                    else:
                        logger.info(f"KI verneint Match: {ai_result.reason}")

                except Exception as e:
                    logger.error(f"KI-Fehler bei '{stb.full_name}': {e}")
                    # Continue without AI match on error

        if best_match:
            target_kanzlei, score, indicators = best_match

            # Log the match
            detail = (
                f"StB '{stb.full_name}' → '{target_kanzlei.name}' "
                f"(Score: {score}, Indikatoren: {', '.join(indicators)})"
            )
            result.details.append(detail)
            logger.info(f"Match: {detail}")

            # Reassign Steuerberater
            old_kanzlei_id = stb.kanzlei_id
            stb.kanzlei_id = target_kanzlei.id
            kanzleien_to_check.add(old_kanzlei_id)

            result.matched += 1

    # 4. Delete orphaned Einzelperson-Kanzleien
    for kanzlei_id in kanzleien_to_check:
        kanzlei = Kanzlei.query.get(kanzlei_id)
        if kanzlei and kanzlei.steuerberater.count() == 0:
            logger.info(f"Lösche verwaiste Kanzlei: '{kanzlei.name}'")
            result.details.append(f"Kanzlei gelöscht: '{kanzlei.name}'")
            db.session.delete(kanzlei)
            result.deleted_kanzleien += 1

    # Commit changes
    if result.matched > 0 or result.ai_requests > 0:
        db.session.commit()

        # Build log message
        log_parts = [f"PLZ {plz}: {result.matched} StB umgehängt"]
        log_parts.append(f"{result.deleted_kanzleien} Kanzleien gelöscht")

        if result.ai_requests > 0:
            log_parts.append(
                f"KI: {result.ai_requests} Anfragen, "
                f"{result.ai_matches} Matches, ${result.ai_cost:.4f}"
            )

        logger.info(", ".join(log_parts))

    return result
