#!/usr/bin/env python3
"""BStBK Collector Entry Point.

Collects data from the Bundessteuerberaterkammer Steuerberaterverzeichnis
and stores results in SQLite database.

Usage:
    python main_bstbk.py [OPTIONS]

Options:
    --plz-filter TEXT   Only process PLZ starting with this prefix (e.g., "4")
    --headless          Run browser in headless mode
    --dry-run           Don't save to database
    --max-plz INT       Maximum number of PLZ to process
    --verbose           Enable debug logging
    --use-ai            Enable AI-assisted matching for uncertain cases (Score=1)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from playwright.async_api import async_playwright

# Add parent directory to path for imports
sys.path.insert(0, ".")

from app import create_app, db
from app.models import Kammer, Kanzlei, Plz, PlzCollector, Rechtsform, Steuerberater
from src.collector_bstbk import BStBKCollector
from src.matcher import match_steuerberater_to_kanzleien

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

COLLECTOR_TYPE = "bstbk"


def save_entry(entry) -> tuple[int, int]:
    """Save a parsed entry to the database.

    Args:
        entry: ParsedBStBKEntry to save

    Returns:
        Tuple of (kanzleien_created, steuerberater_created)
    """
    kanzleien_created = 0
    steuerberater_created = 0

    # Get or create Kammer (returns just the object, not a tuple)
    kammer = None
    if entry.kanzlei.kammer_name:
        kammer = Kammer.get_or_create(entry.kanzlei.kammer_name)

    # Get or create Rechtsform (returns just the object, not a tuple)
    rechtsform = None
    if entry.kanzlei.rechtsform:
        rechtsform = Rechtsform.get_or_create(entry.kanzlei.rechtsform)

    # Get or create Kanzlei
    kanzlei, created = Kanzlei.get_or_create(
        name=entry.kanzlei.name,
        plz=entry.kanzlei.plz,
        ort=entry.kanzlei.ort,
        strasse=entry.kanzlei.strasse,
        telefon=entry.kanzlei.telefon,
        fax=entry.kanzlei.fax,
        email=entry.kanzlei.email,
        website=entry.kanzlei.website,
        rechtsform_id=rechtsform.id if rechtsform else None,
        kammer_id=kammer.id if kammer else None,
    )

    if created:
        kanzleien_created += 1

    # Create Steuerberater
    for stb in entry.steuerberater:
        # VALIDIERUNG: Nachname muss vorhanden sein
        if not stb.nachname or not stb.nachname.strip():
            logger.warning(f"Steuerberater ohne Nachname übersprungen (Kanzlei: {entry.kanzlei.name})")
            continue

        try:
            _, created = Steuerberater.create_or_update(
                safe_id=stb.safe_id,
                nachname=stb.nachname,
                kanzlei_id=kanzlei.id,
                vorname=stb.vorname,
                titel=stb.titel,
                email=stb.email,
                mobil=stb.mobil,
                bestelldatum=stb.bestelldatum,
            )
            if created:
                steuerberater_created += 1
        except Exception as e:
            logger.error(f"Fehler beim Speichern von Steuerberater {stb.nachname}: {e}")
            continue

    return kanzleien_created, steuerberater_created


async def main(
    plz_filter: str = None,
    headless: bool = False,
    dry_run: bool = False,
    max_plz: int = None,
    verbose: bool = False,
    debug: bool = False,
    debug_ui: bool = False,
    name_filter: str = None,
    use_ai: bool = False,
):
    """Main entry point for BStBK scraper.

    Args:
        plz_filter: Only process PLZ starting with this prefix
        headless: Run browser in headless mode
        dry_run: Don't save to database
        max_plz: Maximum number of PLZ to process
        verbose: Enable debug logging
        debug: Enable interactive terminal debug mode (pause after each detail page)
        debug_ui: Enable web-based debug UI on port 5005
        name_filter: Only show entries whose name contains this text (case-insensitive)
        use_ai: Enable AI-assisted matching for Score=1 cases via OpenRouter
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 60)
    print("🏛️  BSTBK COLLECTOR - Steuerberaterverzeichnis")
    print("=" * 60)
    print(f"Modus:        {'Dry-Run' if dry_run else 'Live'}")
    print(f"Headless:     {'Ja' if headless else 'Nein'}")
    print(f"KI-Matching:  {'Ja' if use_ai else 'Nein'}")
    if debug:
        print(f"Debug:        Ja (Terminal-Modus)")
    if debug_ui:
        print(f"Debug-UI:     Ja (Port 5005)")
    if plz_filter:
        print(f"PLZ-Filter:   {plz_filter}*")
    if name_filter:
        print(f"Name-Filter:  \"{name_filter}\"")
    if max_plz:
        print(f"Max PLZ:      {max_plz}")
    print()

    # Initialize Debug UI if requested
    debug_ui_instance = None
    if debug_ui:
        from src.debug_ui import DebugUI
        debug_ui_instance = DebugUI(port=5005)
        debug_ui_instance.start()

        # Open browser automatically
        import webbrowser
        webbrowser.open("http://localhost:5005")

    # Create Flask app context
    app = create_app()
    with app.app_context():
        # Get PLZ list from reference table (on-demand approach)
        # PLZ-Collector entries are created when processing, not pre-initialized
        plz_query = Plz.query.order_by(Plz.plz)

        if plz_filter:
            plz_query = plz_query.filter(Plz.plz.startswith(plz_filter))

        all_plz = plz_query.all()

        if not all_plz:
            print("❌ Keine PLZ in der Datenbank gefunden.")
            print("   Führe 'flask import-plz' aus, um PLZ zu importieren.")
            return

        # Filter out already processed PLZ
        pending_plz = []
        for plz_entry in all_plz:
            # Check if already processed in plz_collector
            collector_entry = PlzCollector.query.filter_by(
                plz=plz_entry.plz,
                collector_type=COLLECTOR_TYPE,
            ).first()

            if collector_entry and collector_entry.processed_at:
                # Already processed, skip
                continue

            pending_plz.append(plz_entry)

            if max_plz and len(pending_plz) >= max_plz:
                break

        if not pending_plz:
            print("✅ Alle PLZ wurden bereits verarbeitet.")
            return

        total_plz = len(pending_plz)
        print(f"📍 {total_plz} PLZ zu verarbeiten")
        print()

        # Stats
        total_kanzleien = 0
        total_steuerberater = 0
        processed_plz = 0
        failed_plz = 0

        # Start Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()

            collector = BStBKCollector(
                page,
                dry_run=dry_run,
                debug=debug,
                debug_ui=debug_ui_instance,
                name_filter=name_filter,
            )

            # Update PLZ progress in Debug UI
            if debug_ui_instance:
                debug_ui_instance.update_plz_progress(0, total_plz)

            for i, plz_ref in enumerate(pending_plz, 1):
                plz = plz_ref.plz
                print(f"[{i}/{total_plz}] 🔍 PLZ: {plz}")

                # Update PLZ progress in Debug UI
                if debug_ui_instance:
                    debug_ui_instance.update_plz_progress(i, total_plz)

                # Create PlzCollector entry on-demand (if not exists)
                plz_collector_entry = PlzCollector.get_or_create(plz, COLLECTOR_TYPE)
                db.session.commit()

                try:
                    # Collect PLZ data
                    entries = await collector.collect_plz(plz)

                    if not entries:
                        print(f"         ⚠️  Keine Ergebnisse")
                        PlzCollector.mark_processed(
                            plz=plz,
                            collector_type=COLLECTOR_TYPE,
                            result_count=0,
                        )
                        db.session.commit()
                        processed_plz += 1
                        continue

                    # Save to database
                    kanzleien_count = 0
                    stb_count = 0

                    if not dry_run:
                        for entry in entries:
                            k, s = save_entry(entry)
                            kanzleien_count += k
                            stb_count += s

                        PlzCollector.mark_processed(
                            plz=plz,
                            collector_type=COLLECTOR_TYPE,
                            result_count=len(entries),
                        )
                        db.session.commit()

                        # Run matching algorithm after PLZ is fully processed
                        match_result = match_steuerberater_to_kanzleien(plz, use_ai=use_ai)
                        if match_result.matched > 0:
                            msg = (
                                f"         🔗 Matching: {match_result.matched} StB umgehängt, "
                                f"{match_result.deleted_kanzleien} Kanzleien gelöscht"
                            )
                            if match_result.ai_requests > 0:
                                msg += f" (KI: {match_result.ai_requests} Anfragen, {match_result.ai_matches} Matches)"
                            print(msg)

                    total_kanzleien += kanzleien_count
                    total_steuerberater += stb_count
                    processed_plz += 1

                    print(
                        f"         ✅ {len(entries)} Einträge "
                        f"(+{kanzleien_count} Kanzleien, +{stb_count} StB)"
                    )

                except Exception as e:
                    logger.error(f"Error processing PLZ {plz}: {e}")
                    failed_plz += 1

                    if not dry_run:
                        PlzCollector.mark_processed(
                            plz=plz,
                            collector_type=COLLECTOR_TYPE,
                            result_count=0,
                            error_message=str(e),
                        )
                        db.session.commit()

            await browser.close()

        # Final summary
        print()
        print("=" * 60)
        print("✅ COLLECTING ABGESCHLOSSEN")
        print("=" * 60)
        print(f"📊 PLZ verarbeitet:     {processed_plz}")
        print(f"❌ PLZ fehlgeschlagen:  {failed_plz}")
        print(f"🏢 Neue Kanzleien:      {total_kanzleien}")
        print(f"👤 Neue Steuerberater:  {total_steuerberater}")
        print(f"🌐 HTTP-Anfragen:       {collector.request_count}")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BStBK Collector - Steuerberaterverzeichnis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python main_bstbk.py --plz-filter 4 --max-plz 5
  python main_bstbk.py --headless
  python main_bstbk.py --dry-run --verbose
        """,
    )

    parser.add_argument(
        "--plz-filter",
        type=str,
        default=None,
        help="Nur PLZ verarbeiten, die mit diesem Prefix beginnen (z.B. '4')",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Browser im Headless-Modus starten",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Keine Daten in Datenbank speichern (Test-Modus)",
    )
    parser.add_argument(
        "--max-plz",
        type=int,
        default=None,
        help="Maximale Anzahl zu verarbeitender PLZ",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Debug-Logging aktivieren",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Interaktiver Terminal-Debug-Modus: Pausiert nach jeder Detailseite und speichert HTML",
    )
    parser.add_argument(
        "--debug-ui",
        action="store_true",
        help="Web-basierte Debug-UI auf Port 5005 starten",
    )
    parser.add_argument(
        "--name-filter",
        type=str,
        default=None,
        help="Nur Einträge anzeigen, deren Name diesen Text enthält (case-insensitive)",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="KI-gestütztes Matching aktivieren für unsichere Fälle (Score=1) via OpenRouter",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            plz_filter=args.plz_filter,
            headless=args.headless,
            dry_run=args.dry_run,
            max_plz=args.max_plz,
            verbose=args.verbose,
            debug=args.debug,
            debug_ui=args.debug_ui,
            name_filter=args.name_filter,
            use_ai=args.use_ai,
        )
    )
