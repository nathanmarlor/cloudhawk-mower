"""CloudHawk switches - settings with real setters, read back after each write."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CloudHawkConfigEntry
from .cloudhawk_mower import CloudHawkMower
from .entity import CloudHawkEntity
from .protocol import MowerData


@dataclass(frozen=True, kw_only=True)
class CloudHawkSwitchDescription(SwitchEntityDescription):
    value_fn: Callable[[MowerData], bool | None]
    set_fn: Callable[[CloudHawkMower, bool], Awaitable[None]]


SWITCHES: tuple[CloudHawkSwitchDescription, ...] = (
    CloudHawkSwitchDescription(
        key="trimming",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.trimming,
        set_fn=lambda m, on: m.set_trimming(on),
    ),
    CloudHawkSwitchDescription(
        key="ultrasonic",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.ultrasonic,
        set_fn=lambda m, on: m.set_ultrasonic(on),
    ),
    CloudHawkSwitchDescription(
        key="rain_sensor",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.rain_sensor,
        set_fn=lambda m, on: m.set_rain_sensor(on),
    ),
    CloudHawkSwitchDescription(
        key="mowing_time_mode",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda d: d.mowing_time_mode,
        set_fn=lambda m, on: m.set_mowing_time_mode(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(CloudHawkSwitch(entry.runtime_data, d) for d in SWITCHES)


class CloudHawkSwitch(CloudHawkEntity, SwitchEntity):
    entity_description: CloudHawkSwitchDescription

    def __init__(self, coordinator, description: CloudHawkSwitchDescription) -> None:
        super().__init__(coordinator, description)
        self._attr_translation_key = description.key

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator.mower, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator.mower, False)
        self.async_write_ha_state()
