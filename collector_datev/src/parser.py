from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:Tel\.?|Telefon)\s*:?\s*(.+)", re.IGNORECASE)
MOBILE_RE = re.compile(r"Mobil\s*:?\s*(.+)", re.IGNORECASE)
URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
PLZ_RE = re.compile(r"\b\d{5}\b")
ROLE_RE = re.compile(r"^Steuerberater(in)?$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedEntry:
    name: str
    salutation: str
    role: str
    street: str
    plz: str
    city: str
    phone: str
    mobile: str
    email: str
    chamber: str
    website: str


def _clean_lines(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line and line.strip()]


def parse_entry(block_text: str) -> ParsedEntry:
    lines = _clean_lines(block_text.splitlines())

    email = ""
    phone = ""
    mobile = ""
    website = ""
    chamber = ""

    cleaned_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if "Berufskammer" in line and ("Zuständige" in line or "Zustaendige" in line):
            if i + 1 < len(lines):
                chamber = lines[i + 1].strip()
                i += 2
                continue

        email_match = EMAIL_RE.search(line)
        if email_match:
            email = email_match.group(0)
            i += 1
            continue

        phone_match = PHONE_RE.search(line)
        if phone_match:
            phone = phone_match.group(1).strip()
            i += 1
            continue

        mobile_match = MOBILE_RE.search(line)
        if mobile_match:
            mobile = mobile_match.group(1).strip()
            i += 1
            continue

        url_match = URL_RE.search(line)
        if url_match:
            website = url_match.group(1).strip()
            i += 1
            continue

        cleaned_lines.append(line)
        i += 1

    if website.startswith("www."):
        website = f"https://{website}"

    plz = ""
    city = ""
    street = ""
    plz_index = -1
    for idx, line in enumerate(cleaned_lines):
        plz_match = PLZ_RE.search(line)
        if plz_match:
            plz = plz_match.group(0)
            city = line[plz_match.end() :].strip()
            plz_index = idx
            break

    if plz_index > 0:
        street = cleaned_lines[plz_index - 1]

    before_address = cleaned_lines[: max(plz_index - 1, 0)]

    salutation = ""
    role = ""
    name_lines: list[str] = []

    if before_address:
        first = before_address[0]
        if first.lower().startswith("herr"):
            salutation = "Herr"
            before_address = before_address[1:]
        elif first.lower().startswith("frau"):
            salutation = "Frau"
            before_address = before_address[1:]

    for line in before_address:
        if ROLE_RE.search(line):
            role = line
        else:
            name_lines.append(line)

    name = " ".join(name_lines).strip()

    return ParsedEntry(
        name=name,
        salutation=salutation,
        role=role,
        street=street,
        plz=plz,
        city=city,
        phone=phone,
        mobile=mobile,
        email=email,
        chamber=chamber,
        website=website,
    )
