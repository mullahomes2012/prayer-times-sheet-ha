"""Config flow for Prayer Times Sheet integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_COLUMN_MAPPING,
    CONF_DATE_COLUMN,
    CONF_DATE_FORMAT,
    CONF_ENABLED_PRAYERS,
    CONF_SHEET_NAME,
    CONF_SHEET_URL,
    DOMAIN,
    PRAYER_SLOT_KEYS,
    PRAYER_SLOT_LABELS,
    PRAYER_SLOTS,
)
from .sheet_data import build_csv_url, get_columns

_LOGGER = logging.getLogger(__name__)

DATE_FORMAT_OPTIONS = [
    "%-d/%-m/%Y",   # 19/4/2026  (no leading zeros, Linux)
    "%d/%m/%Y",     # 19/04/2026
    "%Y-%m-%d",     # 2026-04-19
    "%d-%m-%Y",     # 19-04-2026
    "%d %b %Y",     # 19 Apr 2026
    "%d %B %Y",     # 19 April 2026
]


class PrayerTimesSheetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Multi-step config flow: URL → columns → mapping → prayer selection."""

    VERSION = 1

    def __init__(self) -> None:
        self._sheet_url: str = ""
        self._sheet_name: str = ""
        self._date_format: str = ""
        self._date_column: str = ""
        self._columns: list[str] = []
        self._column_mapping: dict[str, str] = {}
        self._enabled_prayers: list[str] = []

    # ------------------------------------------------------------------ #
    # Step 1 — Sheet URL + name + date format                             #
    # ------------------------------------------------------------------ #
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_SHEET_URL].strip()
            try:
                csv_url = build_csv_url(url)
            except ValueError:
                errors[CONF_SHEET_URL] = "invalid_url"
            else:
                async with aiohttp.ClientSession() as session:
                    try:
                        cols = await get_columns(session, csv_url)
                    except Exception:  # noqa: BLE001
                        errors["base"] = "cannot_connect"
                    else:
                        if not cols:
                            errors["base"] = "empty_sheet"
                        else:
                            self._sheet_url = csv_url
                            self._sheet_name = user_input[CONF_SHEET_NAME].strip()
                            self._date_format = user_input[CONF_DATE_FORMAT]
                            self._columns = cols
                            return await self.async_step_date_column()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SHEET_URL): str,
                    vol.Required(CONF_SHEET_NAME, default="My Masjid"): str,
                    vol.Required(CONF_DATE_FORMAT, default="%Y-%m-%d"): vol.In(
                        DATE_FORMAT_OPTIONS
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "url_hint": "Paste the published Google Sheet URL"
            },
        )

    # ------------------------------------------------------------------ #
    # Step 2 — Pick the date column                                       #
    # ------------------------------------------------------------------ #
    async def async_step_date_column(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._date_column = user_input[CONF_DATE_COLUMN]
            return await self.async_step_map_prayers()

        return self.async_show_form(
            step_id="date_column",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DATE_COLUMN): vol.In(self._columns),
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 3 — Map each prayer slot to a sheet column (or "none")        #
    # ------------------------------------------------------------------ #
    async def async_step_map_prayers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._column_mapping = {
                prayer_key: col
                for prayer_key, col in user_input.items()
                if col and col != "__none__"
            }
            return await self.async_step_select_prayers()

        none_option = "__none__ (not in sheet)"
        col_choices = ["__none__"] + self._columns

        schema_dict: dict = {}
        for prayer_key, label in PRAYER_SLOTS:
            # Try to auto-suggest a column with a similar name
            default = self._guess_column(prayer_key)
            schema_dict[vol.Optional(prayer_key, default=default or "__none__")] = (
                vol.In(col_choices)
            )

        return self.async_show_form(
            step_id="map_prayers",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "hint": (
                    "Map each prayer to its column in the sheet. "
                    "Set to '__none__' if not present."
                )
            },
        )

    def _guess_column(self, prayer_key: str) -> str | None:
        """Fuzzy-match a prayer key to a column header."""
        key_lower = prayer_key.replace("_", "").lower()
        for col in self._columns:
            col_lower = col.replace("_", "").replace(" ", "").lower()
            if key_lower == col_lower:
                return col
        return None

    # ------------------------------------------------------------------ #
    # Step 4 — Choose which mapped prayers to enable as HA sensors       #
    # ------------------------------------------------------------------ #
    async def async_step_select_prayers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        mapped_keys = list(self._column_mapping.keys())

        if user_input is not None:
            self._enabled_prayers = [
                k for k in mapped_keys if user_input.get(k, False)
            ]
            return self._create_entry()

        # Default all mapped prayers to enabled
        schema_dict = {
            vol.Optional(k, default=True): bool for k in mapped_keys
        }

        return self.async_show_form(
            step_id="select_prayers",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "hint": "Choose which prayers to create sensors for in Home Assistant."
            },
        )

    def _create_entry(self) -> FlowResult:
        return self.async_create_entry(
            title=self._sheet_name,
            data={
                CONF_SHEET_URL: self._sheet_url,
                CONF_SHEET_NAME: self._sheet_name,
                CONF_DATE_COLUMN: self._date_column,
                CONF_DATE_FORMAT: self._date_format,
                CONF_COLUMN_MAPPING: self._column_mapping,
                CONF_ENABLED_PRAYERS: self._enabled_prayers,
            },
        )

    # ------------------------------------------------------------------ #
    # Options flow — re-run prayer selection after setup                  #
    # ------------------------------------------------------------------ #
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PrayerTimesOptionsFlow(config_entry)


class PrayerTimesOptionsFlow(config_entries.OptionsFlow):
    """Allow the user to change which prayers are enabled after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        mapped_keys: list[str] = self._config_entry.data.get(CONF_COLUMN_MAPPING, {}).keys()
        currently_enabled: list[str] = self._config_entry.data.get(CONF_ENABLED_PRAYERS, [])

        if user_input is not None:
            enabled = [k for k in mapped_keys if user_input.get(k, False)]
            return self.async_create_entry(
                title="",
                data={CONF_ENABLED_PRAYERS: enabled},
            )

        schema_dict = {
            vol.Optional(k, default=(k in currently_enabled)): bool
            for k in mapped_keys
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
