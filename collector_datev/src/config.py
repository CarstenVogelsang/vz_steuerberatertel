from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    start_url: str
    input_csv_path: Path
    sheet_url: str
    credentials_path: Path
    headless: bool
    timeout_ms: int
    rate_limit_sec: float
    max_retries: int
    log_level: str
    max_plz: int | None


DEFAULT_START_URL = (
    "https://www.datev.de/kasus/First/Start?KammerId=BuKa&Suffix1=BuKaY&Suffix2=BuKaXY&Truncation=42"
)
DEFAULT_INPUT_CSV = Path("data/postleitzahlen.csv")
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1g4PlGQ0Wxdb4HLBdR_6pCzLzg08kB0GteiDoW7oCmyM/edit"
DEFAULT_CREDENTIALS = Path("data/credentials.json")


def load_config() -> Config:
    headless_env = os.getenv("HEADLESS", "false").strip().lower()
    headless = headless_env in {"1", "true", "yes"}

    max_plz_raw = os.getenv("MAX_PLZ", "").strip()
    max_plz = int(max_plz_raw) if max_plz_raw else None

    return Config(
        start_url=os.getenv("START_URL", DEFAULT_START_URL),
        input_csv_path=Path(os.getenv("PLZ_INPUT", str(DEFAULT_INPUT_CSV))),
        sheet_url=os.getenv("SHEET_URL", DEFAULT_SHEET_URL),
        credentials_path=Path(os.getenv("GOOGLE_CREDENTIALS", str(DEFAULT_CREDENTIALS))),
        headless=headless,
        timeout_ms=int(os.getenv("TIMEOUT_MS", "30000")),
        rate_limit_sec=float(os.getenv("RATE_LIMIT_SEC", "2.5")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_plz=max_plz,
    )
