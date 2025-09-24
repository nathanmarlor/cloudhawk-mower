"""CloudHawk Lawn Mower button platform."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CloudHawkDataUpdateCoordinator
from .const import DOMAIN

BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="start",
        name="Mow Now",
        icon="mdi:play",
    ),
    ButtonEntityDescription(
        key="spiral",
        name="Spiral Cut",
        icon="mdi:spiral",
    ),
    ButtonEntityDescription(
        key="edge",
        name="Edge Cut",
        icon="mdi:square-outline",
    ),
    ButtonEntityDescription(
        key="stop",
        name="Stop Mowing",
        icon="mdi:stop",
    ),
    ButtonEntityDescription(
        key="dock",
        name="Return to Dock",
        icon="mdi:home",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CloudHawk button platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        CloudHawkButtonEntity(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    
    async_add_entities(entities)


class CloudHawkButtonEntity(CoordinatorEntity, ButtonEntity):
    """CloudHawk button entity."""
    
    def __init__(
        self,
        coordinator: CloudHawkDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
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
        """Return the name of the button."""
        return f"{self.coordinator.device_name} {self.entity_description.name}"
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
    
    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.send_command(self.entity_description.key)
