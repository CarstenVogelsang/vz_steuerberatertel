from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import gspread

from .parser import ParsedEntry

HEADERS = [
    "Name",
    "Anrede",
    "Rolle",
    "Strasse",
    "PLZ",
    "Ort",
    "Telefon",
    "Mobil",
    "E-Mail",
    "Kammer",
    "Website",
    "Website_Recherche",
    "Website_Konfidenz",
    "Domain_Blacklist",  # X = Website-Domain zur Blacklist hinzufuegen
    "Website_Quelle",
    "LinkedIn",
]


def get_client(credentials_path: Path) -> gspread.Client:
    return gspread.service_account(filename=str(credentials_path))


def open_sheet(client: gspread.Client, sheet_url: str) -> gspread.Worksheet:
    sheet = client.open_by_url(sheet_url)
    return sheet.sheet1


def open_sheet_by_plz_group(client: gspread.Client, sheet_url: str, plz_group: int) -> gspread.Worksheet:
    """Open a specific worksheet by PLZ group (0-9).

    Worksheets are named datev_0, datev_1, ..., datev_9.
    """
    if plz_group < 0 or plz_group > 9:
        raise ValueError(f"PLZ group must be 0-9, got {plz_group}")

    sheet = client.open_by_url(sheet_url)
    worksheet_name = f"datev_{plz_group}"
    return sheet.worksheet(worksheet_name)


def ensure_headers(worksheet: gspread.Worksheet) -> bool:
    """Set headers in row 1 if not already present. Returns True if headers were added."""
    first_row = worksheet.row_values(1)
    if first_row and first_row[0] == HEADERS[0]:
        return False
    worksheet.update(values=[HEADERS], range_name="A1:P1")
    return True


def load_existing_keys(worksheet: gspread.Worksheet) -> set[str]:
    """Load existing PLZ+Name keys from worksheet for duplicate detection.

    Returns a set of lowercase keys in format 'plz|name'.
    """
    all_values = worksheet.get_all_values()
    keys: set[str] = set()

    for row in all_values[1:]:  # Skip header row
        if len(row) >= 5 and row[0] and row[4]:  # Name (A) and PLZ (E)
            key = f"{row[4]}|{row[0]}".lower()
            keys.add(key)

    return keys


def is_duplicate(existing_keys: set[str], plz: str, name: str) -> bool:
    """Check if an entry with this PLZ+Name combination already exists."""
    key = f"{plz}|{name}".lower()
    return key in existing_keys


def append_entries(worksheet: gspread.Worksheet, entries: Iterable[ParsedEntry]) -> int:
    rows = []
    for entry in entries:
        data = asdict(entry)
        rows.append(
            [
                data["name"],
                data["salutation"],
                data["role"],
                data["street"],
                data["plz"],
                data["city"],
                data["phone"],
                data["mobile"],
                data["email"],
                data["chamber"],
                data["website"],
            ]
        )

    if not rows:
        return 0

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)


def append_entries_with_dedup(
    worksheet: gspread.Worksheet,
    entries: Iterable[ParsedEntry],
    existing_keys: set[str],
) -> tuple[int, int]:
    """Append entries, skipping duplicates.

    Args:
        worksheet: Target worksheet
        entries: Entries to append
        existing_keys: Set of existing PLZ|Name keys for duplicate detection

    Returns:
        Tuple of (entries_added, duplicates_skipped)
    """
    rows = []
    duplicates = 0

    for entry in entries:
        if is_duplicate(existing_keys, entry.plz, entry.name):
            duplicates += 1
            continue

        # Add to existing keys to prevent duplicates within batch
        key = f"{entry.plz}|{entry.name}".lower()
        existing_keys.add(key)

        data = asdict(entry)
        rows.append(
            [
                data["name"],
                data["salutation"],
                data["role"],
                data["street"],
                data["plz"],
                data["city"],
                data["phone"],
                data["mobile"],
                data["email"],
                data["chamber"],
                data["website"],
            ]
        )

    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")

    return len(rows), duplicates


@dataclass
class SheetEntry:
    """Entry from Google Sheet for enrichment."""

    row_number: int
    name: str
    email: str
    website: str
    plz: str
    city: str = ""


def load_entries_for_enrichment(
    worksheet: gspread.Worksheet,
    plz_filter: "PlzFilter | None" = None,
) -> list[SheetEntry]:
    """Load entries that need website enrichment.

    Returns entries where:
    - Website (column K) is empty
    - Email (column I) is not empty

    Args:
        worksheet: Target worksheet
        plz_filter: Optional PLZ filter

    Returns:
        List of SheetEntry objects
    """
    from .plz_filter import PlzFilter, matches_filter

    all_values = worksheet.get_all_values()
    entries: list[SheetEntry] = []

    for idx, row in enumerate(all_values[1:], start=2):  # Skip header, 1-indexed
        if len(row) < 11:
            continue

        name = row[0].strip() if row[0] else ""
        plz = row[4].strip() if row[4] else ""
        city = row[5].strip() if len(row) > 5 else ""
        email = row[8].strip() if row[8] else ""
        website = row[10].strip() if len(row) > 10 else ""

        # Skip if website already exists
        if website:
            continue

        # Skip if no email
        if not email:
            continue

        # Skip if no name
        if not name:
            continue

        # Apply PLZ filter if specified
        if plz_filter is not None and plz and not matches_filter(plz, plz_filter):
            continue

        entries.append(
            SheetEntry(
                row_number=idx,
                name=name,
                email=email,
                website=website,
                plz=plz,
                city=city,
            )
        )

    return entries


def update_website_data(
    worksheet: gspread.Worksheet,
    row_number: int,
    website: str | None,
    recherche_date: str,
    confidence: str,
    source: str = "",
    linkedin: str = "",
) -> None:
    """Update website data for a single row.

    Args:
        worksheet: Target worksheet
        row_number: Row to update (1-indexed)
        website: Website URL or None
        recherche_date: Date of research (YYYY-MM-DD)
        confidence: Confidence level (hoch/mittel/niedrig/keine)
        source: Source of website discovery (email/duckduckgo/serpapi)
        linkedin: LinkedIn profile URL (optional)
    """
    # Update columns K-P (Website, Website_Recherche, Website_Konfidenz, email_blacklist, Website_Quelle, LinkedIn)
    values = [[website or "", recherche_date, confidence, "", source, linkedin]]
    worksheet.update(values=values, range_name=f"K{row_number}:P{row_number}")


@dataclass
class BlacklistCorrection:
    """Eintrag zur Blacklist-Korrektur.

    Zeilen mit "X" in Spalte N (Domain_Blacklist) werden zur
    konsolidierten domain_blacklist.txt hinzugefuegt.

    Smart-Logik: Website (K) hat Vorrang, sonst E-Mail (I).
    """

    row_number: int
    website: str  # Website-URL aus Spalte K (Vorrang)
    email: str  # E-Mail-Adresse aus Spalte I (Fallback)
    plz: str


def load_blacklist_corrections(
    worksheet: gspread.Worksheet,
    plz_filter: "PlzFilter | None" = None,
) -> list[BlacklistCorrection]:
    """Lade Eintraege mit X in Spalte N (Domain_Blacklist).

    Smart-Logik: Website (K) hat Vorrang, sonst E-Mail (I).
    Mindestens eines von beiden muss vorhanden sein.

    Args:
        worksheet: Ziel-Tabellenblatt
        plz_filter: Optionaler PLZ-Filter

    Returns:
        Liste von BlacklistCorrection Objekten
    """
    from .plz_filter import matches_filter

    all_values = worksheet.get_all_values()
    corrections: list[BlacklistCorrection] = []

    for idx, row in enumerate(all_values[1:], start=2):  # Header ueberspringen, 1-indexiert
        if len(row) < 14:
            continue

        plz = row[4].strip() if row[4] else ""
        email = row[8].strip() if len(row) > 8 else ""
        website = row[10].strip() if len(row) > 10 else ""
        blacklist_mark = row[13].strip().upper() if len(row) > 13 else ""

        # Nur Zeilen mit X in Spalte N verarbeiten
        if blacklist_mark != "X":
            continue

        # Mindestens Website ODER E-Mail benoetigt
        if not website and not email:
            continue

        # PLZ-Filter anwenden falls angegeben
        if plz_filter is not None and plz and not matches_filter(plz, plz_filter):
            continue

        corrections.append(
            BlacklistCorrection(
                row_number=idx,
                website=website,
                email=email,
                plz=plz,
            )
        )

    return corrections


def clear_website_data(worksheet: gspread.Worksheet, row_number: int) -> None:
    """Clear website data columns K, L, M, N, O, P for a single row.

    Args:
        worksheet: Target worksheet
        row_number: Row to clear (1-indexed)
    """
    worksheet.update(values=[["", "", "", "", "", ""]], range_name=f"K{row_number}:P{row_number}")


@dataclass
class Phase2Entry:
    """Entry from Google Sheet for Phase 2 enrichment."""

    row_number: int
    name: str
    plz: str
    city: str
    street: str
    phone: str
    mobile: str
    email: str
    website: str
    confidence: str


def load_entries_for_phase2(
    worksheet: gspread.Worksheet,
    confidence_filter: list[str],
    plz_filter: "PlzFilter | None" = None,
    row_filter: int | None = None,
) -> list[Phase2Entry]:
    """Load entries for Phase 2 enrichment based on confidence filter.

    Args:
        worksheet: Target worksheet
        confidence_filter: List of confidence levels to include:
            - "none": No website (K empty) AND no confidence (M empty or "keine")
            - "low": Confidence is "niedrig"
            - "medium": Confidence is "mittel"
            - "all": All of the above
        plz_filter: Optional PLZ filter
        row_filter: Optional specific row number to test (bypasses other filters)

    Returns:
        List of Phase2Entry objects
    """
    from .plz_filter import matches_filter

    all_values = worksheet.get_all_values()
    entries: list[Phase2Entry] = []

    # Normalize filter
    if "all" in confidence_filter:
        confidence_filter = ["none", "low", "medium"]

    for idx, row in enumerate(all_values[1:], start=2):  # Skip header, 1-indexed
        # If row_filter is set, only process that specific row
        if row_filter is not None and idx != row_filter:
            continue
        if len(row) < 11:
            continue

        name = row[0].strip() if row[0] else ""
        street = row[3].strip() if len(row) > 3 else ""
        plz = row[4].strip() if row[4] else ""
        city = row[5].strip() if len(row) > 5 else ""
        phone = row[6].strip() if len(row) > 6 else ""
        mobile = row[7].strip() if len(row) > 7 else ""
        email = row[8].strip() if len(row) > 8 else ""
        website = row[10].strip() if len(row) > 10 else ""
        confidence = row[12].strip().lower() if len(row) > 12 else ""

        # Skip if no name
        if not name:
            continue

        # When row_filter is set, bypass all other filters
        if row_filter is None:
            # Apply PLZ filter if specified
            if plz_filter is not None and plz and not matches_filter(plz, plz_filter):
                continue

            # Check confidence filter
            should_include = False

            if "none" in confidence_filter:
                # No website AND (no confidence OR confidence is "keine")
                if not website and (not confidence or confidence == "keine"):
                    should_include = True

            if "low" in confidence_filter:
                # Confidence is "niedrig"
                if confidence == "niedrig":
                    should_include = True

            if "medium" in confidence_filter:
                # Confidence is "mittel"
                if confidence == "mittel":
                    should_include = True

            if not should_include:
                continue

        entries.append(
            Phase2Entry(
                row_number=idx,
                name=name,
                plz=plz,
                city=city,
                street=street,
                phone=phone,
                mobile=mobile,
                email=email,
                website=website,
                confidence=confidence,
            )
        )

    return entries
