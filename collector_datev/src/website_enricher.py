"""Website enrichment module for extracting and validating websites from email domains."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

DEFAULT_BLACKLIST_PATH = Path(__file__).parent.parent / "data" / "domain_blacklist.txt"


class Confidence(Enum):
    """Confidence level for website validation."""

    HIGH = "hoch"  # Name in <title> or <h1>
    MEDIUM = "mittel"  # Name somewhere in body
    LOW = "niedrig"  # Page reachable, name not found
    CONSTRUCTION = "baustelle"  # Website is under construction
    NONE = "keine"  # Page not reachable


# Keywords und Patterns fuer Baustellen-Erkennung
CONSTRUCTION_KEYWORDS = [
    # Deutsch
    "baustelle",
    "im aufbau",
    "in bearbeitung",
    "in kürze",
    "demnächst",
    "website wird erstellt",
    "seite im aufbau",
    "webseite in vorbereitung",
    "noch nicht verfügbar",
    "bald verfuegbar",
    "wir arbeiten daran",
    # Englisch
    "under construction",
    "coming soon",
    "work in progress",
    "launching soon",
    "site under development",
    "website coming",
    "stay tuned",
]

HOSTING_PROVIDER_PATTERNS = [
    r"congratulations.*first.*website",  # Plesk
    r"plesk",
    r"index of /",  # cPanel
    r"apache.*server at",
    r"diese domain wurde.*registriert",  # IONOS
    r"willkommen bei strato",
    r"all-inkl",
    r"webseite in vorbereitung",
    r"apache.*default\s+page",  # Apache default page (spezifischer, um WordPress CSS-Klassen auszuschliessen)
    r"placeholder\s+(page|site|website|seite)",  # Nur "placeholder page/site", nicht HTML placeholder-Attribute
    r"domain.*parked",
    r"website.*parked",
    r"hostinger",
    r"domain.*geparkt",
]

CMS_DEFAULT_PATTERNS = [
    r"hello world",  # WordPress
    r"just another wordpress",
    r"erstellt mit jimdo",
    r"powered by wix",
    r"sample page",
    r"this is your first post",
]


def is_construction_site(html_content: str) -> bool:
    """Erkennt ob eine Website eine Baustelle ist.

    Prueft auf:
    1. Under Construction Keywords (DE/EN)
    2. Hosting-Provider Standard-Seiten (Plesk, cPanel, etc.)
    3. CMS Default-Seiten (WordPress Hello World, etc.)

    Args:
        html_content: HTML-Content der Website (bereits lowercase)

    Returns:
        True wenn Baustelle erkannt wurde
    """
    html_lower = html_content.lower()

    # Keyword-Check
    for keyword in CONSTRUCTION_KEYWORDS:
        if keyword in html_lower:
            logger.debug("Baustellen-Keyword gefunden: '%s'", keyword)
            return True

    # Pattern-Check (Hosting-Provider)
    for pattern in HOSTING_PROVIDER_PATTERNS:
        if re.search(pattern, html_lower):
            logger.debug("Hosting-Provider Pattern gefunden: '%s'", pattern)
            return True

    # CMS-Default-Check
    for pattern in CMS_DEFAULT_PATTERNS:
        if re.search(pattern, html_lower):
            logger.debug("CMS-Default Pattern gefunden: '%s'", pattern)
            return True

    return False


@dataclass
class WebsiteResult:
    """Result of website validation."""

    url: str | None = None
    confidence: Confidence = Confidence.NONE
    error: str | None = None


def load_blacklist(path: Path = DEFAULT_BLACKLIST_PATH) -> set[str]:
    """Load email domain blacklist from file.

    Args:
        path: Path to blacklist file (one domain per line, # for comments)

    Returns:
        Set of blacklisted domains (lowercase)
    """
    blacklist: set[str] = set()

    if not path.exists():
        logger.warning("Blacklist nicht gefunden: %s", path)
        return blacklist

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                blacklist.add(line.lower())

    logger.debug("%s Domains in Blacklist geladen", len(blacklist))
    return blacklist


def extract_domain(email: str) -> str | None:
    """Extract domain from email address.

    Args:
        email: Email address

    Returns:
        Domain part or None if invalid
    """
    if not email or "@" not in email:
        return None

    try:
        domain = email.split("@")[1].strip().lower()
        if "." in domain:
            return domain
    except (IndexError, AttributeError):
        pass

    return None


def is_blacklisted(domain: str, blacklist: set[str]) -> bool:
    """Check if domain is in blacklist.

    Args:
        domain: Domain to check
        blacklist: Set of blacklisted domains

    Returns:
        True if domain is blacklisted
    """
    return domain.lower() in blacklist


def normalize_name(name: str) -> str:
    """Normalize company name for matching.

    Removes common suffixes, special characters, and normalizes whitespace.

    Args:
        name: Company or person name

    Returns:
        Normalized name for comparison
    """
    # Convert to lowercase
    normalized = name.lower()

    # Remove common legal suffixes
    suffixes = [
        r"\bpartnerschaftsgesellschaft\b",
        r"\bmit beschraenkter berufshaftung\b",
        r"\bmit beschränkter berufshaftung\b",
        r"\bpartg\s*mbb\b",
        r"\bpartg\b",
        r"\bgmbh\b",
        r"\bg\.m\.b\.h\.\b",
        r"\bmbh\b",
        r"\bsteuerberatungsgesellschaft\b",
        r"\bsteuerberater\b",
        r"\bsteuerberaterin\b",
        r"\b&\s*co\.\s*kg\b",
        r"\b&\s*co\b",
    ]

    for suffix in suffixes:
        normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)

    # Normalize umlauts
    umlaut_map = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for umlaut, replacement in umlaut_map.items():
        normalized = normalized.replace(umlaut, replacement)

    # Remove special characters, keep only alphanumeric and spaces
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)

    # Normalize whitespace
    normalized = " ".join(normalized.split())

    return normalized.strip()


def extract_search_terms(name: str) -> list[str]:
    """Extract meaningful search terms from company/person name.

    Args:
        name: Company or person name

    Returns:
        List of search terms to look for on website
    """
    normalized = normalize_name(name)
    words = normalized.split()

    # Filter out very short words
    significant_words = [w for w in words if len(w) >= 3]

    terms = []

    # Full normalized name
    if normalized:
        terms.append(normalized)

    # Individual significant words (for matching parts of name)
    terms.extend(significant_words)

    return terms


async def validate_website(
    page: Page,
    domain: str,
    company_name: str,
    timeout_ms: int = 10000,
) -> WebsiteResult:
    """Validate if a website exists and matches the company.

    Tries both https://domain and https://www.domain.

    Args:
        page: Playwright page object
        domain: Domain to check (without protocol)
        company_name: Company name to search for
        timeout_ms: Request timeout in milliseconds

    Returns:
        WebsiteResult with URL and confidence level
    """
    urls_to_try = [
        f"https://www.{domain}",
        f"https://{domain}",
    ]

    search_terms = extract_search_terms(company_name)
    if not search_terms:
        return WebsiteResult(error="Kein gueltiger Firmenname")

    for url in urls_to_try:
        try:
            logger.debug("Pruefe %s", url)
            response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

            if not response or response.status >= 400:
                logger.debug("HTTP %s fuer %s", response.status if response else "None", url)
                continue

            # Get page content
            html_content = await page.content()
            html_lower = html_content.lower()

            # Normalize umlauts in HTML for matching
            for umlaut, replacement in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
                html_lower = html_lower.replace(umlaut, replacement)

            # Check for construction/placeholder site FIRST
            if is_construction_site(html_lower):
                logger.info("Baustelle erkannt: %s", url)
                return WebsiteResult(url=url, confidence=Confidence.CONSTRUCTION)

            # Check for name in title
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html_lower, re.DOTALL)
            title_text = title_match.group(1) if title_match else ""

            # Check for name in h1
            h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html_lower, re.DOTALL)
            h1_text = " ".join(h1_matches)

            # Check each search term
            for term in search_terms:
                # HIGH: Name in title or h1
                if term in title_text or term in h1_text:
                    logger.info("Hohe Konfidenz: '%s' in Title/H1 auf %s", term, url)
                    return WebsiteResult(url=url, confidence=Confidence.HIGH)

            # Check body for any term
            for term in search_terms:
                if term in html_lower:
                    logger.info("Mittlere Konfidenz: '%s' im Body auf %s", term, url)
                    return WebsiteResult(url=url, confidence=Confidence.MEDIUM)

            # Page reachable but name not found
            logger.info("Niedrige Konfidenz: Seite erreichbar aber Name nicht gefunden auf %s", url)
            return WebsiteResult(url=url, confidence=Confidence.LOW)

        except PlaywrightTimeout:
            logger.debug("Timeout fuer %s", url)
            continue
        except Exception as e:
            logger.debug("Fehler bei %s: %s", url, e)
            continue

    return WebsiteResult(error="Seite nicht erreichbar")


async def enrich_website_from_email(
    page: Page,
    email: str,
    company_name: str,
    blacklist: set[str],
    timeout_ms: int = 10000,
) -> WebsiteResult:
    """Attempt to find website from email domain.

    Args:
        page: Playwright page object
        email: Email address
        company_name: Company name for validation
        blacklist: Set of blacklisted domains
        timeout_ms: Request timeout in milliseconds

    Returns:
        WebsiteResult with URL and confidence
    """
    domain = extract_domain(email)

    if not domain:
        return WebsiteResult(error="Keine gueltige E-Mail")

    if is_blacklisted(domain, blacklist):
        return WebsiteResult(error=f"Domain '{domain}' ist blacklisted")

    return await validate_website(page, domain, company_name, timeout_ms)


def extract_domain_from_url(url: str) -> str | None:
    """Extract domain from URL, removing www. prefix.

    Args:
        url: Full URL (e.g., https://www.example.de/path)

    Returns:
        Domain without www. (e.g., example.de) or None if invalid
    """
    if not url:
        return None

    # Remove protocol
    url = url.lower().strip()
    if url.startswith("https://"):
        url = url[8:]
    elif url.startswith("http://"):
        url = url[7:]

    # Remove path
    if "/" in url:
        url = url.split("/")[0]

    # Remove www. prefix
    if url.startswith("www."):
        url = url[4:]

    # Validate domain has at least one dot
    if "." not in url:
        return None

    return url


def add_to_blacklist(domain: str, path: Path = DEFAULT_BLACKLIST_PATH) -> bool:
    """Füge Domain zur Blacklist-Datei hinzu, falls nicht vorhanden.

    Die Domain wird unter der Sektion "# Unsortiert" eingefügt,
    falls diese existiert. Ansonsten wird sie am Ende angehängt.

    Args:
        domain: Domain zum Hinzufügen (ohne www.)
        path: Pfad zur Blacklist-Datei

    Returns:
        True wenn Domain hinzugefügt wurde, False wenn bereits vorhanden
    """
    domain = domain.lower().strip()

    # Existierende Blacklist laden
    existing = load_blacklist(path)

    if domain in existing:
        logger.info("Domain '%s' bereits in Blacklist", domain)
        return False

    # Datei lesen um "# Unsortiert" Sektion zu finden
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = content.splitlines()

    # Suche nach "# Unsortiert" Sektion
    unsortiert_index = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == "# unsortiert":
            unsortiert_index = i
            break

    if unsortiert_index >= 0:
        # Füge nach "# Unsortiert" ein
        lines.insert(unsortiert_index + 1, domain)
        path.write_text("\n".join(lines), encoding="utf-8")
    else:
        # Append am Ende
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{domain}")

    logger.info("Domain '%s' zur Blacklist hinzugefuegt: %s", domain, path.name)
    return True


