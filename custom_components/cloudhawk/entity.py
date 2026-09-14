"""Shared entity base for CloudHawk."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CloudHawkCoordinator
from .const import DOMAIN, MANUFACTURER
from .protocol import MowerData


class CloudHawkEntity(CoordinatorEntity[CloudHawkCoordinator]):
    """Base entity: MAC-based unique id, shared device info, availability from the link."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CloudHawkCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator)
        key = description.key if description else "lawn_mower"
        if description:
            self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{key}"
        data = coordinator.mower.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.device_name,
            manufacturer=MANUFACTURER,
            model="Robotic Lawn Mower",
            serial_number=data.serial,
            sw_version=data.firmware,
        )

    @property
    def data(self) -> MowerData:
        return self.coordinator.mower.data

    @property
    def available(self) -> bool:
        return self.coordinator.connected
