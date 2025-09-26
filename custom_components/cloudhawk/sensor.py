"""CloudHawk Lawn Mower sensor platform."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CloudHawkDataUpdateCoordinator
from .const import DOMAIN

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="signal_type",
        name="Boundary Signal",
        icon="mdi:signal",
    ),
    SensorEntityDescription(
        key="status",
        name="Mower Status",
        icon="mdi:state-machine",
    ),
    SensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
        icon="mdi:chip",
    ),
    SensorEntityDescription(
        key="serial_number",
        name="Serial Number",
        icon="mdi:identifier",
    ),
    SensorEntityDescription(
        key="fault_count",
        name="Fault Count",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CloudHawk sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        CloudHawkSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    
    async_add_entities(entities)


class CloudHawkSensorEntity(CoordinatorEntity, SensorEntity):
    """CloudHawk sensor entity."""
    
    def __init__(
        self,
        coordinator: CloudHawkDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Use device name for unique_id to get better entity names
        device_id = coordinator.device_name.lower().replace(" ", "_").replace("-", "_")
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": coordinator.device_name,
            "manufacturer": "CloudHawk",
            "model": "Lawn Mower",
            "sw_version": coordinator.data.get("firmware_version") if coordinator.data else None,
        }
    
    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.coordinator.device_name} {self.entity_description.name}"
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        
        key = self.entity_description.key
        
        if key == "fault_count":
            fault_records = self.coordinator.data.get("fault_records", [])
            return len(fault_records)
        
        return self.coordinator.data.get(key)
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return entity specific state attributes."""
        if not self.coordinator.data:
            return None
        
        attributes = {}
        
        # Add charging status to battery sensor
        if self.entity_description.key == "battery_level":
            attributes["charging"] = self.coordinator.data.get("is_charging", False)
        
        
        # Add trimming and ultrasonic status
        if self.entity_description.key == "signal_type":
            attributes["trimming_enabled"] = self.coordinator.data.get("trimming_enabled", False)
            attributes["ultrasonic_enabled"] = self.coordinator.data.get("ultrasonic_enabled", False)
        
        # Add fault details to fault count sensor
        if self.entity_description.key == "fault_count":
            fault_records = self.coordinator.data.get("fault_records", [])
            if fault_records:
                # Show last 3 faults
                recent_faults = []
                for fault in fault_records[-3:]:
                    recent_faults.append(f"{fault.timestamp}: Error {fault.error_code}")
                attributes["recent_faults"] = recent_faults
        
        # Add additional info to status sensor
        if self.entity_description.key == "status":
            attributes["device_type"] = "Lawn Mower"
        
        return attributes if attributes else None
