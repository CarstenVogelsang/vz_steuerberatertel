from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from src.config import Config, load_config
from src.plz_filter import PlzFilter, get_sheet_index, parse_plz_filter
from src.scraper import SteuerberaterScraper
from src.sheets_handler import (
    append_entries,
    append_entries_with_dedup,
    ensure_headers,
    get_client,
    load_existing_keys,
    open_sheet,
    open_sheet_by_plz_group,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Steuerberater.tel Scraper")
    parser.add_argument("--plz-file", type=Path, help="Pfad zur PLZ CSV (Legacy-Modus)")
    parser.add_argument("--max-locations", type=int, help="Maximale Anzahl Orte")
    parser.add_argument(
        "--plz-filter",
        type=str,
        help="PLZ-Filter: Praefix (z.B. '4', '40') oder Bereich (z.B. '40000-41000')",
    )
    parser.add_argument("--sheet-url", type=str, help="Google Sheets URL")
    parser.add_argument("--credentials", type=Path, help="Pfad zur credentials.json")
    parser.add_argument("--headless", action="store_true", help="Headless ausfuehren")
    parser.add_argument("--rate-limit", type=float, help="Pause zwischen PLZ in Sekunden")
    parser.add_argument("--max-plz", type=int, help="Maximale Anzahl PLZ")
    parser.add_argument("--dry-run", action="store_true", help="Nur scrapen, nichts schreiben")
    parser.add_argument("--init-headers", action="store_true", help="Header-Zeile im Sheet setzen")
    parser.add_argument("--stats", action="store_true", help="Zeige PLZ-Statistiken aus DB")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    config = load_config()

    if args.plz_file:
        config = replace(config, input_csv_path=args.plz_file)
    if args.sheet_url:
        config = replace(config, sheet_url=args.sheet_url)
    if args.credentials:
        config = replace(config, credentials_path=args.credentials)
    if args.headless:
        config = replace(config, headless=True)
    if args.rate_limit is not None:
        config = replace(config, rate_limit_sec=args.rate_limit)
    if args.max_plz is not None:
        config = replace(config, max_plz=args.max_plz)

    return config


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run_db_mode(args: argparse.Namespace, config: Config) -> None:
    """Run scraper with SQLite-based progress tracking."""
    from playwright.async_api import async_playwright

    # Import PLZ handler (requires Flask app context)
    from src.plz_handler import load_pending_locations, update_plz_status

    plz_filter: PlzFilter | None = None
    sheet_index: int | None = None

    if args.plz_filter:
        plz_filter = parse_plz_filter(args.plz_filter)
        sheet_index = get_sheet_index(plz_filter)
        if plz_filter.prefix:
            logging.info("PLZ-Filter: Praefix '%s'", plz_filter.prefix)
        else:
            logging.info("PLZ-Filter: Bereich %s-%s", plz_filter.range_start, plz_filter.range_end)

    logging.info("DB-Modus: Lade PLZ aus SQLite...")

    locations = load_pending_locations(plz_filter)
    if args.max_locations:
        locations = locations[: args.max_locations]

    total_locations = len(locations)
    total_plz = sum(len(loc.entries) for loc in locations)
    logging.info("%s Orte mit %s PLZ zu verarbeiten", total_locations, total_plz)

    if total_plz == 0:
        logging.info("Keine unverarbeiteten PLZ gefunden")
        return

    scraper = SteuerberaterScraper(config)
    all_entries = []
    total_duplicates = 0

    worksheet = None
    existing_keys: set[str] = set()
    if not args.dry_run:
        client = get_client(config.credentials_path)
        if sheet_index is not None:
            worksheet = open_sheet_by_plz_group(client, config.sheet_url, sheet_index)
            logging.info("Tabellenblatt: datev_%s", sheet_index)
        else:
            worksheet = open_sheet(client, config.sheet_url)
        if args.init_headers:
            ensure_headers(worksheet)
        # Load existing keys for duplicate detection
        logging.info("Lade bestehende Eintraege fuer Duplikat-Pruefung...")
        existing_keys = load_existing_keys(worksheet)
        logging.info("%s bestehende Eintraege geladen", len(existing_keys))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=config.headless)
        page = await browser.new_page()

        try:
            for loc_idx, location in enumerate(locations, start=1):
                logging.info(
                    "[Ort %s/%s] %s (%s PLZ)",
                    loc_idx,
                    total_locations,
                    location.city,
                    len(location.entries),
                )

                for plz_entry in location.entries:
                    result = await scraper.scrape_plz_with_status(page, plz_entry.plz)
                    count = len(result.entries)

                    logging.info(
                        "  PLZ %s: %s Eintraege%s",
                        plz_entry.plz,
                        count,
                        f" (Fehler: {result.error})" if result.error else "",
                    )

                    if not args.dry_run:
                        added = 0
                        duplicates = 0
                        if result.entries and worksheet:
                            added, duplicates = append_entries_with_dedup(
                                worksheet, result.entries, existing_keys
                            )
                            total_duplicates += duplicates
                            if duplicates > 0:
                                logging.info("    -> %s neu, %s Duplikate", added, duplicates)

                        # Update PLZ status in SQLite (row_number is actually DB id)
                        update_plz_status(
                            plz_entry.row_number,
                            added,  # Only count actually added entries
                            result.error,
                        )

                    all_entries.extend(result.entries)
                    await asyncio.sleep(config.rate_limit_sec)

        finally:
            await browser.close()

    logging.info("Gesamt %s Eintraege gesammelt, %s Duplikate uebersprungen", len(all_entries), total_duplicates)


def create_app():
    """Create Flask app for database access."""
    from app import create_app
    return create_app()


def main() -> None:
    args = parse_args()
    load_dotenv()
    config = build_config(args)
    setup_logging(config.log_level)

    # Create Flask app for database access
    app = create_app()

    with app.app_context():
        if args.stats:
            from src.plz_handler import get_progress_stats
            stats = get_progress_stats()
            print("PLZ-Statistiken aus Datenbank:")
            print(f"  Gesamt PLZ:     {stats['total']}")
            print(f"  Verarbeitet:    {stats['processed']}")
            print(f"  Ausstehend:     {stats['pending']}")
            print(f"  Mit Fehlern:    {stats['errors']}")
            return

        # Default: Run in DB mode with progress tracking
        asyncio.run(run_db_mode(args, config))


if __name__ == "__main__":
    main()
