"""CloudHawk numeric settings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CloudHawkConfigEntry
from .cloudhawk_mower import CloudHawkMower
from .entity import CloudHawkEntity
from .protocol import MowerData


@dataclass(frozen=True, kw_only=True)
class CloudHawkNumberDescription(NumberEntityDescription):
    value_fn: Callable[[MowerData], int | None]
    set_fn: Callable[[CloudHawkMower, int], Awaitable[None]]


NUMBERS: tuple[CloudHawkNumberDescription, ...] = (
    CloudHawkNumberDescription(
        key="ultrasonic_distance",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.ultrasonic_distance,
        set_fn=lambda m, v: m.set_ultrasonic_distance(v),
    ),
    CloudHawkNumberDescription(
        key="rain_delay",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.rain_delay,
        set_fn=lambda m, v: m.set_rain_delay(v),
    ),
    CloudHawkNumberDescription(
        key="cut_width",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.cut_width,
        set_fn=lambda m, v: m.set_cut_width(v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(CloudHawkNumber(entry.runtime_data, d) for d in NUMBERS)


class CloudHawkNumber(CloudHawkEntity, NumberEntity):
    entity_description: CloudHawkNumberDescription

    def __init__(self, coordinator, description: CloudHawkNumberDescription) -> None:
        super().__init__(coordinator, description)
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> int | None:
        return self.entity_description.value_fn(self.data)

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.coordinator.mower, int(value))
        self.async_write_ha_state()
