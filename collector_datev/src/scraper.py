from __future__ import annotations

import asyncio
import csv
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from playwright.async_api import Browser, Page, async_playwright

from .config import Config
from .parser import ParsedEntry, parse_entry


@dataclass
class ScrapeResult:
    """Result of scraping a single PLZ."""

    plz: str
    entries: list[ParsedEntry]
    error: str | None = None


RESULT_SELECTORS = [
    "table table tr",  # Nested table rows contain individual entries
    "#searchResult .result",
    "#ergebnisliste .result",
    ".resultlist .result",
    "#searchResult li",
    "#ergebnisliste li",
]


class SteuerberaterScraper:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._seen_keys: set[str] = set()

    def load_plz_list(self, path: Path) -> list[str]:
        if not path.exists():
            raise FileNotFoundError(f"PLZ-Datei nicht gefunden: {path}")

        plz_list: list[str] = []
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row:
                    continue
                plz = row[0].strip()
                if plz:
                    plz_list.append(plz)

        if self.config.max_plz:
            return plz_list[: self.config.max_plz]

        return plz_list

    async def run(self) -> list[ParsedEntry]:
        entries: list[ParsedEntry] = []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.config.headless)
            page = await browser.new_page()

            try:
                plz_list = self.load_plz_list(self.config.input_csv_path)
                total = len(plz_list)
                self.logger.info("%s PLZ geladen", total)

                for index, plz in enumerate(plz_list, start=1):
                    self.logger.info("[%s/%s] Suche PLZ: %s", index, total, plz)
                    new_entries = await self.scrape_plz(page, plz)
                    entries.extend(new_entries)
                    self.logger.info("%s Eintraege gefunden", len(new_entries))
                    await asyncio.sleep(self.config.rate_limit_sec)
            finally:
                await browser.close()

        return entries

    async def scrape_plz(self, page: Page, plz: str) -> list[ParsedEntry]:
        result = await self.scrape_plz_with_status(page, plz)
        return result.entries

    async def scrape_plz_with_status(self, page: Page, plz: str) -> ScrapeResult:
        """Scrape a single PLZ and return result with error info."""
        for attempt in range(1, self.config.max_retries + 1):
            try:
                await page.goto(self.config.start_url, timeout=self.config.timeout_ms)
                await self._fill_plz_and_submit(page, plz)
                await page.wait_for_timeout(500)

                blocks = await self._extract_result_blocks(page)
                if not blocks:
                    self.logger.warning("Keine Ergebnisse fuer PLZ %s", plz)
                    return ScrapeResult(plz=plz, entries=[])

                parsed: list[ParsedEntry] = []
                for block in blocks:
                    entry = parse_entry(block)
                    if not entry.name:
                        continue
                    if self._is_duplicate(entry):
                        continue
                    parsed.append(entry)

                return ScrapeResult(plz=plz, entries=parsed)
            except Exception as exc:  # noqa: BLE001 - coarse retry by design
                self.logger.warning("Fehler bei PLZ %s (Versuch %s): %s", plz, attempt, exc)
                if attempt >= self.config.max_retries:
                    return ScrapeResult(plz=plz, entries=[], error=str(exc))
                await asyncio.sleep(1)

        return ScrapeResult(plz=plz, entries=[], error="Max retries exceeded")

    def _is_duplicate(self, entry: ParsedEntry) -> bool:
        key = f"{entry.name}|{entry.street}|{entry.plz}|{entry.city}".lower()
        if key in self._seen_keys:
            return True
        self._seen_keys.add(key)
        return False

    async def _fill_plz_and_submit(self, page: Page, plz: str) -> None:
        await page.wait_for_load_state("domcontentloaded")

        plz_input = page.locator("input[name='editPLZ']")
        await plz_input.fill("")
        await plz_input.fill(plz)

        submit_button = page.locator("input[name='btnSuch_Suchen']").first
        await submit_button.click()
        await page.wait_for_selector("text=Zuständige Berufskammer", timeout=self.config.timeout_ms)

    async def _extract_result_blocks(self, page: Page) -> list[str]:
        for selector in RESULT_SELECTORS:
            locator = page.locator(selector)
            if await locator.count() > 0:
                return await locator.all_inner_texts()

        locator = page.locator("xpath=//div[.//text()[contains(., 'Zuständige Berufskammer')]]")
        if await locator.count() > 0:
            return await locator.all_inner_texts()

        return []


def flatten_entries(entries: Iterable[ParsedEntry]) -> list[dict[str, str]]:
    return [asdict(entry) for entry in entries]
