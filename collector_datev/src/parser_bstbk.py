"""BStBK Parser.

Parses detail pages from the Bundessteuerberaterkammer Steuerberaterverzeichnis.
URL: https://steuerberaterverzeichnis.berufs-org.de/
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from bs4 import BeautifulSoup

from src.email_classifier import classify_email

logger = logging.getLogger(__name__)


@dataclass
class ParsedSteuerberater:
    """Parsed Steuerberater (person) data."""

    nachname: str
    vorname: Optional[str] = None
    titel: Optional[str] = None  # "Steuerberater" / "Steuerberaterin"
    safe_id: Optional[str] = None
    email: Optional[str] = None  # Only if personal email (not Kanzlei)
    mobil: Optional[str] = None
    bestelldatum: Optional[date] = None


@dataclass
class ParsedKanzlei:
    """Parsed Kanzlei (firm) data."""

    name: str
    rechtsform: Optional[str] = None  # e.g., "GbR", "PartG mbB"
    strasse: Optional[str] = None
    plz: Optional[str] = None
    ort: Optional[str] = None
    telefon: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None  # Only if Kanzlei email
    website: Optional[str] = None
    kammer_name: Optional[str] = None


@dataclass
class ParsedBStBKEntry:
    """Complete parsed entry from BStBK detail page."""

    kanzlei: ParsedKanzlei
    steuerberater: list[ParsedSteuerberater] = field(default_factory=list)
    is_einzelperson: bool = False  # True if single person (not Gesellschaft)


def parse_date(date_str: str) -> Optional[date]:
    """Parse German date format (DD.MM.YYYY) to date object.

    Args:
        date_str: Date string in format "DD.MM.YYYY"

    Returns:
        date object or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Try DD.MM.YYYY format
    match = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date_str)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def extract_plz_ort(plz_ort_str: str) -> tuple[Optional[str], Optional[str]]:
    """Extract PLZ and Ort from combined string.

    Args:
        plz_ort_str: String like "47574 Goch" or "47574 Goch-Kessel"

    Returns:
        Tuple of (plz, ort)
    """
    if not plz_ort_str:
        return None, None

    plz_ort_str = plz_ort_str.strip()

    # Match 5-digit PLZ followed by city name
    match = re.match(r"(\d{5})\s+(.+)", plz_ort_str)
    if match:
        return match.group(1), match.group(2).strip()

    return None, plz_ort_str


def extract_address(soup) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract Straße, PLZ and Ort from #adresse element.

    The address can have 2 or 3 lines with <br> separators:
    - 2 lines: <p id="adresse">Emmericher Weg 72<br>47574 Goch</p>
    - 3 lines: <p id="adresse">Kanzleiname<br>Straße 10<br>47506 Ort</p>

    The LAST line is always PLZ+Ort (starts with 5-digit PLZ).
    Everything before that is treated as address lines (street, etc.).

    Args:
        soup: BeautifulSoup object

    Returns:
        Tuple of (strasse, plz, ort)
    """
    adresse_el = soup.select_one("#adresse")
    if not adresse_el:
        return None, None, None

    # Replace <br> with newline and split
    for br in adresse_el.find_all("br"):
        br.replace_with("\n")

    lines = [line.strip() for line in adresse_el.get_text().strip().split("\n") if line.strip()]

    if not lines:
        return None, None, None

    # Find the PLZ+Ort line (starts with 5-digit PLZ)
    plz_ort_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\d{5}\s", line):
            plz_ort_idx = i
            break

    if plz_ort_idx is not None:
        # Found PLZ+Ort line
        plz_ort = lines[plz_ort_idx]
        plz, ort = extract_plz_ort(plz_ort)

        # Everything before PLZ+Ort is address (join with comma if multiple lines)
        # Take the line directly before PLZ as Straße
        if plz_ort_idx > 0:
            strasse = lines[plz_ort_idx - 1]
        else:
            strasse = None

        return strasse, plz, ort

    # No PLZ found - try to parse last line as PLZ+Ort
    if len(lines) >= 2:
        strasse = lines[-2]
        plz, ort = extract_plz_ort(lines[-1])
        return strasse, plz, ort
    elif len(lines) == 1:
        plz, ort = extract_plz_ort(lines[0])
        return None, plz, ort

    return None, None, None


def extract_kammer(soup) -> Optional[str]:
    """Extract Kammer name from #regionalkammerSection.

    The structure is:
    <section id="regionalkammerSection">
      <h2>Zuständige Steuerberaterkammer</h2>
      <p>
        <span>Steuerberaterkammer</span>
        <span>Düsseldorf</span>
      </p>
    </section>

    Args:
        soup: BeautifulSoup object

    Returns:
        Kammer name or None
    """
    section = soup.select_one("#regionalkammerSection")
    if not section:
        return None

    # First <p> after <h2> contains the Kammer
    p = section.select_one("p")
    if p:
        spans = p.find_all("span")
        if len(spans) >= 2:
            return f"{spans[0].get_text(strip=True)} {spans[1].get_text(strip=True)}"
        elif spans:
            return spans[0].get_text(strip=True)
    return None


def parse_name(name_str: str) -> tuple[Optional[str], str]:
    """Parse name string into vorname and nachname.

    Handles formats like:
    - "Wolfgang Auclair" -> ("Wolfgang", "Auclair")
    - "Hubert Aymans" -> ("Hubert", "Aymans")
    - "Dr. Hans Müller" -> ("Hans", "Dr. Müller") - academic title stays with name

    Args:
        name_str: Full name string

    Returns:
        Tuple of (vorname, nachname)
    """
    if not name_str:
        return None, ""

    name_str = name_str.strip()
    parts = name_str.split()

    if len(parts) == 0:
        return None, ""
    elif len(parts) == 1:
        return None, parts[0]
    else:
        # Last part is nachname, everything else is vorname
        return " ".join(parts[:-1]), parts[-1]


def parse_namen_from_firmenname(firmenname_html: str) -> list[tuple[Optional[str], str]]:
    """Parse multiple names from Firmenname HTML (separated by <br>).

    The Firmenname field in Gesellschaften contains all Steuerberater names
    separated by <br> tags. Format: "Nachname, Vorname" or "Nachname, Vorname, Titel"

    Args:
        firmenname_html: HTML content of the firmenname field

    Returns:
        List of (vorname, nachname) tuples
    """
    if not firmenname_html:
        return []

    soup = BeautifulSoup(firmenname_html, "html.parser")

    # Get text content, replacing <br> with newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    text = soup.get_text()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    namen = []
    for line in lines:
        # Format: "Nachname, Vorname" or "Nachname, Vorname, Titel"
        parts = [p.strip() for p in line.split(",")]

        if len(parts) >= 2:
            nachname = parts[0]
            vorname = parts[1]
            namen.append((vorname, nachname))
        elif len(parts) == 1 and parts[0]:
            # Only nachname
            namen.append((None, parts[0]))

    return namen


def parse_detail_page(html: str) -> Optional[ParsedBStBKEntry]:
    """Parse a BStBK detail page.

    Distinguishes between:
    1. Einzelperson (single Steuerberater): Has id="beruf" element
    2. Gesellschaft (firm with multiple Steuerberater): Has id="firmenname" + id="rechtsform"

    Args:
        html: HTML content of the detail page

    Returns:
        ParsedBStBKEntry or None if parsing fails
    """
    soup = BeautifulSoup(html, "html.parser")

    # Common fields extraction
    def get_text(selector: str) -> Optional[str]:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    def get_html(selector: str) -> Optional[str]:
        el = soup.select_one(selector)
        return str(el) if el else None

    def get_span_text(selector: str) -> Optional[str]:
        el = soup.select_one(selector)
        if el:
            span = el.select_one("span.text-wrap")
            return span.get_text(strip=True) if span else None
        return None

    # Check if this is an Einzelperson or Gesellschaft
    beruf_el = soup.select_one("#beruf")
    is_einzelperson = beruf_el is not None

    # Extract common address fields using new function
    strasse, plz, ort = extract_address(soup)

    # Contact info
    telefon = get_span_text("#telefon")
    fax = get_span_text("#fax")
    email = get_span_text("#email")
    website = get_span_text("#website")

    # Kammer - use new extract function
    kammer_name = extract_kammer(soup)

    # Safe ID
    safe_id = get_span_text("#safeid")

    # Bestelldatum
    bestelldatum_str = get_span_text("#bestelldatum")
    bestelldatum = parse_date(bestelldatum_str)

    if is_einzelperson:
        # Case 1: Einzelperson - single Steuerberater who IS the Kanzlei
        name_el = soup.select_one("#vorname-and-nachname")
        full_name = name_el.get_text(strip=True) if name_el else ""
        vorname, nachname = parse_name(full_name)

        # VALIDIERUNG: Name und PLZ müssen vorhanden sein
        if not full_name or not full_name.strip():
            logger.warning("Leere Einzelperson-Seite: Kein Name gefunden")
            return None
        if not plz:
            logger.warning(f"Einzelperson ohne PLZ: {full_name}")
            return None

        titel = get_text("#beruf")  # "Steuerberater" or "Steuerberaterin"

        # Extract mobile phone number
        mobil = get_span_text("#mobil")

        # Classify email
        steuerberater_email = None
        kanzlei_email = None
        if email:
            if classify_email(email) == "kanzlei":
                kanzlei_email = email
            else:
                steuerberater_email = email

        # Create Kanzlei with person's name
        kanzlei = ParsedKanzlei(
            name=full_name,
            strasse=strasse,
            plz=plz,
            ort=ort,
            telefon=telefon,
            fax=fax,
            email=kanzlei_email,
            website=website,
            kammer_name=kammer_name,
        )

        # Create single Steuerberater
        steuerberater = ParsedSteuerberater(
            nachname=nachname,
            vorname=vorname,
            titel=titel,
            safe_id=safe_id,
            email=steuerberater_email,
            mobil=mobil,
            bestelldatum=bestelldatum,
        )

        return ParsedBStBKEntry(
            kanzlei=kanzlei,
            steuerberater=[steuerberater],
            is_einzelperson=True,
        )

    else:
        # Case 2: Gesellschaft - firm page (no individual Steuerberater data)
        # IMPORTANT: Gesellschafts-Seiten enthalten keine zuverlässigen
        # Steuerberater-Daten. Die Namen im Firmenname-Feld sind oft
        # der Firmenname selbst, nicht Personennamen.
        # Steuerberater werden über ihre Einzelperson-Seiten erfasst (mit Safe ID).

        firmenname_el = soup.select_one("#firmenname")
        if firmenname_el:
            # Replace <br> with spaces to preserve word boundaries
            for br in firmenname_el.find_all("br"):
                br.replace_with(" ")
            # Normalize multiple whitespaces to single space
            firmenname = re.sub(r"\s+", " ", firmenname_el.get_text()).strip()
        else:
            firmenname = ""

        # VALIDIERUNG: Firmenname und PLZ müssen vorhanden sein
        if not firmenname or not firmenname.strip():
            logger.warning("Leere Gesellschafts-Seite: Kein Firmenname gefunden")
            return None
        if not plz:
            logger.warning(f"Gesellschaft ohne PLZ: {firmenname}")
            return None

        # Extract Rechtsform
        rechtsform = get_span_text("#rechtsform")

        # Classify email - for Gesellschaft, email is usually Kanzlei email
        kanzlei_email = email  # Gesellschaft emails are typically firm emails

        # Create Kanzlei
        kanzlei = ParsedKanzlei(
            name=firmenname,
            rechtsform=rechtsform,
            strasse=strasse,
            plz=plz,
            ort=ort,
            telefon=telefon,
            fax=fax,
            email=kanzlei_email,
            website=website,
            kammer_name=kammer_name,
        )

        # NO Steuerberater extraction from Gesellschafts-Seiten!
        # Reason: The firmenname field contains the company name (possibly
        # split across lines), not individual person names.
        # Steuerberater will be collected from their individual pages
        # where they have a Safe ID.

        logger.debug(f"Gesellschaft: {firmenname} (keine Steuerberater-Extraktion)")

        return ParsedBStBKEntry(
            kanzlei=kanzlei,
            steuerberater=[],  # Empty! No Steuerberater from Gesellschafts-Seiten
            is_einzelperson=False,
        )


def parse_search_results(html: str) -> list[str]:
    """Parse search results page and extract detail page URLs.

    Args:
        html: HTML content of the search results page

    Returns:
        List of detail page URLs (relative or absolute)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find all links to detail pages
    # The exact selector depends on the actual HTML structure
    # Common patterns: links in result list, links with specific class
    urls = []

    # Try to find result links - adjust selector based on actual HTML
    for link in soup.select("a[href*='detail'], a[href*='view'], .result-item a"):
        href = link.get("href")
        if href and href not in urls:
            urls.append(href)

    # Fallback: look for any links that might be detail pages
    if not urls:
        for link in soup.select("table a, .list a, ul.results a"):
            href = link.get("href")
            if href and href not in urls:
                urls.append(href)

    return urls
