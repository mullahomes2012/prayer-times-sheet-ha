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
    CONF_SHEET_NAME,
    CONF_SHEET_PREFIX,
    DOMAIN,
    PRAYER_SLOT_LABELS,
)
from .coordinator import PrayerTimesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrayerTimesCoordinator = hass.data[DOMAIN][entry.entry_id]

    enabled = entry.options.get(
        CONF_ENABLED_PRAYERS,
        entry.data.get(CONF_ENABLED_PRAYERS, []),
    )
    custom_names: dict[str, str] = entry.options.get(
        CONF_CUSTOM_NAMES,
        entry.data.get(CONF_CUSTOM_NAMES, {}),
    )
    sheet_name: str = entry.data[CONF_SHEET_NAME]
    sheet_prefix: str = entry.options.get(
        CONF_SHEET_PREFIX,
        entry.data.get(CONF_SHEET_PREFIX, ""),
    ).strip()

    entities = [
        PrayerTimeSensor(coordinator, entry, k, sheet_name, sheet_prefix, custom_names)
        for k in enabled
    ]
    async_add_entities(entities)


class PrayerTimeSensor(CoordinatorEntity, SensorEntity):
    """A single prayer time sensor."""

    def __init__(
        self,
        coordinator: PrayerTimesCoordinator,
        entry: ConfigEntry,
        prayer_key: str,
        sheet_name: str,
        sheet_prefix: str,
        custom_names: dict[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._prayer_key = prayer_key
        self._sheet_name = sheet_name
        self._entry_id = entry.entry_id

        default_label = PRAYER_SLOT_LABELS.get(
            prayer_key, prayer_key.replace("_", " ").title()
        )
        label = custom_names.get(prayer_key, default_label)
        prefix = sheet_prefix if sheet_prefix else sheet_name
        self._attr_name = f"{prefix} {label}"
        self._attr_unique_id = f"{entry.entry_id}_{prayer_key}"
        self._attr_icon = "mdi:clock-outline"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._sheet_name,
            manufacturer="Mullatech",
            model="Awqaat",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._prayer_key)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "prayer": self._prayer_key,
            "sheet": self._sheet_name,
        }
