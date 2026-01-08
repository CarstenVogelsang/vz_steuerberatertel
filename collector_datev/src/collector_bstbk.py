"""BStBK Collector.

Collects data from the Bundessteuerberaterkammer Steuerberaterverzeichnis.
URL: https://steuerberaterverzeichnis.berufs-org.de/
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.parser_bstbk import ParsedBStBKEntry, parse_detail_page, parse_search_results

# Import DebugUI only when needed (to avoid circular imports)
TYPE_CHECKING = False
if TYPE_CHECKING:
    from src.debug_ui import DebugUI

logger = logging.getLogger(__name__)

# Base URL for the BStBK Steuerberaterverzeichnis
BASE_URL = "https://steuerberaterverzeichnis.berufs-org.de/"

# Rate limiting: seconds between requests (erhöht wegen Bot-Protection)
REQUEST_DELAY = 2.5

# Debug output directory
DEBUG_HTML_DIR = Path("data/debug_html")


class BStBKCollector:
    """Collector for the Bundessteuerberaterkammer Steuerberaterverzeichnis."""

    def __init__(
        self,
        page: Page,
        dry_run: bool = False,
        debug: bool = False,
        debug_ui: "DebugUI" = None,
        name_filter: str = None,
    ):
        """Initialize the collector.

        Args:
            page: Playwright page instance
            dry_run: If True, don't save to database (for testing)
            debug: If True, enable interactive terminal debug mode
            debug_ui: Optional DebugUI instance for web-based debugging
            name_filter: Only show entries whose name contains this text (case-insensitive)
        """
        self.page = page
        self.dry_run = dry_run
        self.debug = debug
        self.debug_ui = debug_ui
        self.name_filter = name_filter
        self._request_count = 0
        self._debug_counter = 0
        self._current_plz: Optional[str] = None
        self._filtered_count = 0  # Track filtered entries

        # Create debug directory if needed
        if debug:
            DEBUG_HTML_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Debug-Modus aktiviert. HTML wird gespeichert in: {DEBUG_HTML_DIR}")

    def _save_debug_html(self, html: str, url: str, entry: Optional[ParsedBStBKEntry]) -> Path:
        """Save HTML content for debugging.

        Args:
            html: The HTML content
            url: The source URL
            entry: The parsed entry (if any)

        Returns:
            Path to the saved file
        """
        self._debug_counter += 1
        timestamp = datetime.now().strftime("%H%M%S")

        # Create meaningful filename
        parsed_url = urlparse(url)
        url_part = parsed_url.path.replace("/", "_")[:30]

        filename = f"{self._debug_counter:03d}_{timestamp}{url_part}.html"
        filepath = DEBUG_HTML_DIR / filename

        # Add debug info as HTML comment at the top
        debug_info = f"""<!--
DEBUG INFO
==========
URL: {url}
Timestamp: {datetime.now().isoformat()}
Counter: {self._debug_counter}

Parsed Entry:
- Kanzlei: {entry.kanzlei.name if entry else 'N/A'}
- PLZ/Ort: {entry.kanzlei.plz} {entry.kanzlei.ort if entry else 'N/A'}
- Ist Einzelperson: {entry.is_einzelperson if entry else 'N/A'}
- Steuerberater Anzahl: {len(entry.steuerberater) if entry else 'N/A'}
-->

"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(debug_info + html)

        return filepath

    def _show_debug_info(self, entry: Optional[ParsedBStBKEntry], html_path: Path):
        """Show debug information and wait for user input.

        Args:
            entry: The parsed entry
            html_path: Path to the saved HTML file
        """
        print("\n" + "=" * 60)
        print("🔍 DEBUG MODE - Detailseite verarbeitet")
        print("=" * 60)

        if entry:
            print(f"📋 Kanzlei:        {entry.kanzlei.name}")
            print(f"📍 PLZ/Ort:        {entry.kanzlei.plz} {entry.kanzlei.ort}")
            print(f"👤 Einzelperson:   {'Ja' if entry.is_einzelperson else 'Nein'}")
            print(f"👥 Steuerberater:  {len(entry.steuerberater)}")

            if entry.steuerberater:
                print("   Gefundene Steuerberater:")
                for stb in entry.steuerberater:
                    name = f"{stb.vorname} {stb.nachname}" if stb.vorname else stb.nachname
                    safe_id = f"(Safe ID: {stb.safe_id[:20]}...)" if stb.safe_id else "(keine Safe ID)"
                    print(f"   - {name} {safe_id}")
            else:
                print("   (Keine Steuerberater extrahiert)")
        else:
            print("❌ Parsing fehlgeschlagen - kein Ergebnis")

        print(f"\n📄 HTML gespeichert: {html_path}")
        print("-" * 60)
        print("Drücke ENTER um fortzufahren, 'q' + ENTER zum Abbrechen...")

        user_input = input()
        if user_input.lower() == 'q':
            raise KeyboardInterrupt("Debug-Modus vom Benutzer abgebrochen")

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        await asyncio.sleep(REQUEST_DELAY)
        self._request_count += 1

    async def navigate_to_search(self) -> bool:
        """Navigate to the search page.

        Returns:
            True if navigation was successful
        """
        try:
            await self.page.goto(BASE_URL, wait_until="networkidle")
            logger.info(f"Navigated to {BASE_URL}")
            return True
        except PlaywrightTimeout:
            logger.error(f"Timeout navigating to {BASE_URL}")
            return False

    async def search_plz(self, plz: str) -> bool:
        """Enter PLZ and submit search.

        Args:
            plz: The postal code to search for

        Returns:
            True if search was submitted successfully
        """
        try:
            # Find and fill PLZ input field
            plz_input = self.page.locator("#plz-text")
            await plz_input.fill(plz)
            logger.debug(f"Filled PLZ: {plz}")

            # Find and click submit button
            submit_btn = self.page.locator('input[type="submit"]')
            await submit_btn.click()

            # Wait for results page to load
            await self.page.wait_for_load_state("networkidle")
            await self._rate_limit()

            logger.info(f"Search submitted for PLZ: {plz}")
            return True

        except PlaywrightTimeout:
            logger.error(f"Timeout during search for PLZ: {plz}")
            return False
        except Exception as e:
            logger.error(f"Error during search for PLZ {plz}: {e}")
            return False

    async def get_detail_urls(self) -> list[str]:
        """Extract all detail page URLs from search results.

        Returns:
            List of absolute URLs to detail pages
        """
        try:
            html = await self.page.content()
            relative_urls = parse_search_results(html)

            # Convert to absolute URLs
            absolute_urls = [urljoin(BASE_URL, url) for url in relative_urls]

            logger.info(f"Found {len(absolute_urls)} detail page URLs")
            return absolute_urls

        except Exception as e:
            logger.error(f"Error extracting detail URLs: {e}")
            return []

    async def collect_detail_page(self, url: str) -> Optional[ParsedBStBKEntry]:
        """Collect data from a single detail page.

        Args:
            url: URL of the detail page

        Returns:
            ParsedBStBKEntry or None if collection failed (or skipped by user)
        """
        try:
            await self.page.goto(url, wait_until="networkidle")
            await self._rate_limit()

            html = await self.page.content()
            entry = parse_detail_page(html)

            if entry:
                stb_count = len(entry.steuerberater)
                logger.debug(
                    f"Parsed: {entry.kanzlei.name} ({stb_count} Steuerberater)"
                )

                # Apply name filter before showing in Debug UI
                if self.name_filter:
                    name = entry.kanzlei.name if entry.kanzlei else ""
                    if self.name_filter.lower() not in name.lower():
                        self._filtered_count += 1
                        logger.debug(f"Übersprungen (Name-Filter): {name}")
                        return None  # Skip this entry entirely

            # Debug UI mode: show in web interface and wait for user action
            if self.debug_ui:
                action = self.debug_ui.show_entry(
                    url=url,
                    entry=entry,
                    plz=self._current_plz,
                    is_success=entry is not None,
                )
                if action == "stop":
                    raise KeyboardInterrupt("Vom Benutzer in Debug-UI gestoppt")
                elif action == "skip":
                    logger.info(f"Eintrag übersprungen: {url}")
                    return None  # Skip this entry

            # Terminal debug mode: save HTML and show interactive info
            elif self.debug:
                html_path = self._save_debug_html(html, url, entry)
                self._show_debug_info(entry, html_path)

            return entry

        except PlaywrightTimeout:
            logger.error(f"Timeout collecting detail page: {url}")
            return None
        except KeyboardInterrupt:
            raise  # Re-raise to stop the collector
        except Exception as e:
            logger.error(f"Error collecting detail page {url}: {e}")
            return None

    async def collect_plz(self, plz: str) -> list[ParsedBStBKEntry]:
        """Collect all entries for a given PLZ.

        Args:
            plz: The postal code to collect

        Returns:
            List of parsed entries
        """
        entries = []

        # Track current PLZ for debug UI
        self._current_plz = plz

        # Navigate to search page
        if not await self.navigate_to_search():
            return entries

        # Submit search
        if not await self.search_plz(plz):
            return entries

        # Get all detail page URLs
        detail_urls = await self.get_detail_urls()

        if not detail_urls:
            logger.info(f"No results found for PLZ: {plz}")
            return entries

        # Collect each detail page
        for i, url in enumerate(detail_urls, 1):
            logger.info(f"Collecting detail page {i}/{len(detail_urls)}")

            entry = await self.collect_detail_page(url)
            if entry:
                entries.append(entry)

        if self.name_filter and self._filtered_count > 0:
            logger.info(f"Collected {len(entries)} entries for PLZ: {plz} ({self._filtered_count} durch Filter übersprungen)")
        else:
            logger.info(f"Collected {len(entries)} entries for PLZ: {plz}")
        return entries

    @property
    def request_count(self) -> int:
        """Return the number of requests made."""
        return self._request_count
