"""Fetch and parse prayer times from a public Google Sheet CSV."""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime

import aiohttp

_LOGGER = logging.getLogger(__name__)


def build_csv_url(sheet_url: str) -> str:
    """Convert any published Google Sheet URL to its CSV export equivalent."""
    # Already a CSV export URL
    if "output=csv" in sheet_url:
        return sheet_url

    # Extract the /e/XXXX/pub part and rebuild cleanly
    match = re.search(r"spreadsheets/d/e/([^/]+)/pub", sheet_url)
    if match:
        key = match.group(1)
        # Preserve gid if present
        gid_match = re.search(r"gid=(\d+)", sheet_url)
        gid = gid_match.group(1) if gid_match else "0"
        return (
            f"https://docs.google.com/spreadsheets/d/e/{key}"
            f"/pub?gid={gid}&single=true&output=csv"
        )

    raise ValueError(f"Cannot derive CSV URL from: {sheet_url}")


async def fetch_csv(session: aiohttp.ClientSession, url: str) -> list[dict]:
    """Fetch and parse CSV rows from the sheet URL."""
    csv_url = build_csv_url(url)
    _LOGGER.debug("Fetching prayer times CSV from %s", csv_url)

    async with session.get(csv_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        text = await resp.text()

    reader = csv.DictReader(io.StringIO(text))
    rows = [row for row in reader]
    _LOGGER.debug("Fetched %d rows from sheet", len(rows))
    return rows


async def get_columns(session: aiohttp.ClientSession, url: str) -> list[str]:
    """Return the list of column headers from the sheet."""
    rows = await fetch_csv(session, url)
    if not rows:
        return []
    return list(rows[0].keys())


ALL_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%-d/%-m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
]


def find_todays_row(
    rows: list[dict],
    date_column: str,
    date_format: str,
) -> dict | None:
    """Find the row matching today's date."""
    today = datetime.now().date()

    # Build a set of all possible string representations of today
    today_strings: set[str] = set()
    for fmt in [date_format] + ALL_DATE_FORMATS:
        try:
            today_strings.add(datetime.now().strftime(fmt))
        except ValueError:
            pass

    # Also try parsing each cell against all known formats
    for row in rows:
        # Strip BOM, whitespace, and invisible chars from the cell value
        cell = row.get(date_column, "")
        if cell is None:
            cell = ""
        cell = cell.strip().lstrip("\ufeff").strip()

        # Fast string match first
        if cell in today_strings:
            return row

        # Slower parse fallback
        for fmt in [date_format] + ALL_DATE_FORMATS:
            try:
                if datetime.strptime(cell, fmt).date() == today:
                    return row
            except ValueError:
                continue

    _LOGGER.warning(
        "No row found for today (%s) in column '%s'. First few date values: %s",
        today,
        date_column,
        [r.get(date_column, "").strip() for r in rows[:5]],
    )
    return None


def extract_prayer_times(
    row: dict,
    column_mapping: dict[str, str],  # prayer_key -> sheet_column_name
    enabled_prayers: list[str],
) -> dict[str, str | None]:
    """Extract the relevant prayer times from a row."""
    result: dict[str, str | None] = {}
    for prayer_key in enabled_prayers:
        col_name = column_mapping.get(prayer_key)
        if col_name:
            result[prayer_key] = row.get(col_name, "").strip() or None
        else:
            result[prayer_key] = None
    return result
