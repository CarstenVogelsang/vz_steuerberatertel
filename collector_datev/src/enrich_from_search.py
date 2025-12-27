"""Website-Anreicherung Phase 2 - Suchmaschinen-basierte Website-Ermittlung.

Dieses Skript sucht Websites fuer Steuerberater-Eintraege, bei denen
Phase 1 (E-Mail-Domain-Extraktion) keine Website gefunden hat.

VERWENDUNG:
    # Einfacher Aufruf mit PLZ-Praefix (alle PLZ beginnend mit 478)
    python -m src.enrich_from_search --plz-filter 478 --max-entries 5

    # PLZ-Bereich (von 47800 bis 47900)
    python -m src.enrich_from_search --plz-filter 47800-47900

    # Nur Eintraege ohne bisherige Recherche
    python -m src.enrich_from_search --plz-filter 4 --confidence-filter none

    # Niedrige und mittlere Konfidenz erneut pruefen
    python -m src.enrich_from_search --plz-filter 4 --confidence-filter low,medium

    # Testlauf ohne Schreiben ins Sheet
    python -m src.enrich_from_search --plz-filter 478 --dry-run

    # Einzelne Zeile testen (z.B. Zeile 8)
    python -m src.enrich_from_search --plz-filter 4 --row 8 --headless

PLZ-FILTER:
    Der --plz-filter Parameter unterstuetzt zwei Formate:

    1. PRAEFIX-FILTER: Nur die ersten Ziffern angeben
       --plz-filter 4       -> Alle PLZ 40000-49999 (Tabellenblatt: datev_4)
       --plz-filter 47      -> Alle PLZ 47000-47999
       --plz-filter 478     -> Alle PLZ 47800-47899
       --plz-filter 4780    -> Alle PLZ 47800-47809

    2. BEREICHS-FILTER: Start und Ende mit Bindestrich
       --plz-filter 47000-48000  -> PLZ von 47000 bis 48000
       --plz-filter 40000-45000  -> PLZ von 40000 bis 45000

    Das Tabellenblatt wird automatisch aus der ersten Ziffer abgeleitet.

KONFIDENZ-FILTER:
    --confidence-filter none    -> Eintraege ohne Website UND ohne Konfidenz
    --confidence-filter low     -> Eintraege mit Konfidenz "niedrig"
    --confidence-filter medium  -> Eintraege mit Konfidenz "mittel"
    --confidence-filter all     -> Alle obigen kombiniert
    --confidence-filter low,medium -> Mehrere Filter kombinieren

SUCH-PROVIDER:
    --search-provider brave       -> 2000 kostenlose Suchen/Monat (Standard)
                                     Benoetigt BRAVE_API_KEY (https://api-dashboard.search.brave.com)
    --search-provider serper      -> 2500 kostenlose Suchen/Monat
                                     Benoetigt SERPER_API_KEY (https://serper.dev)
    --search-provider duckduckgo  -> Kostenlos, Playwright-basiert mit Stealth
    --search-provider serpapi     -> Kostenpflichtig, benoetigt SERPAPI_KEY

ZEILEN-FILTER:
    --row 8                       -> Nur Zeile 8 testen (ueberspringt alle anderen Filter)
                                     Ideal zum Testen mit verschiedenen Search Providern

AUSGABE:
    - HTML-Report in data/reports/search_report_YYYY-MM-DD_HH-MM.html
    - Aktualisierung der Google Sheets Spalten K-P
    - LinkedIn-URLs werden in Spalte P gespeichert (ohne Besuch der Seite)
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
from .report_generator import HTMLReportGenerator, ReportEntry, SearchResultEntry
from .search_enricher import (
    SearchProvider,
    build_search_query,
    extract_linkedin_url,
    is_directory_url,
    is_linkedin_url,
    load_blacklist,
    search_brave,
    search_duckduckgo_playwright,
    search_serper,
    search_website,
    validate_with_impressum,
)
from .sheets_handler import (
    get_client,
    load_entries_for_phase2,
    open_sheet,
    open_sheet_by_plz_group,
    update_website_data,
)
from .website_enricher import Confidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Website-Anreicherung Phase 2 (Suchmaschinen-Suche)"
    )
    parser.add_argument(
        "--plz-filter",
        type=str,
        help="PLZ-Filter: Praefix (z.B. '4', '40') oder Bereich (z.B. '40000-41000')",
    )
    parser.add_argument(
        "--confidence-filter",
        type=str,
        default="none",
        help="Konfidenz-Filter: none, low, medium, all (kommagetrennt, z.B. 'low,medium')",
    )
    parser.add_argument(
        "--search-provider",
        type=str,
        choices=["brave", "serper", "duckduckgo", "serpapi"],
        default="brave",
        help="Such-Provider: brave (Standard, 2000 kostenlos/Monat), serper (2500/Monat), duckduckgo (mit Stealth), serpapi",
    )
    parser.add_argument("--sheet-url", type=str, help="Google Sheets URL")
    parser.add_argument("--credentials", type=Path, help="Pfad zur credentials.json")
    parser.add_argument("--headless", action="store_true", help="Headless ausfuehren")
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=4.0,
        help="Pause zwischen Suchen in Sekunden",
    )
    parser.add_argument("--max-entries", type=int, help="Maximale Anzahl Eintraege")
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximale Anzahl Suchergebnisse pro Eintrag",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Nur pruefen, nichts schreiben"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10000,
        help="Timeout fuer Website-Requests in ms",
    )
    parser.add_argument(
        "--row",
        type=int,
        help="Nur eine bestimmte Zeile testen (z.B. --row 8 fuer Zeile 8)",
    )
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def parse_confidence_filter(filter_str: str) -> list[str]:
    """Parse confidence filter string into list."""
    filters = [f.strip().lower() for f in filter_str.split(",")]
    valid_filters = {"none", "low", "medium", "all"}
    for f in filters:
        if f not in valid_filters:
            raise ValueError(f"Ungueltiger Konfidenz-Filter: {f}")
    return filters


async def run_phase2_enrichment(args: argparse.Namespace, config: Config) -> None:
    """Run Phase 2 website enrichment."""
    from playwright.async_api import async_playwright

    plz_filter = None
    sheet_index = None
    plz_filter_str = ""

    if args.plz_filter:
        plz_filter = parse_plz_filter(args.plz_filter)
        plz_filter_str = args.plz_filter
        sheet_index = get_sheet_index(plz_filter)
        if plz_filter.prefix:
            logging.info("PLZ-Filter: Praefix '%s'", plz_filter.prefix)
        else:
            logging.info(
                "PLZ-Filter: Bereich %s-%s", plz_filter.range_start, plz_filter.range_end
            )

    # Parse confidence filter
    confidence_filter = parse_confidence_filter(args.confidence_filter)
    logging.info("Konfidenz-Filter: %s", confidence_filter)

    # Determine search provider
    if args.search_provider == "brave":
        search_provider = SearchProvider.BRAVE
        logging.info("Such-Provider: Brave Search (2000 kostenlos/Monat)")
    elif args.search_provider == "serper":
        search_provider = SearchProvider.SERPER
        logging.info("Such-Provider: Serper (Google-Ergebnisse, 2500 kostenlos/Monat)")
    elif args.search_provider == "serpapi":
        search_provider = SearchProvider.SERPAPI
        logging.info("Such-Provider: SerpAPI")
    else:
        search_provider = SearchProvider.DUCKDUCKGO
        logging.info("Such-Provider: DuckDuckGo (mit Stealth-Modus)")

    # Load domain blacklist
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

    # Load entries for Phase 2
    if args.row:
        logging.info("Zeilen-Filter: Nur Zeile %s", args.row)
    logging.info("Lade Eintraege fuer Phase 2...")
    entries = load_entries_for_phase2(
        worksheet, confidence_filter, plz_filter, row_filter=args.row
    )

    if args.max_entries and not args.row:  # row_filter hat Vorrang
        entries = entries[: args.max_entries]

    logging.info("%s Eintraege zu verarbeiten", len(entries))

    if not entries:
        logging.info("Keine Eintraege zur Anreicherung gefunden")
        return

    # Initialize HTML Report Generator
    report = HTMLReportGenerator(plz_filter=plz_filter_str)

    # Statistics
    stats = {
        "processed": 0,
        "websites_found": 0,
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "no_results": 0,
        "search_errors": 0,
        "linkedin_found": 0,
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
                # Clear visual separator for each entry
                print(f"\n{'='*70}")
                print(f"[{idx}/{len(entries)}] {entry.name}")
                print(f"         PLZ: {entry.plz} | Ort: {entry.city}")
                print(f"{'='*70}")

                # Build search query
                query = build_search_query(entry.name, entry.plz, entry.city)
                print(f"\n🔍 SUCHE: {query}")
                print("-" * 70)

                # Initialize report entry
                report_entry = ReportEntry(
                    name=entry.name,
                    plz=entry.plz,
                    city=entry.city,
                    search_query=query,
                )

                # Search based on provider
                if search_provider == SearchProvider.BRAVE:
                    # Brave Search API (REST-based, no browser needed)
                    results = search_brave(query, max_results=args.max_results)
                elif search_provider == SearchProvider.SERPER:
                    # Serper API (REST-based, no browser needed)
                    results = search_serper(query, max_results=args.max_results)
                elif search_provider == SearchProvider.DUCKDUCKGO:
                    # DuckDuckGo via Playwright with Stealth
                    results = await search_duckduckgo_playwright(
                        page=page,
                        query=query,
                        max_results=args.max_results,
                        use_stealth=True,
                    )
                else:
                    # SerpAPI for paid option
                    results = search_website(
                        name=entry.name,
                        plz=entry.plz,
                        city=entry.city,
                        provider=search_provider,
                        max_results=args.max_results,
                    )

                # Extract LinkedIn URL (without visiting)
                linkedin_url = extract_linkedin_url(results)
                if linkedin_url:
                    report_entry.linkedin_url = linkedin_url
                    stats["linkedin_found"] += 1
                    print(f"\n🔗 LinkedIn gefunden: {linkedin_url}")

                # Display all raw results
                if results:
                    print(f"\n📋 ROHE SUCHERGEBNISSE ({len(results)}):")
                    for i, r in enumerate(results, 1):
                        # Check if it will be filtered
                        is_filtered = is_directory_url(r.url, blacklist)
                        is_linkedin = is_linkedin_url(r.url)

                        # Add to report
                        result_entry = SearchResultEntry(
                            url=r.url,
                            title=r.title,
                            is_filtered=is_filtered,
                            filter_reason="Blacklist" if is_filtered else "",
                            is_linkedin=is_linkedin,
                        )
                        report_entry.search_results.append(result_entry)

                        if is_linkedin:
                            status = "🔗 LINKEDIN"
                        elif is_filtered:
                            status = "❌ BLACKLIST"
                        else:
                            status = "✅"
                        print(f"  {i}. {status} {r.url}")
                        print(f"      {r.title[:70]}..." if len(r.title) > 70 else f"      {r.title}")
                else:
                    print("\n❌ Keine Suchergebnisse gefunden")

                if not results:
                    stats["no_results"] += 1
                    stats["processed"] += 1

                    if not args.dry_run:
                        update_website_data(
                            worksheet,
                            entry.row_number,
                            None,
                            today,
                            Confidence.NONE.value,
                            source=search_provider.value,
                            linkedin=linkedin_url or "",
                        )

                    report.add_entry(report_entry)
                    await asyncio.sleep(args.rate_limit)
                    continue

                # Filter directory URLs (including LinkedIn)
                filtered_results = [
                    r for r in results
                    if not is_directory_url(r.url, blacklist)
                    and not is_linkedin_url(r.url)
                ]

                print(f"\n✅ NACH FILTERUNG: {len(filtered_results)} von {len(results)} Ergebnissen")

                if not filtered_results:
                    print("   Alle Ergebnisse waren Verzeichnisse/Blacklist/LinkedIn")
                    stats["no_results"] += 1
                    stats["processed"] += 1

                    if not args.dry_run:
                        update_website_data(
                            worksheet,
                            entry.row_number,
                            None,
                            today,
                            Confidence.NONE.value,
                            source=search_provider.value,
                            linkedin=linkedin_url or "",
                        )

                    report.add_entry(report_entry)
                    await asyncio.sleep(args.rate_limit)
                    continue

                # Validate each result with Impressum verification
                print("\n🔎 VALIDIERUNG (Impressum-Check):")
                found_website = False
                for result in filtered_results:
                    print(f"\n   Pruefe: {result.url}")

                    validation = await validate_with_impressum(
                        page=page,
                        url=result.url,
                        name=entry.name,
                        plz=entry.plz,
                        city=entry.city,
                        street=entry.street,
                        phone=entry.phone,
                        mobile=entry.mobile,
                        email=entry.email,
                        timeout_ms=args.timeout,
                    )

                    # Update report entry with validation results
                    for re_entry in report_entry.search_results:
                        if re_entry.url == result.url:
                            if validation.error:
                                re_entry.validation_error = validation.error
                            else:
                                re_entry.validation_score = validation.score
                                re_entry.validation_confidence = validation.confidence.value
                                re_entry.validation_matches = [
                                    k for k, v in validation.matches.items() if v
                                ]

                    if validation.error:
                        print(f"      ❌ Fehler: {validation.error}")
                        continue

                    # Show validation score details
                    matches_str = ", ".join(k for k, v in validation.matches.items() if v)
                    print(f"      Score: {validation.score} ({validation.confidence.value})")
                    if matches_str:
                        print(f"      Matches: {matches_str}")

                    # Accept HIGH or MEDIUM confidence (score >= 4)
                    if validation.confidence in [Confidence.HIGH, Confidence.MEDIUM]:
                        print(f"\n   ✅ TREFFER GEFUNDEN!")
                        print(f"      URL: {validation.url}")
                        print(f"      Score: {validation.score} | Konfidenz: {validation.confidence.value}")

                        # Mark as match in report
                        for re_entry in report_entry.search_results:
                            if re_entry.url == result.url:
                                re_entry.is_match = True

                        report_entry.final_website = validation.url
                        report_entry.final_confidence = validation.confidence.value

                        stats["websites_found"] += 1
                        if validation.confidence == Confidence.HIGH:
                            stats["high_confidence"] += 1
                        else:
                            stats["medium_confidence"] += 1

                        if not args.dry_run:
                            update_website_data(
                                worksheet,
                                entry.row_number,
                                validation.url,
                                today,
                                validation.confidence.value,
                                source=search_provider.value,
                                linkedin=linkedin_url or "",
                            )

                        found_website = True
                        break
                    else:
                        print(f"      ⚠️ Score zu niedrig ({validation.score} < 4)")

                if not found_website:
                    print("\n   ❌ Keine passende Website gefunden")
                    stats["no_results"] += 1

                    if not args.dry_run:
                        update_website_data(
                            worksheet,
                            entry.row_number,
                            None,
                            today,
                            Confidence.NONE.value,
                            source=search_provider.value,
                            linkedin=linkedin_url or "",
                        )

                report.add_entry(report_entry)
                stats["processed"] += 1
                await asyncio.sleep(args.rate_limit)

        finally:
            await browser.close()

    # Save HTML report
    report_path = report.save()
    print(f"\n📄 HTML-Report gespeichert: {report_path}")
    logging.info("HTML-Report gespeichert: %s", report_path)

    # Print statistics
    logging.info("=" * 60)
    logging.info("STATISTIK")
    logging.info("=" * 60)
    logging.info("Verarbeitet:         %s", stats["processed"])
    logging.info("Websites gefunden:   %s", stats["websites_found"])
    logging.info("  - Hohe Konfidenz:  %s", stats["high_confidence"])
    logging.info("  - Mittlere:        %s", stats["medium_confidence"])
    logging.info("LinkedIn gefunden:   %s", stats["linkedin_found"])
    logging.info("Keine Ergebnisse:    %s", stats["no_results"])


def main() -> None:
    args = parse_args()
    load_dotenv()
    config = load_config()
    setup_logging(config.log_level)

    asyncio.run(run_phase2_enrichment(args, config))


if __name__ == "__main__":
    main()
