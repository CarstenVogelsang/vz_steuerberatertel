"""Search-based website enrichment module.

Provides website search via DuckDuckGo or SerpAPI.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .website_enricher import (
    Confidence,
    WebsiteResult,
    extract_search_terms,
    is_construction_site,
)

logger = logging.getLogger(__name__)

DEFAULT_BLACKLIST_PATH = Path(__file__).parent.parent / "data" / "domain_blacklist.txt"


class SearchProvider(Enum):
    """Available search providers."""

    DUCKDUCKGO = "duckduckgo"
    SERPAPI = "serpapi"
    SERPER = "serper"  # 2,500 kostenlose Suchen/Monat
    BRAVE = "brave"  # 2,000 kostenlose Suchen/Monat


@dataclass
class SearchResult:
    """A single search result."""

    url: str
    title: str
    snippet: str = ""


def load_blacklist(path: Path = DEFAULT_BLACKLIST_PATH) -> set[str]:
    """Load domain blacklist from file.

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


def is_directory_url(url: str, blacklist: set[str]) -> bool:
    """Check if URL belongs to a blacklisted directory.

    Args:
        url: URL to check
        blacklist: Set of blacklisted domains

    Returns:
        True if URL is from a blacklisted directory
    """
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc

        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Check exact match
        if domain in blacklist:
            return True

        # Check if any blacklist entry is contained in the domain
        for blocked in blacklist:
            # TLD filter (e.g., ".cn", ".ru")
            if blocked.startswith(".") and domain.endswith(blocked):
                return True
            # Normal domain check
            if blocked in domain or domain.endswith(f".{blocked}"):
                return True

        # Check path-based matches (e.g., google.com/maps)
        full_path = f"{domain}{parsed.path}"
        for blocked in blacklist:
            if not blocked.startswith(".") and blocked in full_path:
                return True

        return False
    except Exception:
        return False


def search_duckduckgo(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search using DuckDuckGo (legacy API-based, often unreliable).

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    try:
        from duckduckgo_search import DDGS

        ddgs = DDGS()
        results = ddgs.text(query, region="de-de", max_results=max_results)

        search_results = []
        for r in results:
            search_results.append(
                SearchResult(
                    url=r.get("href", ""),
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                )
            )

        logger.debug("DuckDuckGo: %s Ergebnisse fuer '%s'", len(search_results), query)
        return search_results

    except ImportError:
        logger.error("duckduckgo-search nicht installiert. Bitte 'pip install duckduckgo-search' ausfuehren.")
        return []
    except Exception as e:
        logger.error("DuckDuckGo Fehler: %s", e)
        return []


async def search_duckduckgo_playwright(
    page: Page,
    query: str,
    max_results: int = 5,
    use_stealth: bool = True,
) -> list[SearchResult]:
    """Search using DuckDuckGo via Playwright browser (more reliable).

    Uses real browser to perform DuckDuckGo search, avoiding API issues.
    With stealth mode enabled, uses playwright-stealth to avoid bot detection.

    Args:
        page: Playwright page object
        query: Search query
        max_results: Maximum number of results
        use_stealth: Enable playwright-stealth for anti-bot detection (default: True)

    Returns:
        List of SearchResult objects
    """
    from urllib.parse import quote_plus

    # Apply stealth mode if requested
    if use_stealth:
        try:
            from playwright_stealth import Stealth
            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            logger.debug("Stealth-Modus aktiviert")
        except ImportError:
            logger.warning("playwright-stealth nicht installiert. Stealth-Modus deaktiviert.")

    search_results: list[SearchResult] = []

    try:
        # Navigate to DuckDuckGo with German region
        search_url = f"https://duckduckgo.com/?q={quote_plus(query)}&kl=de-de"
        logger.debug("DuckDuckGo Browser-Suche: %s", search_url)

        await page.goto(search_url, timeout=15000, wait_until="domcontentloaded")

        # Wait for results to load
        await page.wait_for_selector('article[data-testid="result"], .result', timeout=10000)

        # Small delay to ensure all results are rendered
        await page.wait_for_timeout(500)

        # Extract results - try multiple selectors for compatibility
        result_elements = await page.locator('article[data-testid="result"]').all()

        if not result_elements:
            # Fallback selector for older DuckDuckGo layout
            result_elements = await page.locator('.result:not(.result--ad)').all()

        for element in result_elements[:max_results]:
            try:
                # Skip ads
                is_ad = await element.get_attribute("data-testid")
                if is_ad and "ad" in is_ad.lower():
                    continue

                # Try to find the title link
                link = element.locator('a[data-testid="result-title-a"]').first
                if not await link.count():
                    link = element.locator('a.result__a').first
                if not await link.count():
                    link = element.locator('h2 a').first

                if await link.count():
                    url = await link.get_attribute("href") or ""
                    title = await link.inner_text() or ""

                    # Skip if no valid URL
                    if not url or not url.startswith("http"):
                        continue

                    # Try to get snippet
                    snippet = ""
                    snippet_el = element.locator('[data-testid="result-snippet"]').first
                    if not await snippet_el.count():
                        snippet_el = element.locator('.result__snippet').first
                    if await snippet_el.count():
                        snippet = await snippet_el.inner_text() or ""

                    search_results.append(
                        SearchResult(
                            url=url,
                            title=title.strip(),
                            snippet=snippet.strip(),
                        )
                    )

            except Exception as e:
                logger.debug("Fehler beim Extrahieren eines Ergebnisses: %s", e)
                continue

        logger.info("DuckDuckGo Browser: %s Ergebnisse fuer '%s'", len(search_results), query)
        return search_results

    except PlaywrightTimeout:
        logger.warning("DuckDuckGo Browser Timeout fuer: %s", query)
        return []
    except Exception as e:
        logger.error("DuckDuckGo Browser Fehler: %s", e)
        return []


def search_serpapi(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search using SerpAPI (Google results).

    Requires SERPAPI_KEY environment variable.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        logger.error("SERPAPI_KEY nicht in Umgebungsvariablen gesetzt")
        return []

    try:
        from serpapi import GoogleSearch

        params = {
            "q": query,
            "api_key": api_key,
            "gl": "de",  # Germany
            "hl": "de",  # German language
            "num": max_results,
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        search_results = []
        organic_results = results.get("organic_results", [])

        for r in organic_results[:max_results]:
            search_results.append(
                SearchResult(
                    url=r.get("link", ""),
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                )
            )

        logger.debug("SerpAPI: %s Ergebnisse fuer '%s'", len(search_results), query)
        return search_results

    except ImportError:
        logger.error("google-search-results nicht installiert. Bitte 'pip install google-search-results' ausfuehren.")
        return []
    except Exception as e:
        logger.error("SerpAPI Fehler: %s", e)
        return []


def search_serper(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search using Serper API (Google results, 2500 free searches/month).

    Requires SERPER_API_KEY environment variable.
    Register at https://serper.dev for free API key.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    import requests

    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.error("SERPER_API_KEY nicht in Umgebungsvariablen gesetzt")
        return []

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "gl": "de",  # Germany
        "hl": "de",  # German language
        "num": max_results,
    }

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        search_results = []
        for item in data.get("organic", [])[:max_results]:
            search_results.append(
                SearchResult(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                )
            )

        logger.info("Serper: %s Ergebnisse fuer '%s'", len(search_results), query)
        return search_results

    except requests.exceptions.Timeout:
        logger.error("Serper Timeout fuer: %s", query)
        return []
    except requests.exceptions.HTTPError as e:
        logger.error("Serper HTTP Fehler: %s", e)
        return []
    except Exception as e:
        logger.error("Serper Fehler: %s", e)
        return []


def search_brave(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search using Brave Search API (2000 free searches/month).

    Requires BRAVE_API_KEY environment variable.
    Register at https://api-dashboard.search.brave.com/register for API key.
    Note: Credit card required for verification (not charged on free plan).

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    import requests

    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        logger.error("BRAVE_API_KEY nicht in Umgebungsvariablen gesetzt")
        return []

    headers = {
        "X-Subscription-Token": api_key,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }

    params = {
        "q": query,
        "count": max_results,
        "country": "de",
        "search_lang": "de",
    }

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        search_results = []
        web_results = data.get("web", {}).get("results", [])

        for item in web_results[:max_results]:
            search_results.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                )
            )

        logger.info("Brave: %s Ergebnisse fuer '%s'", len(search_results), query)
        return search_results

    except requests.exceptions.Timeout:
        logger.error("Brave Timeout fuer: %s", query)
        return []
    except requests.exceptions.HTTPError as e:
        logger.error("Brave HTTP Fehler: %s", e)
        return []
    except Exception as e:
        logger.error("Brave Fehler: %s", e)
        return []


def build_search_query(name: str, plz: str, city: str) -> str:
    """Build an optimized search query for finding Steuerberater websites.

    Uses lastname + city + "Steuerberater" for better results.

    Args:
        name: Company or person name
        plz: Postal code
        city: City name

    Returns:
        Optimized search query
    """
    # Extract lastname for better search results
    lastname = extract_lastname(name)

    if lastname:
        # For persons: use lastname + city
        query = f"{lastname} Steuerberater {city}"
    else:
        # For companies: use full name
        # Remove legal suffixes
        clean_name = name
        for suffix in ["GmbH", "PartG", "mbB", "MBB", "Partnerschaft", "Gesellschaft", "mbH"]:
            clean_name = clean_name.replace(suffix, "").strip()
        query = f"{clean_name} {city}"

    return query


def search_website(
    name: str,
    plz: str,
    city: str,
    provider: SearchProvider = SearchProvider.DUCKDUCKGO,
    max_results: int = 5,
) -> list[SearchResult]:
    """Search for a Steuerberater website.

    Args:
        name: Company or person name
        plz: Postal code
        city: City name
        provider: Search provider to use
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    # Build optimized search query
    query = build_search_query(name, plz, city)
    logger.info("Suche: '%s'", query)

    if provider == SearchProvider.SERPER:
        return search_serper(query, max_results)
    elif provider == SearchProvider.BRAVE:
        return search_brave(query, max_results)
    elif provider == SearchProvider.SERPAPI:
        return search_serpapi(query, max_results)
    else:
        return search_duckduckgo(query, max_results)


def filter_directory_urls(
    results: list[SearchResult],
    blacklist: set[str],
) -> list[SearchResult]:
    """Filter out directory URLs from search results.

    Args:
        results: List of search results
        blacklist: Set of blacklisted directory domains

    Returns:
        Filtered list of search results
    """
    filtered = []
    for result in results:
        if is_directory_url(result.url, blacklist):
            logger.debug("Gefiltert (Verzeichnis): %s", result.url)
            continue
        filtered.append(result)

    logger.debug("%s von %s Ergebnissen nach Filterung", len(filtered), len(results))
    return filtered


async def validate_search_result(
    page: Page,
    url: str,
    company_name: str,
    timeout_ms: int = 10000,
) -> WebsiteResult:
    """Validate a search result by visiting the page (legacy function).

    Args:
        page: Playwright page object
        url: URL to validate
        company_name: Company name to search for
        timeout_ms: Request timeout in milliseconds

    Returns:
        WebsiteResult with URL and confidence level
    """
    import re

    search_terms = extract_search_terms(company_name)
    if not search_terms:
        return WebsiteResult(error="Kein gueltiger Firmenname")

    try:
        logger.debug("Validiere: %s", url)
        response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        if not response or response.status >= 400:
            logger.debug("HTTP %s fuer %s", response.status if response else "None", url)
            return WebsiteResult(error=f"HTTP {response.status if response else 'None'}")

        # Get page content
        html_content = await page.content()
        html_lower = html_content.lower()

        # Normalize umlauts in HTML for matching
        for umlaut, replacement in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
            html_lower = html_lower.replace(umlaut, replacement)

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
        logger.info("Niedrige Konfidenz: Name nicht gefunden auf %s", url)
        return WebsiteResult(url=url, confidence=Confidence.LOW)

    except PlaywrightTimeout:
        logger.debug("Timeout fuer %s", url)
        return WebsiteResult(error="Timeout")
    except Exception as e:
        logger.debug("Fehler bei %s: %s", url, e)
        return WebsiteResult(error=str(e))


def extract_lastname(name: str) -> str | None:
    """Extract lastname from a name.

    For persons: Returns the last word (usually the surname).
    Removes titles like Dr., Prof. and legal/professional suffixes.

    Args:
        name: Full name string

    Returns:
        Extracted lastname or None
    """
    # Remove common titles
    titles = ["dr.", "dr", "prof.", "prof", "dipl.", "dipl", "ing.", "ing"]
    name_lower = name.lower().strip()

    for title in titles:
        if name_lower.startswith(title + " "):
            name_lower = name_lower[len(title) + 1:]
        if name_lower.startswith(title + "."):
            name_lower = name_lower[len(title) + 1:]

    # Remove legal and professional suffixes (loop until no more found)
    suffixes = [
        # Legal forms
        "gmbh", "mbh", "partg", "partnerschaft", "gbr", "ohg", "kg",
        "e.k.", "ek", "mbbb", "mbb", "ag", "ug",
        # Professional titles
        "steuerberater", "steuerberaterin", "steuerberatungsgesellschaft",
        "wirtschaftsprüfer", "wirtschaftsprüferin", "wirtschaftsprüfungsgesellschaft",
        "rechtsanwalt", "rechtsanwältin", "rechtsanwälte",
        # Company descriptors
        "verwaltungs", "verwaltungsgesellschaft", "berufsausübungsgesellschaft",
        "treuhand", "treuhandgesellschaft",
    ]

    # Loop until no more suffixes are removed
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if name_lower.endswith(" " + suffix):
                name_lower = name_lower[: -(len(suffix) + 1)]
                changed = True

    words = name_lower.split()
    if not words:
        return None

    # Return the last word as lastname
    lastname = words[-1].strip()

    # Skip if too short or contains dots (like "d.a.b.u.")
    if len(lastname) < 3 or "." in lastname:
        return None

    return lastname


@dataclass
class ValidationScore:
    """Result of the improved validation with scoring."""

    url: str
    impressum_url: str | None
    score: int
    confidence: Confidence
    matches: dict[str, bool]
    error: str | None = None


async def validate_with_impressum(
    page: Page,
    url: str,
    name: str,
    plz: str,
    city: str,
    street: str,
    phone: str,
    mobile: str,
    email: str,
    timeout_ms: int = 10000,
) -> ValidationScore:
    """Validate a search result using Impressum verification.

    Scoring system:
    - Lastname found: +2 points
    - Full name found: +3 points
    - PLZ found: +2 points
    - City found: +1 point
    - Street found: +2 points
    - Phone found: +3 points
    - "Steuerberater" on page: +1 point

    Confidence:
    - HIGH: >= 6 points
    - MEDIUM: 4-5 points
    - LOW: 2-3 points
    - NONE: < 2 points

    Args:
        page: Playwright page object
        url: URL to validate
        name: Full name of the Steuerberater
        plz: Postal code
        city: City name
        street: Street address
        phone: Phone number
        mobile: Mobile number
        email: Email address
        timeout_ms: Request timeout in milliseconds

    Returns:
        ValidationScore with detailed results
    """
    from .impressum_finder import (
        find_impressum_url,
        load_impressum_content,
        normalize_for_comparison,
        search_in_content,
        search_phone_in_content,
    )

    matches: dict[str, bool] = {
        "nachname": False,
        "voller_name": False,
        "plz": False,
        "ort": False,
        "strasse": False,
        "telefon": False,
        "steuerberater": False,
    }

    try:
        # Load the main page
        logger.debug("Validiere mit Impressum: %s", url)
        response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        if not response or response.status >= 400:
            return ValidationScore(
                url=url,
                impressum_url=None,
                score=0,
                confidence=Confidence.NONE,
                matches=matches,
                error=f"HTTP {response.status if response else 'None'}",
            )

        # Get main page content
        main_content = await page.content()
        main_content_lower = normalize_for_comparison(main_content)

        # Find Impressum link
        impressum_url = await find_impressum_url(page, url)

        # Try to load Impressum page
        impressum_content = ""
        if impressum_url:
            impressum_raw = await load_impressum_content(page, impressum_url, timeout_ms)
            if impressum_raw:
                impressum_content = normalize_for_comparison(impressum_raw)
                logger.debug("Impressum geladen: %s", impressum_url)

        # Combine content for searching (Impressum has priority)
        combined_content = impressum_content + " " + main_content_lower

        # Check for construction/placeholder site FIRST
        if is_construction_site(combined_content):
            logger.info("Baustelle erkannt: %s", url)
            return ValidationScore(
                url=url,
                impressum_url=impressum_url,
                score=0,
                confidence=Confidence.CONSTRUCTION,
                matches=matches,
            )

        # Extract lastname
        lastname = extract_lastname(name)

        # Calculate score
        score = 0

        # Check lastname (+2)
        if lastname and search_in_content(combined_content, lastname):
            matches["nachname"] = True
            score += 2
            logger.debug("  Nachname '%s' gefunden (+2)", lastname)

        # Check full name (+3)
        normalized_name = normalize_for_comparison(name)
        # Remove common suffixes for name matching
        for suffix in ["steuerberater", "steuerberaterin", "gmbh", "partg", "mbb"]:
            normalized_name = normalized_name.replace(suffix, "").strip()
        if normalized_name and search_in_content(combined_content, normalized_name):
            matches["voller_name"] = True
            score += 3
            logger.debug("  Voller Name gefunden (+3)")

        # Check PLZ (+2)
        if plz and search_in_content(combined_content, plz):
            matches["plz"] = True
            score += 2
            logger.debug("  PLZ '%s' gefunden (+2)", plz)

        # Check city (+1)
        if city and search_in_content(combined_content, city):
            matches["ort"] = True
            score += 1
            logger.debug("  Ort '%s' gefunden (+1)", city)

        # Check street (+2) - extract just the street name, not the number
        if street:
            street_name = street.split()[0] if street.split() else ""
            if len(street_name) > 3 and search_in_content(combined_content, street_name):
                matches["strasse"] = True
                score += 2
                logger.debug("  Strasse '%s' gefunden (+2)", street_name)

        # Check phone (+3)
        if phone and search_phone_in_content(combined_content, phone):
            matches["telefon"] = True
            score += 3
            logger.debug("  Telefon gefunden (+3)")
        elif mobile and search_phone_in_content(combined_content, mobile):
            matches["telefon"] = True
            score += 3
            logger.debug("  Mobil gefunden (+3)")

        # Check "Steuerberater" (+1)
        if search_in_content(combined_content, "steuerberater"):
            matches["steuerberater"] = True
            score += 1
            logger.debug("  'Steuerberater' gefunden (+1)")

        # Determine confidence based on score
        if score >= 6:
            confidence = Confidence.HIGH
        elif score >= 4:
            confidence = Confidence.MEDIUM
        elif score >= 2:
            confidence = Confidence.LOW
        else:
            confidence = Confidence.NONE

        logger.info(
            "Validierung: %s - Score %d (%s) - Matches: %s",
            url[:50],
            score,
            confidence.value,
            {k: v for k, v in matches.items() if v},
        )

        return ValidationScore(
            url=url,
            impressum_url=impressum_url,
            score=score,
            confidence=confidence,
            matches=matches,
        )

    except PlaywrightTimeout:
        logger.debug("Timeout fuer %s", url)
        return ValidationScore(
            url=url,
            impressum_url=None,
            score=0,
            confidence=Confidence.NONE,
            matches=matches,
            error="Timeout",
        )
    except Exception as e:
        logger.debug("Fehler bei %s: %s", url, e)
        return ValidationScore(
            url=url,
            impressum_url=None,
            score=0,
            confidence=Confidence.NONE,
            matches=matches,
            error=str(e),
        )


def extract_linkedin_url(results: list[SearchResult]) -> str | None:
    """Extract LinkedIn URL from search results without visiting it.

    Finds LinkedIn personal or company profiles in search results.
    This function only extracts URLs - it does NOT visit the LinkedIn page.

    Args:
        results: List of search results

    Returns:
        LinkedIn URL if found, None otherwise
    """
    for result in results:
        url_lower = result.url.lower()
        if "linkedin.com/in/" in url_lower or "linkedin.com/company/" in url_lower:
            logger.debug("LinkedIn gefunden: %s", result.url)
            return result.url
    return None


def is_linkedin_url(url: str) -> bool:
    """Check if a URL is a LinkedIn profile or company page.

    Args:
        url: URL to check

    Returns:
        True if URL is a LinkedIn page
    """
    url_lower = url.lower()
    return "linkedin.com/in/" in url_lower or "linkedin.com/company/" in url_lower
