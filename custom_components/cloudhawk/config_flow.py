"""Config flow for CloudHawk Lawn Mower."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.device_registry import format_mac

from .cloudhawk_mower import INFO_COMMANDS, CloudHawkMower
from .const import DEFAULT_NAME, DOMAIN
from .protocol import SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class CloudHawkConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}  # address -> display name
        self._discovery: BluetoothServiceInfoBleak | None = None

    async def _probe(self, address: str) -> str | None:
        """Connect once and return the serial number (or None on failure)."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address, connectable=True
        )
        if ble_device is None:
            return None
        mower = CloudHawkMower(address, ble_device)
        try:
            await mower.connect()
            await mower.refresh(INFO_COMMANDS)
            return mower.data.serial or ""
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Probe of %s failed: %s", address, err)
            return None
        finally:
            await mower.disconnect()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            name = user_input.get(CONF_NAME) or DEFAULT_NAME
            if (serial := await self._probe(self._discovery.address)) is None:
                return self.async_abort(reason="cannot_connect")
            return self._entry(self._discovery.address, name, serial)
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_NAME, default=DEFAULT_NAME): str}
            ),
            description_placeholders={
                "name": self._discovery.name or self._discovery.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(format_mac(address), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            name = user_input.get(CONF_NAME) or DEFAULT_NAME
            if (serial := await self._probe(address)) is not None:
                return self._entry(address, name, serial)
            errors["base"] = "cannot_connect"

        current = self._async_current_ids()
        for info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            if format_mac(info.address) in current:
                continue
            if SERVICE_UUID in info.service_uuids or (info.name or "").startswith("SN"):
                self._discovered[info.address] = (
                    f"{info.name or 'CloudHawk'} ({info.address})"
                )
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self._discovered),
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    def _entry(self, address: str, name: str, serial: str) -> ConfigFlowResult:
        title = f"{name} {serial}".strip() if serial and name == DEFAULT_NAME else name
        return self.async_create_entry(
            title=title, data={CONF_ADDRESS: address, CONF_NAME: name}
        )
