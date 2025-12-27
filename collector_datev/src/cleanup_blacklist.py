"""Cleanup-Skript fuer manuell markierte Blacklist-Korrekturen.

Liest Eintraege mit X in Spalte N (Domain_Blacklist) und fuegt
die Website-Domain zur konsolidierten domain_blacklist.txt hinzu.

VERWENDUNG:
    # Alle Tabellenblaetter durchsuchen
    python -m src.cleanup_blacklist

    # Nur Tabellenblatt datev_4
    python -m src.cleanup_blacklist --plz-filter 4

    # Testlauf ohne Aenderungen
    python -m src.cleanup_blacklist --plz-filter 4 --dry-run

SMART-LOGIK:
    Der X-Marker in Spalte N ermittelt die Domain automatisch:
    - Website (Spalte K) vorhanden → Domain aus URL extrahieren
    - Sonst E-Mail (Spalte I) vorhanden → Domain aus E-Mail extrahieren
    - Beides leer → Fehler/ueberspringen
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from .config import load_config
from .plz_filter import get_sheet_index, parse_plz_filter
from .sheets_handler import (
    clear_website_data,
    get_client,
    load_blacklist_corrections,
    open_sheet,
    open_sheet_by_plz_group,
)
from .website_enricher import (
    add_to_blacklist,
    extract_domain,
    extract_domain_from_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Blacklist-Korrektur verarbeiten")
    parser.add_argument(
        "--plz-filter",
        type=str,
        help="PLZ-Filter: Praefix (z.B. '4', '40') oder Bereich (z.B. '40000-41000')",
    )
    parser.add_argument("--sheet-url", type=str, help="Google Sheets URL")
    parser.add_argument("--credentials", type=Path, help="Pfad zur credentials.json")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts aendern")
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def process_worksheet(
    worksheet,
    sheet_name: str,
    plz_filter,
    dry_run: bool,
    stats: dict,
) -> None:
    """Verarbeite ein einzelnes Tabellenblatt fuer Blacklist-Korrekturen.

    Smart-Logik fuer X-Marker in Spalte N (Domain_Blacklist):
    - Website (K) vorhanden → Domain aus URL extrahieren
    - Sonst E-Mail (I) vorhanden → Domain aus E-Mail extrahieren
    """
    logging.info("Verarbeite Tabellenblatt: %s", sheet_name)

    corrections = load_blacklist_corrections(worksheet, plz_filter)
    logging.info("%s Korrekturen gefunden in %s", len(corrections), sheet_name)

    if not corrections:
        return

    for idx, correction in enumerate(corrections, start=1):
        # Smart-Logik: Website hat Vorrang, sonst E-Mail
        if correction.website:
            source = "Website"
            source_value = correction.website
            domain = extract_domain_from_url(correction.website)
        elif correction.email:
            source = "E-Mail"
            source_value = correction.email
            domain = extract_domain(correction.email)
        else:
            logging.warning(
                "[%s/%s] Zeile %s: Keine Website und keine E-Mail vorhanden",
                idx,
                len(corrections),
                correction.row_number,
            )
            stats["errors"] += 1
            continue

        logging.info(
            "[%s/%s] Zeile %s (%s): %s",
            idx,
            len(corrections),
            correction.row_number,
            source,
            source_value,
        )

        if not domain:
            logging.warning("  -> Keine gueltige Domain extrahiert")
            stats["errors"] += 1
            continue

        logging.info("  -> Domain: %s", domain)

        if dry_run:
            logging.info("  -> [DRY-RUN] Wuerde zu domain_blacklist.txt hinzufuegen und Zeile bereinigen")
            stats["processed"] += 1
            continue

        # Zur Blacklist hinzufuegen
        added = add_to_blacklist(domain)

        if added:
            stats["domains_added"] += 1
            logging.info("  -> Zu domain_blacklist.txt hinzugefuegt")
        else:
            stats["domains_existing"] += 1
            logging.info("  -> Bereits in domain_blacklist.txt")

        # Website-Daten im Sheet loeschen (K-P)
        clear_website_data(worksheet, correction.row_number)
        logging.info("  -> Zeile bereinigt (K-P geloescht)")

        stats["processed"] += 1


def main() -> None:
    args = parse_args()
    load_dotenv()
    config = load_config()
    setup_logging(config.log_level)

    plz_filter = None
    sheet_index = None

    if args.plz_filter:
        plz_filter = parse_plz_filter(args.plz_filter)
        sheet_index = get_sheet_index(plz_filter)
        if plz_filter.prefix:
            logging.info("PLZ-Filter: Praefix '%s'", plz_filter.prefix)
        else:
            logging.info("PLZ-Filter: Bereich %s-%s", plz_filter.range_start, plz_filter.range_end)

    # Connect to Google Sheets
    credentials_path = args.credentials or config.credentials_path
    sheet_url = args.sheet_url or config.sheet_url
    client = get_client(credentials_path)

    # Statistics
    stats = {
        "processed": 0,
        "domains_added": 0,
        "domains_existing": 0,
        "errors": 0,
    }

    if sheet_index is not None:
        # Process single worksheet based on PLZ filter
        worksheet = open_sheet_by_plz_group(client, sheet_url, sheet_index)
        process_worksheet(
            worksheet,
            f"datev_{sheet_index}",
            plz_filter,
            args.dry_run,
            stats,
        )
    else:
        # Process ALL worksheets (datev_0 to datev_9)
        logging.info("Kein PLZ-Filter angegeben - durchsuche alle 10 Tabellenblaetter")
        for i in range(10):
            worksheet = open_sheet_by_plz_group(client, sheet_url, i)
            process_worksheet(
                worksheet,
                f"datev_{i}",
                None,
                args.dry_run,
                stats,
            )

    # Print statistics
    logging.info("=" * 60)
    logging.info("STATISTIK")
    logging.info("=" * 60)
    logging.info("Verarbeitet:           %s", stats["processed"])
    logging.info("Domains hinzugefuegt:  %s", stats["domains_added"])
    logging.info("Bereits vorhanden:     %s", stats["domains_existing"])
    logging.info("Fehler:                %s", stats["errors"])


if __name__ == "__main__":
    main()
