"""DataUpdateCoordinator for Prayer Times Sheet."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COLUMN_MAPPING,
    CONF_DATE_COLUMN,
    CONF_DATE_FORMAT,
    CONF_ENABLED_PRAYERS,
    CONF_SHEET_URL,
    DOMAIN,
    SCAN_INTERVAL_MINUTES,
)
from .sheet_data import extract_prayer_times, fetch_csv, find_todays_row

_LOGGER = logging.getLogger(__name__)


class PrayerTimesCoordinator(DataUpdateCoordinator):
    """Fetch today's prayer times from a Google Sheet and distribute to sensors."""

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict) -> None:
        self.sheet_url: str = config[CONF_SHEET_URL]
        self.date_column: str = config[CONF_DATE_COLUMN]
        self.date_format: str = config[CONF_DATE_FORMAT]
        self.column_mapping: dict[str, str] = config[CONF_COLUMN_MAPPING]
        self.enabled_prayers: list[str] = config[CONF_ENABLED_PRAYERS]
        self._session: aiohttp.ClientSession | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> dict[str, str | None]:
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

        return extract_prayer_times(row, self.column_mapping, self.enabled_prayers)

    async def async_shutdown(self) -> None:
        """Close the aiohttp session on unload."""
        if self._session and not self._session.closed:
            await self._session.close()
