from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from src.config import Config, load_config
from src.excel_handler import get_progress_stats, load_pending_locations, update_plz_status
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

DEFAULT_EXCEL_PATH = Path("data/plz_de.xlsx")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Steuerberater.tel Scraper")
    parser.add_argument("--plz-file", type=Path, help="Pfad zur PLZ CSV")
    parser.add_argument("--excel", type=Path, nargs="?", const=DEFAULT_EXCEL_PATH, help="Excel-Modus mit PLZ-Datei")
    parser.add_argument("--max-locations", type=int, help="Maximale Anzahl Orte (nur Excel-Modus)")
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
    parser.add_argument("--stats", action="store_true", help="Zeige Excel-Statistiken")
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


async def run_excel_mode(args: argparse.Namespace, config: Config) -> None:
    """Run scraper in Excel mode with status tracking."""
    from playwright.async_api import async_playwright

    excel_path = args.excel
    plz_filter: PlzFilter | None = None
    sheet_index: int | None = None

    if args.plz_filter:
        plz_filter = parse_plz_filter(args.plz_filter)
        sheet_index = get_sheet_index(plz_filter)
        if plz_filter.prefix:
            logging.info("PLZ-Filter: Praefix '%s'", plz_filter.prefix)
        else:
            logging.info("PLZ-Filter: Bereich %s-%s", plz_filter.range_start, plz_filter.range_end)

    logging.info("Excel-Modus: %s", excel_path)

    locations = load_pending_locations(excel_path, plz_filter)
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

                        update_plz_status(
                            excel_path,
                            plz_entry.row_number,
                            added,  # Only count actually added entries
                            result.error,
                        )

                    all_entries.extend(result.entries)
                    await asyncio.sleep(config.rate_limit_sec)

        finally:
            await browser.close()

    logging.info("Gesamt %s Eintraege gesammelt, %s Duplikate uebersprungen", len(all_entries), total_duplicates)


def main() -> None:
    args = parse_args()
    load_dotenv()
    config = build_config(args)
    setup_logging(config.log_level)

    if args.stats:
        excel_path = args.excel or DEFAULT_EXCEL_PATH
        stats = get_progress_stats(excel_path)
        print(f"Excel-Statistiken fuer {excel_path}:")
        print(f"  Gesamt PLZ:     {stats['total']}")
        print(f"  Verarbeitet:    {stats['processed']}")
        print(f"  Ausstehend:     {stats['pending']}")
        print(f"  Mit Fehlern:    {stats['errors']}")
        return

    if args.excel:
        asyncio.run(run_excel_mode(args, config))
        return

    scraper = SteuerberaterScraper(config)
    entries = asyncio.run(scraper.run())

    logging.info("Gesamt %s Eintraege gesammelt", len(entries))

    if args.dry_run:
        return

    client = get_client(config.credentials_path)
    worksheet = open_sheet(client, config.sheet_url)

    if args.init_headers:
        if ensure_headers(worksheet):
            logging.info("Header-Zeile gesetzt")
        else:
            logging.info("Header-Zeile bereits vorhanden")

    written = append_entries(worksheet, entries)
    logging.info("%s Eintraege in Google Sheets geschrieben", written)


if __name__ == "__main__":
    main()
