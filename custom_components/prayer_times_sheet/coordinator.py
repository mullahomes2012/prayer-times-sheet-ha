"""DataUpdateCoordinator for Prayer Times Sheet."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COLUMN_MAPPING,
    CONF_DATE_COLUMN,
    CONF_DATE_FORMAT,
    CONF_ENABLED_PRAYERS,
    CONF_END_TIMES,
    CONF_SHEET_URL,
    DEFAULT_END_TIMES,
    DOMAIN,
    END_TIME_MINUTES,
    END_TIME_NONE,
    END_TIME_PRAYER,
    SCAN_INTERVAL_MINUTES,
)
from .sheet_data import extract_prayer_times, fetch_csv, find_todays_row

_LOGGER = logging.getLogger(__name__)

TIME_FORMATS = ["%H:%M", "%I:%M %p", "%I:%M%p", "%H:%M:%S"]


def _parse_time(time_str: str) -> datetime | None:
    """Parse a time string into a datetime (today's date)."""
    if not time_str:
        return None
    for fmt in TIME_FORMATS:
        try:
            t = datetime.strptime(time_str.strip(), fmt)
            now = datetime.now()
            return t.replace(year=now.year, month=now.month, day=now.day)
        except ValueError:
            continue
    return None


def _format_time(dt: datetime) -> str:
    """Format a datetime back to HH:MM."""
    return dt.strftime("%H:%M")


def _compute_end_times(
    prayer_times: dict[str, str | None],
    end_time_config: dict[str, dict],
) -> dict[str, str | None]:
    """Compute end time for each prayer based on config."""
    result: dict[str, str | None] = {}

    for prayer_key, raw_time in prayer_times.items():
        cfg = end_time_config.get(prayer_key, {})
        mode = cfg.get("mode", END_TIME_NONE)

        if mode == END_TIME_NONE:
            result[prayer_key] = None
            continue

        if mode == END_TIME_MINUTES:
            start_dt = _parse_time(raw_time or "")
            if start_dt is None:
                result[prayer_key] = None
                continue
            minutes = int(cfg.get("value", 15))
            result[prayer_key] = _format_time(start_dt + timedelta(minutes=minutes))

        elif mode == END_TIME_PRAYER:
            target_key = cfg.get("value", "")
            target_time = prayer_times.get(target_key)
            # If target prayer isn't in today's data, skip
            result[prayer_key] = target_time if target_time else None

        else:
            result[prayer_key] = None

    return result


class PrayerTimesCoordinator(DataUpdateCoordinator):
    """Fetch today's prayer times from a Google Sheet and distribute to sensors."""

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict) -> None:
        self.sheet_url: str = config[CONF_SHEET_URL]
        self.date_column: str = config[CONF_DATE_COLUMN]
        self.date_format: str = config[CONF_DATE_FORMAT]
        self.column_mapping: dict[str, str] = config[CONF_COLUMN_MAPPING]
        self.enabled_prayers: list[str] = config[CONF_ENABLED_PRAYERS]
        self.end_time_config: dict[str, dict] = config.get(CONF_END_TIMES, {})
        self._session: aiohttp.ClientSession | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> dict:
        """Fetch latest data from the sheet."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        try:
            rows = await fetch_csv(self._session, self.sheet_url)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching sheet: {err}") from err

        row = find_todays_row(rows, self.date_column, self.date_format)
        if row is None:
            raise UpdateFailed(
                f"No row found for today in column '{self.date_column}'"
            )

        prayer_times = extract_prayer_times(
            row, self.column_mapping, self.enabled_prayers
        )
        end_times = _compute_end_times(prayer_times, self.end_time_config)

        return {
            "times": prayer_times,
            "end_times": end_times,
        }

    async def async_shutdown(self) -> None:
        """Close the aiohttp session on unload."""
        if self._session and not self._session.closed:
            await self._session.close()
