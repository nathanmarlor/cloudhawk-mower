"""CloudHawk Lawn Mower integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .cloudhawk_mower import STATS_COMMANDS, CloudHawkMower
from .const import DEFAULT_NAME, DOMAIN
from .protocol import MowerData
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LAWN_MOWER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

STATS_INTERVAL = timedelta(minutes=10)
RECONNECT_DELAYS = (5, 10, 30, 60)
HEARTBEAT_TIMEOUT = timedelta(minutes=3)  # mower heartbeats every 60 s

type CloudHawkConfigEntry = ConfigEntry[CloudHawkCoordinator]


class CloudHawkCoordinator(DataUpdateCoordinator[MowerData]):
    """Keeps a persistent BLE connection and republishes pushed data."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, mower: CloudHawkMower
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_interval=STATS_INTERVAL,
            config_entry=entry,
        )
        self.entry = entry
        self.mower = mower
        self.address = entry.data[CONF_ADDRESS]
        self.device_name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._disconnected = asyncio.Event()
        self._stop = asyncio.Event()
        self._unsub_listeners = [
            mower.add_listener(self._on_mower_data),
            mower.add_disconnect_listener(self._on_mower_disconnect),
        ]

    # -- availability -------------------------------------------------------

    @property
    def connected(self) -> bool:
        if not self.mower.is_connected:
            return False
        hb = self.mower.data.last_heartbeat
        return hb is None or datetime.now() - hb < HEARTBEAT_TIMEOUT

    # -- mower callbacks (may fire from bleak's thread) ------------------------

    def _on_mower_data(self, data: MowerData) -> None:
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

    def _on_mower_disconnect(self) -> None:
        self.hass.loop.call_soon_threadsafe(self._disconnected.set)
        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    # -- periodic poll ------------------------------------------------------

    async def _async_update_data(self) -> MowerData:
        if self.mower.is_connected:
            if not self.connected:
                # GATT link says connected but heartbeats stopped: drop it so run() reconnects.
                _LOGGER.warning(
                    "%s: no heartbeat for %s, reconnecting",
                    self.name,
                    HEARTBEAT_TIMEOUT,
                )
                await self.mower.disconnect()
                self._disconnected.set()
                return self.mower.data
            try:
                await self.mower.refresh(STATS_COMMANDS)
            except BleakError as err:
                _LOGGER.debug("%s: stats refresh failed: %s", self.name, err)
        return self.mower.data

    # -- connection loop ----------------------------------------------------

    async def run(self) -> None:
        """Connect, stay connected, reconnect with backoff. Runs until unload."""
        attempt = 0
        while not self._stop.is_set():
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                _LOGGER.debug(
                    "%s: not seen by any Bluetooth adapter/proxy yet", self.name
                )
            else:
                self.mower.set_ble_device(ble_device)
                try:
                    await self.mower.connect()
                    attempt = 0
                    self._disconnected.clear()
                    await self.mower.refresh_all()
                    self.async_set_updated_data(self.mower.data)
                    self._update_device_registry()
                    await self._wait_disconnect_or_stop()
                    continue
                except (BleakError, asyncio.TimeoutError) as err:
                    _LOGGER.warning("%s: connection failed: %s", self.name, err)
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            attempt += 1
            try:
                await asyncio.wait_for(self._stop.wait(), delay)
            except asyncio.TimeoutError:
                pass

    @callback
    def _update_device_registry(self) -> None:
        """Entities register the device before the mower has answered; fill in what we learned."""
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, self.address)})
        data = self.mower.data
        if device and (data.firmware or data.serial):
            registry.async_update_device(
                device.id, sw_version=data.firmware, serial_number=data.serial
            )

    async def _wait_disconnect_or_stop(self) -> None:
        stop = asyncio.ensure_future(self._stop.wait())
        gone = asyncio.ensure_future(self._disconnected.wait())
        try:
            await asyncio.wait({stop, gone}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stop.cancel()
            gone.cancel()

    async def async_shutdown(self) -> None:
        """Called on unload and on HA stop; safe to run twice."""
        if self._stop.is_set():
            return
        self._stop.set()
        for unsub in self._unsub_listeners:
            unsub()
        await self.mower.disconnect()
        await super().async_shutdown()


async def async_setup_entry(hass: HomeAssistant, entry: CloudHawkConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS]
    mower = CloudHawkMower(address, name=entry.data.get(CONF_NAME, DEFAULT_NAME))
    coordinator = CloudHawkCoordinator(hass, entry, mower)
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)

    entry.async_create_background_task(
        hass, coordinator.run(), f"{DOMAIN}_{address}_connection"
    )

    @callback
    def _seen(
        _info: bluetooth.BluetoothServiceInfoBleak, _change: bluetooth.BluetoothChange
    ) -> None:
        # Advertisement seen: refresh the cached BLEDevice so the next connect uses the best path.
        if dev := bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        ):
            mower.set_ble_device(dev)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _seen,
            {"address": address, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CloudHawkConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: CloudHawkCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
