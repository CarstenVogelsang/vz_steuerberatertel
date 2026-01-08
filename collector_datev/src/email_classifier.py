"""Email Classifier.

Classifies emails as either Kanzlei (firm) or Steuerberater (person) emails
based on keyword patterns in the local part.
"""

from __future__ import annotations


# Keywords that indicate a Kanzlei email (generic firm addresses)
KANZLEI_KEYWORDS = [
    "kanzlei",
    "info",
    "kontakt",
    "office",
    "mail",
    "post",
    "sekretariat",
    "buero",
    "empfang",
    "verwaltung",
    "zentrale",
    "team",
    "service",
    "anfrage",
]


def is_kanzlei_email(email: str) -> bool:
    """Check if an email address belongs to a Kanzlei (firm) rather than a person.

    This function uses keyword-based heuristics to determine if an email address
    is a generic firm address (e.g., info@, kanzlei@, kontakt@) or a personal
    address (e.g., vorname.nachname@).

    Args:
        email: The email address to classify

    Returns:
        True if the email appears to be a Kanzlei email, False otherwise

    Examples:
        >>> is_kanzlei_email("kanzlei@stb-mueller.de")
        True
        >>> is_kanzlei_email("info@steuerberater.de")
        True
        >>> is_kanzlei_email("hans.mueller@kanzlei.de")
        False
        >>> is_kanzlei_email("h.schmidt@stb-schmidt.de")
        False
    """
    if not email or "@" not in email:
        return False

    local_part = email.split("@")[0].lower()

    # Check if the local part contains any Kanzlei keywords
    for keyword in KANZLEI_KEYWORDS:
        if keyword in local_part:
            return True

    return False


def classify_email(email: str) -> str:
    """Classify an email address as 'kanzlei' or 'steuerberater'.

    Args:
        email: The email address to classify

    Returns:
        'kanzlei' or 'steuerberater'
    """
    return "kanzlei" if is_kanzlei_email(email) else "steuerberater"
