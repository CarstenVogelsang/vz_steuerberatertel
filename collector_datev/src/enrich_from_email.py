"""Website enrichment script for Steuerberater entries.

Stage 1: Extract websites from email domains.

VERWENDUNG:
    # Mit PLZ-Praefix
    python -m src.enrich_from_email --plz-filter 4 --headless

    # Mit PLZ-Bereich
    python -m src.enrich_from_email --plz-filter 47500-48000 --dry-run

    # Limitiert auf N Eintraege
    python -m src.enrich_from_email --plz-filter 4 --max-entries 10
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .config import Config, load_config
from .plz_filter import get_sheet_index, parse_plz_filter
from .sheets_handler import (
    get_client,
    load_entries_for_enrichment,
    open_sheet,
    open_sheet_by_plz_group,
    update_website_data,
)
from .website_enricher import (
    Confidence,
    enrich_website_from_email,
    load_blacklist,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Website-Anreicherung fuer Steuerberater")
    parser.add_argument(
        "--plz-filter",
        type=str,
        help="PLZ-Filter: Praefix (z.B. '4', '40') oder Bereich (z.B. '40000-41000')",
    )
    parser.add_argument("--sheet-url", type=str, help="Google Sheets URL")
    parser.add_argument("--credentials", type=Path, help="Pfad zur credentials.json")
    parser.add_argument("--headless", action="store_true", help="Headless ausfuehren")
    parser.add_argument("--rate-limit", type=float, default=2.5, help="Pause zwischen Requests in Sekunden")
    parser.add_argument("--max-entries", type=int, help="Maximale Anzahl Eintraege")
    parser.add_argument("--dry-run", action="store_true", help="Nur pruefen, nichts schreiben")
    parser.add_argument("--timeout", type=int, default=10000, help="Timeout fuer Website-Requests in ms")
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run_enrichment(args: argparse.Namespace, config: Config) -> None:
    """Run website enrichment."""
    from playwright.async_api import async_playwright

    plz_filter = None
    sheet_index = None

    if args.plz_filter:
        plz_filter = parse_plz_filter(args.plz_filter)
        sheet_index = get_sheet_index(plz_filter)
        if plz_filter.prefix:
            logging.info("PLZ-Filter: Praefix '%s'", plz_filter.prefix)
        else:
            logging.info("PLZ-Filter: Bereich %s-%s", plz_filter.range_start, plz_filter.range_end)

    # Load blacklist
    blacklist = load_blacklist()
    logging.info("%s Domains in Blacklist", len(blacklist))

    # Connect to Google Sheets
    credentials_path = args.credentials or config.credentials_path
    sheet_url = args.sheet_url or config.sheet_url
    client = get_client(credentials_path)

    if sheet_index is not None:
        worksheet = open_sheet_by_plz_group(client, sheet_url, sheet_index)
        logging.info("Tabellenblatt: datev_%s", sheet_index)
    else:
        worksheet = open_sheet(client, sheet_url)

    # Load entries needing enrichment
    logging.info("Lade Eintraege zur Anreicherung...")
    entries = load_entries_for_enrichment(worksheet, plz_filter)

    if args.max_entries:
        entries = entries[: args.max_entries]

    logging.info("%s Eintraege zu verarbeiten", len(entries))

    if not entries:
        logging.info("Keine Eintraege zur Anreicherung gefunden")
        return

    # Statistics
    stats = {
        "processed": 0,
        "websites_found": 0,
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "blacklisted": 0,
        "not_reachable": 0,
    }

    headless = args.headless or config.headless
    today = datetime.now().strftime("%Y-%m-%d")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        # Ignore HTTPS errors to catch construction sites with invalid certificates
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = await context.new_page()

        try:
            for idx, entry in enumerate(entries, start=1):
                logging.info(
                    "[%s/%s] %s (%s)",
                    idx,
                    len(entries),
                    entry.name[:50],
                    entry.email,
                )

                result = await enrich_website_from_email(
                    page=page,
                    email=entry.email,
                    company_name=entry.name,
                    blacklist=blacklist,
                    timeout_ms=args.timeout,
                )

                stats["processed"] += 1

                if result.error:
                    if "blacklisted" in result.error:
                        stats["blacklisted"] += 1
                        logging.info("  -> Blacklisted")
                    else:
                        stats["not_reachable"] += 1
                        logging.info("  -> %s", result.error)

                    if not args.dry_run:
                        update_website_data(
                            worksheet,
                            entry.row_number,
                            None,
                            today,
                            Confidence.NONE.value,
                            source="email",
                        )
                else:
                    stats["websites_found"] += 1

                    if result.confidence == Confidence.HIGH:
                        stats["high_confidence"] += 1
                    elif result.confidence == Confidence.MEDIUM:
                        stats["medium_confidence"] += 1
                    else:
                        stats["low_confidence"] += 1

                    logging.info(
                        "  -> %s (%s)",
                        result.url,
                        result.confidence.value,
                    )

                    if not args.dry_run:
                        update_website_data(
                            worksheet,
                            entry.row_number,
                            result.url,
                            today,
                            result.confidence.value,
                            source="email",
                        )

                await asyncio.sleep(args.rate_limit)

        finally:
            await browser.close()

    # Print statistics
    logging.info("=" * 60)
    logging.info("STATISTIK")
    logging.info("=" * 60)
    logging.info("Verarbeitet:         %s", stats["processed"])
    logging.info("Websites gefunden:   %s", stats["websites_found"])
    logging.info("  - Hohe Konfidenz:  %s", stats["high_confidence"])
    logging.info("  - Mittlere:        %s", stats["medium_confidence"])
    logging.info("  - Niedrige:        %s", stats["low_confidence"])
    logging.info("Blacklisted:         %s", stats["blacklisted"])
    logging.info("Nicht erreichbar:    %s", stats["not_reachable"])


def main() -> None:
    args = parse_args()
    load_dotenv()
    config = load_config()
    setup_logging(config.log_level)

    asyncio.run(run_enrichment(args, config))


if __name__ == "__main__":
    main()
