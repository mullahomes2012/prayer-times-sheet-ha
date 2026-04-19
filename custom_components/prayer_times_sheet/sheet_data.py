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


def find_todays_row(
    rows: list[dict],
    date_column: str,
    date_format: str,
) -> dict | None:
    """Find the row matching today's date."""
    today_str = datetime.now().strftime(date_format)
    for row in rows:
        cell = row.get(date_column, "").strip()
        if cell == today_str:
            return row
    # Fallback: try parsing each cell with the given format
    today = datetime.now().date()
    for row in rows:
        cell = row.get(date_column, "").strip()
        try:
            parsed = datetime.strptime(cell, date_format).date()
            if parsed == today:
                return row
        except ValueError:
            continue
    _LOGGER.warning(
        "No row found for today (%s) in column '%s'", today_str, date_column
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
