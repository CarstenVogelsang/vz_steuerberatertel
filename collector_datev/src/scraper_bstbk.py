"""BStBK Scraper.

Scrapes the Bundessteuerberaterkammer Steuerberaterverzeichnis.
URL: https://steuerberaterverzeichnis.berufs-org.de/
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.parser_bstbk import ParsedBStBKEntry, parse_detail_page, parse_search_results

logger = logging.getLogger(__name__)

# Base URL for the BStBK Steuerberaterverzeichnis
BASE_URL = "https://steuerberaterverzeichnis.berufs-org.de/"

# Rate limiting: seconds between requests (erhöht wegen Bot-Protection)
REQUEST_DELAY = 2.5


class BStBKScraper:
    """Scraper for the Bundessteuerberaterkammer Steuerberaterverzeichnis."""

    def __init__(self, page: Page, dry_run: bool = False):
        """Initialize the scraper.

        Args:
            page: Playwright page instance
            dry_run: If True, don't save to database (for testing)
        """
        self.page = page
        self.dry_run = dry_run
        self._request_count = 0

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

    async def scrape_detail_page(self, url: str) -> Optional[ParsedBStBKEntry]:
        """Scrape a single detail page.

        Args:
            url: URL of the detail page

        Returns:
            ParsedBStBKEntry or None if scraping failed
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

            return entry

        except PlaywrightTimeout:
            logger.error(f"Timeout scraping detail page: {url}")
            return None
        except Exception as e:
            logger.error(f"Error scraping detail page {url}: {e}")
            return None

    async def scrape_plz(self, plz: str) -> list[ParsedBStBKEntry]:
        """Scrape all entries for a given PLZ.

        Args:
            plz: The postal code to scrape

        Returns:
            List of parsed entries
        """
        entries = []

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

        # Scrape each detail page
        for i, url in enumerate(detail_urls, 1):
            logger.info(f"Scraping detail page {i}/{len(detail_urls)}")

            entry = await self.scrape_detail_page(url)
            if entry:
                entries.append(entry)

        logger.info(f"Scraped {len(entries)} entries for PLZ: {plz}")
        return entries

    @property
    def request_count(self) -> int:
        """Return the number of requests made."""
        return self._request_count
