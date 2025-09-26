"""CloudHawk Lawn Mower platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lawn_mower import LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CloudHawkDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CloudHawk lawn mower platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([CloudHawkLawnMowerEntity(coordinator)])


class CloudHawkLawnMowerEntity(CoordinatorEntity, LawnMowerEntity):
    """CloudHawk lawn mower entity."""
    
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )
    
    def __init__(self, coordinator: CloudHawkDataUpdateCoordinator) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_name.lower().replace(' ', '_').replace('-', '_')}_lawn_mower"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": coordinator.device_name,
            "manufacturer": "CloudHawk",
            "model": "Lawn Mower",
            "sw_version": coordinator.data.get("firmware_version") if coordinator.data else None,
        }
    
    @property
    def name(self) -> str:
        """Return the name of the lawn mower."""
        return self.coordinator.device_name
    
    @property
    def activity(self) -> str | None:
        """Return the current activity of the lawn mower."""
        if not self.coordinator.data:
            return None
        
        status = self.coordinator.data.get("status", "").lower()
        
        # Map CloudHawk status to Home Assistant lawn mower activity
        # CloudHawk states: unknown, idle, mowing, docked, returning, stopped
        if status == "mowing":
            return "mowing"
        elif status == "returning":
            return "returning_to_base"
        elif status == "docked":
            return "docked"
        elif status in ["idle", "stopped"]:
            return "paused"
        elif status == "unknown":
            return "error"  # Unknown state is treated as error
        else:
            return "paused"  # Default fallback for any unexpected status
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        
        attributes = {
            "battery_level": self.coordinator.data.get("battery_level"),
            "is_charging": self.coordinator.data.get("is_charging"),
            "signal_type": self.coordinator.data.get("signal_type"),
            "firmware_version": self.coordinator.data.get("firmware_version"),
            "serial_number": self.coordinator.data.get("serial_number"),
            "trimming_enabled": self.coordinator.data.get("trimming_enabled"),
            "has_schedule": self.coordinator.data.get("has_schedule"),
            "fault_count": len(self.coordinator.data.get("fault_records", [])),
        }
        
        return attributes
    
    async def async_start_mowing(self) -> None:
        """Start mowing."""
        await self.coordinator.send_command("start")
    
    async def async_pause(self) -> None:
        """Pause mowing."""
        await self.coordinator.send_command("stop")
    
    async def async_dock(self) -> None:
        """Dock the lawn mower."""
        await self.coordinator.send_command("dock")
