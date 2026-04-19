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
    CONF_CUSTOM_NAMES,
    CONF_DATE_COLUMN,
    CONF_DATE_FORMAT,
    CONF_ENABLED_PRAYERS,
    CONF_END_TIMES,
    CONF_SHEET_NAME,
    CONF_SHEET_PREFIX,
    CONF_SHEET_URL,
    DEFAULT_END_TIMES,
    DOMAIN,
    END_TIME_MINUTES,
    END_TIME_NONE,
    END_TIME_PRAYER,
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
    """Multi-step config flow: URL → columns → mapping → prayer selection."""

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

    # Step 1 — Sheet URL + name + prefix + date format
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

    # Step 2 — Pick the date column
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

    # Step 3 — Map each prayer slot to a sheet column
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

        col_choices = ["__none__"] + self._columns
        schema_dict: dict = {}
        for prayer_key, label in PRAYER_SLOTS:
            default = self._guess_column(prayer_key)
            schema_dict[vol.Optional(prayer_key, default=default or "__none__")] = (
                vol.In(col_choices)
            )

        return self.async_show_form(
            step_id="map_prayers",
            data_schema=vol.Schema(schema_dict),
        )

    def _guess_column(self, prayer_key: str) -> str | None:
        key_lower = prayer_key.replace("_", "").lower()
        for col in self._columns:
            col_lower = col.replace("_", "").replace(" ", "").lower()
            if key_lower == col_lower:
                return col
        return None

    # Step 4 — Choose which prayers to enable
    async def async_step_select_prayers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        mapped_keys = list(self._column_mapping.keys())

        if user_input is not None:
            self._enabled_prayers = [
                k for k in mapped_keys if user_input.get(k, False)
            ]
            return self._create_entry()

        schema_dict = {
            vol.Optional(k, default=True): bool for k in mapped_keys
        }

        return self.async_show_form(
            step_id="select_prayers",
            data_schema=vol.Schema(schema_dict),
        )

    def _create_entry(self) -> FlowResult:
        # Apply default end times for enabled prayers
        end_times = {}
        for k in self._enabled_prayers:
            if k in DEFAULT_END_TIMES:
                mode, value = DEFAULT_END_TIMES[k]
                end_times[k] = {"mode": mode, "value": value}
            else:
                end_times[k] = {"mode": END_TIME_NONE, "value": ""}

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
                CONF_END_TIMES: end_times,
                CONF_CUSTOM_NAMES: {},
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PrayerTimesOptionsFlow(config_entry)


class PrayerTimesOptionsFlow(config_entries.OptionsFlow):
    """Options: enable/disable → end times → rename → prefix."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._enabled_prayers: list[str] = []
        self._end_times: dict[str, dict] = {}
        self._all_prayer_keys: list[str] = []

    def _current(self, key: str, default: Any) -> Any:
        """Get value from options first, then data."""
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    # Step 1 — Enable / disable
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        mapped_keys = list(
            self._config_entry.data.get(CONF_COLUMN_MAPPING, {}).keys()
        )
        self._all_prayer_keys = mapped_keys
        currently_enabled: list[str] = self._current(CONF_ENABLED_PRAYERS, [])

        if user_input is not None:
            self._enabled_prayers = [
                k for k in mapped_keys if user_input.get(k, False)
            ]
            return await self.async_step_end_times()

        schema_dict = {
            vol.Optional(k, default=(k in currently_enabled)): bool
            for k in mapped_keys
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )

    # Step 2 — End times
    # One dropdown per enabled prayer: "None", "X minutes", or another prayer name
    async def async_step_end_times(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        current_end_times: dict[str, dict] = self._current(CONF_END_TIMES, {})

        if user_input is not None:
            end_times: dict[str, dict] = {}
            for k in self._enabled_prayers:
                choice = user_input.get(k, END_TIME_NONE)
                if choice == END_TIME_NONE:
                    end_times[k] = {"mode": END_TIME_NONE, "value": ""}
                elif choice.startswith("minutes:"):
                    mins = choice.split(":", 1)[1]
                    end_times[k] = {"mode": END_TIME_MINUTES, "value": mins}
                else:
                    # It's a prayer key
                    end_times[k] = {"mode": END_TIME_PRAYER, "value": choice}
            self._end_times = end_times
            return await self.async_step_rename()

        # Build choices: none + minute options + all other enabled prayer keys
        minute_options = [f"minutes:{m}" for m in ["5", "10", "15", "20", "30", "45", "60", "90", "120"]]
        prayer_options = [k for k in self._enabled_prayers]

        choices = (
            [END_TIME_NONE]
            + minute_options
            + prayer_options
        )

        # Human-readable labels for the dropdown
        choice_labels = {END_TIME_NONE: "No end time"}
        for m in ["5", "10", "15", "20", "30", "45", "60", "90", "120"]:
            choice_labels[f"minutes:{m}"] = f"{m} minutes after start"
        for k in prayer_options:
            choice_labels[k] = f"At {PRAYER_SLOT_LABELS.get(k, k)}"

        def _default_for(k: str) -> str:
            cfg = current_end_times.get(k, {})
            mode = cfg.get("mode", END_TIME_NONE)
            if mode == END_TIME_NONE:
                # Apply default if not previously configured
                if k in DEFAULT_END_TIMES:
                    d_mode, d_val = DEFAULT_END_TIMES[k]
                    if d_mode == END_TIME_MINUTES:
                        return f"minutes:{d_val}"
                    elif d_mode == END_TIME_PRAYER and d_val in self._enabled_prayers:
                        return d_val
                return END_TIME_NONE
            elif mode == END_TIME_MINUTES:
                return f"minutes:{cfg.get('value', '15')}"
            else:
                val = cfg.get("value", "")
                return val if val in choices else END_TIME_NONE

        schema_dict = {
            vol.Optional(k, default=_default_for(k)): vol.In(choices)
            for k in self._enabled_prayers
        }

        return self.async_show_form(
            step_id="end_times",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "hint": "Set when each prayer ends. Choose 'No end time' to skip."
            },
        )

    # Step 3 — Custom names
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
            current = current_names.get(k, default_label)
            schema_dict[vol.Optional(k, default=current)] = str

        return self.async_show_form(
            step_id="rename",
            data_schema=vol.Schema(schema_dict),
        )

    # Step 4 — Sheet prefix
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
                    CONF_END_TIMES: self._end_times,
                    CONF_CUSTOM_NAMES: custom_names,
                    CONF_SHEET_PREFIX: user_input.get(CONF_SHEET_PREFIX, "").strip(),
                },
            )

        return self.async_show_form(
            step_id="prefix",
            data_schema=vol.Schema({
                vol.Optional(CONF_SHEET_PREFIX, default=current_prefix): str,
            }),
            description_placeholders={
                "hint": (
                    "Optional: a prefix added to all sensor names from this sheet. "
                    "E.g. 'Green Lane' → 'Green Lane Fajr Jama'ah'. "
                    "Leave blank to use the sheet name instead."
                )
            },
        )
