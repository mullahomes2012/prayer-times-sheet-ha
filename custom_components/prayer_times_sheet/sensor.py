"""Sensor platform for Prayer Times Sheet."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CUSTOM_NAMES,
    CONF_ENABLED_PRAYERS,
    CONF_END_TIMES,
    CONF_SHEET_NAME,
    CONF_SHEET_PREFIX,
    DOMAIN,
    END_TIME_NONE,
    PRAYER_SLOT_LABELS,
)
from .coordinator import PrayerTimesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a config entry."""
    coordinator: PrayerTimesCoordinator = hass.data[DOMAIN][entry.entry_id]

    enabled = entry.options.get(
        CONF_ENABLED_PRAYERS,
        entry.data.get(CONF_ENABLED_PRAYERS, []),
    )
    custom_names: dict[str, str] = entry.options.get(
        CONF_CUSTOM_NAMES,
        entry.data.get(CONF_CUSTOM_NAMES, {}),
    )
    end_time_config: dict[str, dict] = entry.options.get(
        CONF_END_TIMES,
        entry.data.get(CONF_END_TIMES, {}),
    )
    sheet_name: str = entry.data[CONF_SHEET_NAME]
    sheet_prefix: str = entry.options.get(
        CONF_SHEET_PREFIX,
        entry.data.get(CONF_SHEET_PREFIX, ""),
    ).strip()

    entities: list[SensorEntity] = []
    for prayer_key in enabled:
        # Start time sensor
        entities.append(
            PrayerTimeSensor(
                coordinator, entry, prayer_key, sheet_name,
                sheet_prefix, custom_names, is_end=False,
            )
        )
        # End time sensor — only if mode is not "none"
        cfg = end_time_config.get(prayer_key, {})
        if cfg.get("mode", END_TIME_NONE) != END_TIME_NONE:
            entities.append(
                PrayerTimeSensor(
                    coordinator, entry, prayer_key, sheet_name,
                    sheet_prefix, custom_names, is_end=True,
                )
            )

    async_add_entities(entities)


def _build_name(
    sheet_name: str,
    sheet_prefix: str,
    prayer_key: str,
    custom_names: dict[str, str],
    is_end: bool,
) -> str:
    """Build the sensor display name."""
    default_label = PRAYER_SLOT_LABELS.get(
        prayer_key, prayer_key.replace("_", " ").title()
    )
    label = custom_names.get(prayer_key, default_label)
    suffix = " End" if is_end else ""

    if sheet_prefix:
        return f"{sheet_prefix} {label}{suffix}"
    return f"{sheet_name} {label}{suffix}"


class PrayerTimeSensor(CoordinatorEntity, SensorEntity):
    """A single prayer time sensor (start or end)."""

    def __init__(
        self,
        coordinator: PrayerTimesCoordinator,
        entry: ConfigEntry,
        prayer_key: str,
        sheet_name: str,
        sheet_prefix: str,
        custom_names: dict[str, str],
        is_end: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._prayer_key = prayer_key
        self._sheet_name = sheet_name
        self._entry_id = entry.entry_id
        self._is_end = is_end

        self._attr_name = _build_name(
            sheet_name, sheet_prefix, prayer_key, custom_names, is_end
        )
        uid_suffix = "_end" if is_end else ""
        self._attr_unique_id = f"{entry.entry_id}_{prayer_key}{uid_suffix}"
        self._attr_icon = "mdi:clock-end" if is_end else "mdi:clock-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors for this sheet under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._sheet_name,
            manufacturer="Google Sheets",
            model="Prayer Times",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | None:
        """Return today's time for this prayer."""
        if self.coordinator.data is None:
            return None
        if self._is_end:
            return self.coordinator.data.get("end_times", {}).get(self._prayer_key)
        return self.coordinator.data.get("times", {}).get(self._prayer_key)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "prayer": self._prayer_key,
            "sheet": self._sheet_name,
            "type": "end" if self._is_end else "start",
        }
