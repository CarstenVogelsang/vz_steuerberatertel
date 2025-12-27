"""Impressum-Finder module for German websites.

Finds and extracts Impressum (legal notice) pages from websites,
which are required by German law (TMG) and contain contact information.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# Patterns for finding Impressum links
IMPRESSUM_LINK_PATTERNS = [
    # German
    "impressum",
    "kontakt",
    "ueber-uns",
    "über uns",
    "ueber uns",
    # English
    "imprint",
    "contact",
    "about-us",
    "about us",
    "legal",
    "legal-notice",
]

IMPRESSUM_URL_PATTERNS = [
    "/impressum",
    "/imprint",
    "/kontakt",
    "/contact",
    "/about",
    "/ueber-uns",
    "/about-us",
    "/legal",
]


async def find_impressum_url(page: Page, base_url: str) -> str | None:
    """Find Impressum link on a website.

    Strategy:
    1. Search for links with href containing Impressum patterns
    2. Search for links with text matching Impressum patterns
    3. Search specifically in footer area
    4. Fallback: Try appending /impressum to base URL

    Args:
        page: Playwright page object (already loaded with website)
        base_url: Base URL of the website

    Returns:
        Full URL to Impressum page or None if not found
    """
    try:
        # Strategy 1: Search for links by href pattern
        for pattern in IMPRESSUM_URL_PATTERNS:
            links = await page.locator(f'a[href*="{pattern}"]').all()
            if links:
                href = await links[0].get_attribute("href")
                if href:
                    full_url = urljoin(base_url, href)
                    logger.debug("Impressum gefunden via href: %s", full_url)
                    return full_url

        # Strategy 2: Search for links by text content
        for pattern in IMPRESSUM_LINK_PATTERNS:
            # Case-insensitive text search
            links = await page.locator(f'a:text-is("{pattern}")').all()
            if not links:
                links = await page.locator(f'a:text("{pattern}")').all()
            if links:
                href = await links[0].get_attribute("href")
                if href:
                    full_url = urljoin(base_url, href)
                    logger.debug("Impressum gefunden via Text '%s': %s", pattern, full_url)
                    return full_url

        # Strategy 3: Search specifically in footer
        footer_selectors = ["footer", ".footer", "#footer", "[role='contentinfo']"]
        for selector in footer_selectors:
            footer = page.locator(selector)
            if await footer.count() > 0:
                for pattern in IMPRESSUM_LINK_PATTERNS:
                    links = await footer.locator(f'a:text("{pattern}")').all()
                    if links:
                        href = await links[0].get_attribute("href")
                        if href:
                            full_url = urljoin(base_url, href)
                            logger.debug("Impressum im Footer gefunden: %s", full_url)
                            return full_url

        # Strategy 4: Fallback - try /impressum directly
        parsed = urlparse(base_url)
        fallback_url = f"{parsed.scheme}://{parsed.netloc}/impressum"
        logger.debug("Kein Impressum-Link gefunden, versuche Fallback: %s", fallback_url)
        return fallback_url

    except Exception as e:
        logger.debug("Fehler beim Impressum-Suchen: %s", e)
        return None


async def load_impressum_content(
    page: Page,
    impressum_url: str,
    timeout_ms: int = 10000,
) -> str | None:
    """Load Impressum page and return its text content.

    Args:
        page: Playwright page object
        impressum_url: URL to the Impressum page
        timeout_ms: Timeout in milliseconds

    Returns:
        Text content of the page or None if failed
    """
    try:
        response = await page.goto(impressum_url, timeout=timeout_ms, wait_until="domcontentloaded")

        if not response or response.status >= 400:
            logger.debug("Impressum nicht erreichbar: HTTP %s", response.status if response else "None")
            return None

        # Get text content
        content = await page.content()
        return content.lower()

    except PlaywrightTimeout:
        logger.debug("Timeout beim Laden des Impressums: %s", impressum_url)
        return None
    except Exception as e:
        logger.debug("Fehler beim Laden des Impressums: %s", e)
        return None


def normalize_for_comparison(text: str) -> str:
    """Normalize text for comparison (lowercase, normalize umlauts, remove special chars).

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    text = text.lower().strip()

    # Normalize umlauts
    replacements = [
        ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
        ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    return text


def normalize_phone(phone: str) -> str:
    """Normalize phone number for comparison.

    Removes spaces, slashes, dashes, parentheses.
    Keeps only digits.

    Args:
        phone: Phone number string

    Returns:
        Normalized phone (digits only)
    """
    return re.sub(r"[^\d]", "", phone)


def search_in_content(content: str, search_term: str) -> bool:
    """Search for a term in content with normalization.

    Args:
        content: Content to search in (should be pre-normalized/lowercase)
        search_term: Term to search for

    Returns:
        True if found
    """
    normalized_term = normalize_for_comparison(search_term)
    return normalized_term in content


def search_phone_in_content(content: str, phone: str) -> bool:
    """Search for phone number in content.

    Normalizes both content and phone number to digits only
    and searches for a subsequence match.

    Args:
        content: Content to search in
        phone: Phone number to find

    Returns:
        True if phone found
    """
    if not phone:
        return False

    # Normalize phone to digits only
    phone_digits = normalize_phone(phone)
    if len(phone_digits) < 6:  # Too short to be meaningful
        return False

    # Extract all digits from content
    content_digits = re.sub(r"[^\d]", "", content)

    # Search for phone digits in content
    return phone_digits in content_digits
