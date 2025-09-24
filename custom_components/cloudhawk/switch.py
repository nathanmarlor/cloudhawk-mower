"""CloudHawk Lawn Mower switch platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CloudHawkDataUpdateCoordinator
from .const import DOMAIN

SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="trimming_enabled",
        name="Boundary Trimming",
        icon="mdi:scissors-cutting",
    ),
    SwitchEntityDescription(
        key="ultrasonic_enabled",
        name="Ultrasonic Sensor",
        icon="mdi:radar",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CloudHawk switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        CloudHawkSwitchEntity(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    ]
    
    async_add_entities(entities)


class CloudHawkSwitchEntity(CoordinatorEntity, SwitchEntity):
    """CloudHawk switch entity."""
    
    def __init__(
        self,
        coordinator: CloudHawkDataUpdateCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": coordinator.device_name,
            "manufacturer": "CloudHawk",
            "model": "Lawn Mower",
            "sw_version": coordinator.data.get("firmware_version") if coordinator.data else None,
        }
    
    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return f"{self.coordinator.device_name} {self.entity_description.name}"
    
    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key, False)
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Note: These would need to be implemented in the CloudHawk library
        # For now, they are read-only switches showing current state
        pass
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Note: These would need to be implemented in the CloudHawk library
        # For now, they are read-only switches showing current state
        pass
