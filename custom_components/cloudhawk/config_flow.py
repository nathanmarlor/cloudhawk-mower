"""Config flow for CloudHawk Lawn Mower integration."""
import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .cloudhawk_mower import CloudHawkMower
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("address", description="Enter the Bluetooth MAC address of your CloudHawk mower"): str,
        vol.Optional("name", default="CloudHawk Mower", description="Give your mower a friendly name"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    mower = CloudHawkMower()
    
    try:
        if not await mower.connect(data["address"]):
            raise CannotConnect
        
        # Get basic info to validate connection
        info = await mower.get_mower_info()
        serial = info.serial_number or "Unknown"
        
        await mower.disconnect()
        
        return {"title": f"CloudHawk {serial}", "serial": serial}
        
    except Exception as ex:
        _LOGGER.error(f"Connection test failed: {ex}")
        raise CannotConnect from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CloudHawk Lawn Mower."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_devices = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step for manual configuration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(user_input["address"])
                self._abort_if_unique_id_configured()
                
                # If user didn't change the default name, use the device title instead
                if user_input["name"] == "CloudHawk Mower":
                    user_input["name"] = info["title"]
                
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_bluetooth(self, discovery_info) -> FlowResult:
        """Handle automatic Bluetooth discovery."""
        address = discovery_info.address
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        
        # Try to get device name
        device_name = discovery_info.name or "CloudHawk Mower"
        
        self.context["title_placeholders"] = {"name": device_name}
        
        # Store discovery info for later
        self.discovered_devices[address] = {
            "address": address,
            "name": device_name,
        }
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm automatic Bluetooth discovery."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            address = self.unique_id
            device_info = self.discovered_devices.get(address, {})
            
            data = {
                "address": address,
                "name": device_info.get("name", "CloudHawk Mower"),
            }
            
            try:
                info = await validate_input(self.hass, data)
                # If using default name, use the device title instead
                if data["name"] == "CloudHawk Mower":
                    data["name"] = info["title"]
                return self.async_create_entry(title=info["title"], data=data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self.context["title_placeholders"]["name"]},
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
