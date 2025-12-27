from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlzFilter:
    """Filter for PLZ selection.

    Supports two modes:
    - Prefix mode: Match PLZ starting with a given prefix (e.g., "4", "40", "401")
    - Range mode: Match PLZ within a numeric range (e.g., 40000-41000)
    """

    prefix: str | None = None
    range_start: int | None = None
    range_end: int | None = None


def parse_plz_filter(value: str) -> PlzFilter:
    """Parse a PLZ filter string.

    Args:
        value: Filter string, either:
            - A prefix like "4", "40", "401"
            - A range like "40000-41000"

    Returns:
        PlzFilter with either prefix or range set.

    Raises:
        ValueError: If the filter string is invalid.
    """
    if "-" in value:
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError(f"Ungültiger Bereich: {value}")
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            raise ValueError(f"Ungültiger Bereich: {value}")

        if start >= end:
            raise ValueError(f"Start muss kleiner als Ende sein: {value}")
        if start < 0 or end > 99999:
            raise ValueError(f"PLZ muss zwischen 0 und 99999 liegen: {value}")

        return PlzFilter(range_start=start, range_end=end)
    else:
        if not value.isdigit():
            raise ValueError(f"Präfix muss nur Ziffern enthalten: {value}")
        if len(value) > 5:
            raise ValueError(f"Präfix darf maximal 5 Ziffern haben: {value}")

        return PlzFilter(prefix=value)


def matches_filter(plz: str, plz_filter: PlzFilter) -> bool:
    """Check if a PLZ matches the filter.

    Args:
        plz: The PLZ to check (5-digit string)
        plz_filter: The filter to match against

    Returns:
        True if the PLZ matches the filter.
    """
    if plz_filter.prefix is not None:
        return plz.startswith(plz_filter.prefix)

    if plz_filter.range_start is not None and plz_filter.range_end is not None:
        try:
            plz_int = int(plz)
            return plz_filter.range_start <= plz_int <= plz_filter.range_end
        except ValueError:
            return False

    return True


def get_sheet_index(plz_filter: PlzFilter) -> int:
    """Get the target sheet index (0-9) from the filter.

    The sheet index is determined by the first digit of the PLZ range.

    Args:
        plz_filter: The filter to get the sheet index from

    Returns:
        Sheet index from 0 to 9

    Raises:
        ValueError: If the filter has no prefix or range set.
    """
    if plz_filter.prefix is not None:
        return int(plz_filter.prefix[0])

    if plz_filter.range_start is not None:
        return int(str(plz_filter.range_start)[0])

    raise ValueError("Filter muss Praefix oder Bereich haben")
