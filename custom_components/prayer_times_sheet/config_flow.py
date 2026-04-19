"""Config flow for Salaah Times integration."""
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
    CONF_CUSTOM_NAMES,
    CONF_DATE_COLUMN,
    CONF_DATE_FORMAT,
    CONF_ENABLED_PRAYERS,
    CONF_SHEET_NAME,
    CONF_SHEET_PREFIX,
    CONF_SHEET_URL,
    DOMAIN,
    PRAYER_SLOT_LABELS,
    PRAYER_SLOTS,
)
from .sheet_data import build_csv_url, get_columns

_LOGGER = logging.getLogger(__name__)

DATE_FORMAT_OPTIONS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%-d/%-m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
]


class PrayerTimesSheetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow: URL → date column → map columns → select prayers."""

    VERSION = 1

    def __init__(self) -> None:
        self._sheet_url: str = ""
        self._sheet_name: str = ""
        self._sheet_prefix: str = ""
        self._date_format: str = ""
        self._date_column: str = ""
        self._columns: list[str] = []
        self._column_mapping: dict[str, str] = {}
        self._enabled_prayers: list[str] = []

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
                            self._sheet_prefix = user_input.get(CONF_SHEET_PREFIX, "").strip()
                            self._date_format = user_input[CONF_DATE_FORMAT]
                            self._columns = cols
                            return await self.async_step_date_column()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SHEET_URL): str,
                vol.Required(CONF_SHEET_NAME, default="My Masjid"): str,
                vol.Optional(CONF_SHEET_PREFIX, default=""): str,
                vol.Required(CONF_DATE_FORMAT, default="%Y-%m-%d"): vol.In(
                    DATE_FORMAT_OPTIONS
                ),
            }),
            errors=errors,
        )

    async def async_step_date_column(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._date_column = user_input[CONF_DATE_COLUMN]
            return await self.async_step_map_prayers()

        return self.async_show_form(
            step_id="date_column",
            data_schema=vol.Schema({
                vol.Required(CONF_DATE_COLUMN): vol.In(self._columns),
            }),
        )

    async def async_step_map_prayers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._column_mapping = {
                k: col for k, col in user_input.items()
                if col and col != "__none__"
            }
            return await self.async_step_select_prayers()

        col_choices = ["__none__"] + self._columns
        schema_dict = {
            vol.Optional(k, default=self._guess_column(k) or "__none__"): vol.In(col_choices)
            for k, _ in PRAYER_SLOTS
        }
        return self.async_show_form(
            step_id="map_prayers",
            data_schema=vol.Schema(schema_dict),
        )

    def _guess_column(self, prayer_key: str) -> str | None:
        key_lower = prayer_key.replace("_", "").lower()
        for col in self._columns:
            if col.replace("_", "").replace(" ", "").lower() == key_lower:
                return col
        return None

    async def async_step_select_prayers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        mapped_keys = list(self._column_mapping.keys())

        if user_input is not None:
            self._enabled_prayers = [k for k in mapped_keys if user_input.get(k, False)]
            return self.async_create_entry(
                title=self._sheet_name,
                data={
                    CONF_SHEET_URL: self._sheet_url,
                    CONF_SHEET_NAME: self._sheet_name,
                    CONF_SHEET_PREFIX: self._sheet_prefix,
                    CONF_DATE_COLUMN: self._date_column,
                    CONF_DATE_FORMAT: self._date_format,
                    CONF_COLUMN_MAPPING: self._column_mapping,
                    CONF_ENABLED_PRAYERS: self._enabled_prayers,
                    CONF_CUSTOM_NAMES: {},
                },
            )

        return self.async_show_form(
            step_id="select_prayers",
            data_schema=vol.Schema({
                vol.Optional(k, default=True): bool for k in mapped_keys
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SalaahTimesOptionsFlow(config_entry)


class SalaahTimesOptionsFlow(config_entries.OptionsFlow):
    """Options: enable/disable → rename → prefix."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._enabled_prayers: list[str] = []

    def _current(self, key: str, default: Any) -> Any:
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        mapped_keys = list(self._config_entry.data.get(CONF_COLUMN_MAPPING, {}).keys())
        currently_enabled: list[str] = self._current(CONF_ENABLED_PRAYERS, [])

        if user_input is not None:
            self._enabled_prayers = [k for k in mapped_keys if user_input.get(k, False)]
            return await self.async_step_rename()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(k, default=(k in currently_enabled)): bool
                for k in mapped_keys
            }),
        )

    async def async_step_rename(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        current_names: dict[str, str] = self._current(CONF_CUSTOM_NAMES, {})

        if user_input is not None:
            custom_names = {
                k: v.strip()
                for k, v in user_input.items()
                if v.strip() and v.strip() != PRAYER_SLOT_LABELS.get(k, k)
            }
            return await self.async_step_prefix(custom_names)

        schema_dict = {}
        for k in self._enabled_prayers:
            default_label = PRAYER_SLOT_LABELS.get(k, k.replace("_", " ").title())
            schema_dict[vol.Optional(k, default=current_names.get(k, default_label))] = str

        return self.async_show_form(
            step_id="rename",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_prefix(
        self,
        custom_names: dict[str, str],
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        current_prefix: str = self._current(CONF_SHEET_PREFIX, "")

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_ENABLED_PRAYERS: self._enabled_prayers,
                    CONF_CUSTOM_NAMES: custom_names,
                    CONF_SHEET_PREFIX: user_input.get(CONF_SHEET_PREFIX, "").strip(),
                },
            )

        return self.async_show_form(
            step_id="prefix",
            data_schema=vol.Schema({
                vol.Optional(CONF_SHEET_PREFIX, default=current_prefix): str,
            }),
        )
