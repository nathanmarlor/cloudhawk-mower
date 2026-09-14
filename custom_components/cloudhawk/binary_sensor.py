"""CloudHawk binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CloudHawkConfigEntry
from .entity import CloudHawkEntity
from .protocol import MowerData, MowerState


@dataclass(frozen=True, kw_only=True)
class CloudHawkBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[MowerData], bool | None]


BINARY_SENSORS: tuple[CloudHawkBinaryDescription, ...] = (
    CloudHawkBinaryDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: d.charging,
    ),
    # blade/cover/work notifications (0x88/0x8a/0x87) are never emitted by MB400
    # firmware RM V6.01 - confirmed absent across a full mow+dock cycle - so these
    # stay unknown here. Disabled by default; enable if your model does send them.
    CloudHawkBinaryDescription(
        key="blade",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.blade_running,
    ),
    CloudHawkBinaryDescription(
        key="cover",
        device_class=BinarySensorDeviceClass.OPENING,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.cover_open,
    ),
    CloudHawkBinaryDescription(
        key="working",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.working,
    ),
    CloudHawkBinaryDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: (
            d.activity == MowerState.ERROR if d.state_code is not None else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities = [CloudHawkBinarySensor(coordinator, d) for d in BINARY_SENSORS]
    entities.append(CloudHawkConnectedSensor(coordinator))
    async_add_entities(entities)


class CloudHawkBinarySensor(CloudHawkEntity, BinarySensorEntity):
    entity_description: CloudHawkBinaryDescription

    def __init__(self, coordinator, description: CloudHawkBinaryDescription) -> None:
        super().__init__(coordinator, description)
        self._attr_translation_key = description.key

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.data)


class CloudHawkConnectedSensor(CloudHawkEntity, BinarySensorEntity):
    """BLE link state; always available so it can report False."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connected"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, BinarySensorEntityDescription(key="connected"))

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected
