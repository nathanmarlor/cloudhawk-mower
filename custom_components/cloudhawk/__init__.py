"""CloudHawk Lawn Mower integration for Home Assistant."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloudhawk_mower import CloudHawkMower
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.SWITCH]

# No regular polling - updates triggered by mower data callbacks
UPDATE_INTERVAL = timedelta(hours=1)  # Very long interval as fallback


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CloudHawk from a config entry."""
    address = entry.data["address"]
    name = entry.data.get("name", "CloudHawk Mower")
    
    mower = CloudHawkMower()
    
    # Create coordinator first
    coordinator = CloudHawkDataUpdateCoordinator(
        hass,
        mower=mower,
        address=address,
        name=name,
    )
    
    # Set up callbacks to be notified when mower sends new data or connection status changes
    mower.set_data_update_callback(coordinator._on_mower_data_update)
    mower.set_connection_status_callback(coordinator._on_connection_status_change)
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    # Set up platforms first
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Start connection establishment as first task after setup
    asyncio.create_task(coordinator._establish_connection())
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.mower.disconnect()
    
    return unload_ok


class CloudHawkDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the CloudHawk mower."""
    
    def __init__(self, hass: HomeAssistant, mower: CloudHawkMower, address: str, name: str):
        """Initialize."""
        self.mower = mower
        self.address = address
        self.device_name = name  # Use device_name for entities
        self._last_successful_data = None
        self.hass = hass
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} Coordinator",  # Internal coordinator name
            update_interval=UPDATE_INTERVAL,
        )

    @property
    def _attr_entity_registry_enabled_default(self) -> bool:
        """Disable coordinator entity by default."""
        return False
    
    def _on_mower_data_update(self):
        """Callback triggered when mower sends new data"""
        _LOGGER.debug("New mower data received, scheduling HA update")
        
        # Schedule an async update in the event loop
        def schedule_update():
            asyncio.create_task(self.async_request_refresh())
        
        # Run in the event loop if we're in one, otherwise schedule it
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(schedule_update)
        except RuntimeError:
            # No event loop running, schedule it for later
            asyncio.create_task(self.async_request_refresh())
    
    def _on_connection_status_change(self):
        """Callback triggered when mower connection status changes"""
        _LOGGER.info(f"Connection status changed, mower connected: {self.mower.is_connected()}")
        
        # Schedule an async update in the event loop
        def schedule_update():
            asyncio.create_task(self.async_request_refresh())
        
        # Run in the event loop if we're in one, otherwise schedule it
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(schedule_update)
        except RuntimeError:
            # No event loop running, schedule it for later
            asyncio.create_task(self.async_request_refresh())
    

    async def _async_update_data(self):
        """Update data from library store.
        
        This method gets data from the library's response store.
        """
        try:      
            # Get mower information from the library's response store
            mower_info = await self.mower.get_mower_info()
            
            # Build the data response
            data = {
                "serial_number": mower_info.serial_number,
                "firmware_version": mower_info.firmware_version,
                "battery_level": mower_info.battery_level,
                "is_charging": mower_info.is_charging,
                "signal_type": mower_info.signal_type.name,
                "trimming_enabled": mower_info.trimming_enabled,
                "has_schedule": mower_info.has_schedule,
                "status": mower_info.status.value.replace('_', ' ').title() if mower_info.status else "Unknown",
                "fault_records": mower_info.fault_records,
            }
            
            # Store successful data for reference
            self._last_successful_data = data
            _LOGGER.debug("Successfully updated mower data from store")
            return data
            
        except Exception as ex:
            _LOGGER.error(f"Error getting mower data: {ex}")
            raise UpdateFailed(f"Error getting mower data: {ex}") from ex
    
    async def _establish_connection(self):
        """Establish connection to mower, retrying until successful"""
        _LOGGER.info("Establishing connection to mower")
        
        while True:
            try:
                if await self.mower.connect(self.address):
                    _LOGGER.info("Connection established successfully")
                    return
                else:
                    _LOGGER.warning("Connection failed, retrying in 5 seconds")
                    await asyncio.sleep(5)
            except Exception as ex:
                _LOGGER.error(f"Error during connection attempt: {ex}, retrying in 5 seconds")
                await asyncio.sleep(5)
    
    async def send_command(self, command_name: str) -> bool:
        """Send a command to the mower via the library."""
        try:
            _LOGGER.debug(f"Sending command: {command_name}")
            
            if command_name == "start":
                result = await self.mower.start_mowing()
            elif command_name == "spiral":
                result = await self.mower.start_spiral_cutting()
            elif command_name == "edge":
                result = await self.mower.start_edge_cutting()
            elif command_name == "stop":
                result = await self.mower.stop_mowing()
            elif command_name == "dock":
                result = await self.mower.return_to_dock()
            else:
                _LOGGER.error(f"Unknown command: {command_name}")
                return False
            
            if result:
                _LOGGER.debug(f"Command '{command_name}' successful")
            else:
                _LOGGER.warning(f"Command '{command_name}' failed")
            
            return result
            
        except Exception as ex:
            _LOGGER.error(f"Error sending command {command_name}: {ex}")
            return False
