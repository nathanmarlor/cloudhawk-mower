"""CloudHawk lawn mower BLE client.

Holds a persistent GATT connection, folds every notification into a MowerData
snapshot and lets callers send commands. Transport is bleak; when a BLEDevice is
supplied (Home Assistant) connections go through bleak-retry-connector so they
work over ESPHome/Shelly Bluetooth proxies.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .protocol import (
    NOTIFY_UUID,
    WRITE_UUID,
    Cmd,
    MowerData,
    TimePeriod,
    apply_frame,
    build_frame,
    encode_cut_days,
    encode_schedule,
    parse_frames,
)

try:  # present inside Home Assistant, optional for standalone use
    from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
except ImportError:  # pragma: no cover
    establish_connection = None
    BleakClientWithServiceCache = BleakClient

_LOGGER = logging.getLogger(__name__)

# Commands whose replies populate MowerData; polled after connect and on demand.
INFO_COMMANDS: tuple[Cmd, ...] = (Cmd.GET_FIRMWARE, Cmd.GET_SERIAL)
SETTINGS_COMMANDS: tuple[Cmd, ...] = (
    Cmd.GET_SIGNAL,
    Cmd.GET_TRIMMING,
    Cmd.GET_WIDTH,
    Cmd.GET_ULTRASONIC,
    Cmd.GET_ULTRASONIC_DISTANCE,
    Cmd.GET_RAIN,
    Cmd.GET_RAIN_DELAY,
    Cmd.GET_MOWING_TIME,
    Cmd.GET_CUT_DAYS,
    Cmd.GET_SCHEDULE,
    Cmd.GET_DATE,
    Cmd.GET_TIME,
)
STATS_COMMANDS: tuple[Cmd, ...] = (
    Cmd.GET_BATTERY,
    Cmd.GET_HEALTH,
    Cmd.GET_FAULT_RECORDS,
    Cmd.GET_CUTTING_RECORDS,
    Cmd.GET_CHARGING_RECORDS,
)

COMMAND_SPACING = 0.4  # seconds between writes; the mower drops back-to-back frames
REPLY_TIMEOUT = 3.0


class CloudHawkMower:
    """One mower. Not thread-safe; use from a single event loop."""

    def __init__(
        self,
        address: str,
        ble_device: BLEDevice | None = None,
        name: str = "CloudHawk",
    ) -> None:
        self.address = address
        self.name = name
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self.data = MowerData()
        self._listeners: list[Callable[[MowerData], None]] = []
        self._disconnect_listeners: list[Callable[[], None]] = []
        self._write_lock = asyncio.Lock()
        self._waiters: dict[int, asyncio.Future] = {}
        self._expected_disconnect = False

    # ------------------------------------------------------------------ wiring

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device

    def add_listener(self, cb: Callable[[MowerData], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: cb in self._listeners and self._listeners.remove(cb)

    def add_disconnect_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._disconnect_listeners.append(cb)
        return lambda: (
            cb in self._disconnect_listeners and self._disconnect_listeners.remove(cb)
        )

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    # ------------------------------------------------------------------ connection

    async def connect(self) -> None:
        if self.is_connected:
            return
        self._expected_disconnect = False
        if self._ble_device is not None and establish_connection is not None:
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                disconnected_callback=self._on_disconnected,
                use_services_cache=True,
                ble_device_callback=lambda: self._ble_device,
            )
        else:
            client = BleakClient(
                self._ble_device or self.address,
                disconnected_callback=self._on_disconnected,
            )
            await client.connect()
        self._client = client
        await client.start_notify(NOTIFY_UUID, self._on_notify)
        _LOGGER.debug("%s: connected", self.name)

    async def disconnect(self) -> None:
        self._expected_disconnect = True
        client, self._client = self._client, None
        if client is None:
            return
        try:
            if client.is_connected:
                await client.stop_notify(NOTIFY_UUID)
                await client.disconnect()
        except Exception as err:  # noqa: BLE001 - never let teardown raise
            _LOGGER.debug("%s: error during disconnect: %s", self.name, err)

    def _on_disconnected(self, _client: BleakClient) -> None:
        if self._expected_disconnect:
            return
        _LOGGER.warning("%s: unexpected disconnect", self.name)
        self._client = None
        for fut in self._waiters.values():
            if not fut.done():
                fut.set_exception(BleakError("disconnected"))
        for cb in list(self._disconnect_listeners):
            cb()

    # ------------------------------------------------------------------ rx

    def _on_notify(self, _char, payload: bytearray) -> None:
        raw = bytes(payload)
        frames = parse_frames(raw)
        if not frames:
            _LOGGER.debug("%s: unparsable notification %s", self.name, raw.hex())
            return
        changed = False
        now = datetime.now()
        for frame in frames:
            _LOGGER.debug("%s: rx %02x %s", self.name, frame.cmd, frame.content.hex())
            if apply_frame(self.data, frame, now):
                changed = True
            if (fut := self._waiters.get(frame.cmd)) and not fut.done():
                fut.set_result(frame.content)
        if changed:
            for cb in list(self._listeners):
                cb(self.data)

    # ------------------------------------------------------------------ tx

    async def send(
        self, cmd: int, content: bytes = b"", wait_reply: bool = True
    ) -> bytes | None:
        """Write one frame; optionally wait for a frame with the same command byte."""
        if not self.is_connected:
            raise BleakError("not connected")
        async with self._write_lock:
            fut: asyncio.Future | None = None
            if wait_reply:
                fut = asyncio.get_running_loop().create_future()
                self._waiters[cmd] = fut
            try:
                frame = build_frame(cmd, content)
                _LOGGER.debug("%s: tx %s", self.name, frame.hex())
                await self._client.write_gatt_char(WRITE_UUID, frame, response=False)
                if fut is None:
                    await asyncio.sleep(COMMAND_SPACING)
                    return None
                try:
                    return await asyncio.wait_for(fut, REPLY_TIMEOUT)
                except asyncio.TimeoutError:
                    _LOGGER.debug("%s: no reply to %02x", self.name, cmd)
                    return None
            finally:
                if wait_reply:
                    self._waiters.pop(cmd, None)
                await asyncio.sleep(COMMAND_SPACING)

    async def refresh(self, commands: tuple[Cmd, ...]) -> None:
        for cmd in commands:
            await self.send(cmd)

    async def refresh_all(self) -> None:
        await self.refresh(INFO_COMMANDS + SETTINGS_COMMANDS + STATS_COMMANDS)

    # ------------------------------------------------------------------ control

    async def start_mowing(self) -> None:
        await self.send(Cmd.START)

    async def start_mowing_once(self) -> None:
        await self.send(Cmd.START_ONCE)

    async def stop(self) -> None:
        await self.send(Cmd.STOP)

    async def return_to_dock(self) -> None:
        await self.send(Cmd.CHARGE)

    async def spiral_cut(self) -> str | None:
        await self.send(Cmd.SPIRAL_CUT)
        return self.data.last_spiral_result

    async def edge_cut(self) -> str | None:
        await self.send(Cmd.EDGE_CUT_ONCE)
        return self.data.last_edge_result

    # ------------------------------------------------------------------ settings
    # Every setter writes, then re-reads so MowerData reflects what the mower accepted.

    async def _set_flag(self, set_cmd: Cmd, get_cmd: Cmd, on: bool) -> None:
        await self.send(set_cmd, bytes([1 if on else 0]))
        await self.send(get_cmd)

    async def set_trimming(self, on: bool) -> None:
        await self._set_flag(Cmd.SET_TRIMMING, Cmd.GET_TRIMMING, on)

    async def set_ultrasonic(self, on: bool) -> None:
        await self._set_flag(Cmd.SET_ULTRASONIC, Cmd.GET_ULTRASONIC, on)

    async def set_rain_sensor(self, on: bool) -> None:
        await self._set_flag(Cmd.SET_RAIN, Cmd.GET_RAIN, on)

    async def set_mowing_time_mode(self, on: bool) -> None:
        await self._set_flag(Cmd.SET_MOWING_TIME, Cmd.GET_MOWING_TIME, on)

    async def set_signal(self, signal: int) -> None:
        if signal not in (1, 2, 3):
            raise ValueError("signal must be 1, 2 or 3")
        await self.send(Cmd.SET_SIGNAL, bytes([signal]))
        await self.send(Cmd.GET_SIGNAL)

    async def set_ultrasonic_distance(self, value: int) -> None:
        await self.send(Cmd.SET_ULTRASONIC_DISTANCE, bytes([value & 0xFF]))
        await self.send(Cmd.GET_ULTRASONIC_DISTANCE)

    async def set_rain_delay(self, value: int) -> None:
        await self.send(Cmd.SET_RAIN_DELAY, bytes([0, value & 0xFF]))
        await self.send(Cmd.GET_RAIN_DELAY)

    async def set_cut_width(self, value: int) -> None:
        await self.send(Cmd.SET_WIDTH, bytes([value & 0xFF]))
        await self.send(Cmd.GET_WIDTH)

    async def set_cut_days(self, days: list[bool]) -> None:
        await self.send(Cmd.SET_CUT_DAYS, bytes([encode_cut_days(days)]))
        await self.send(Cmd.GET_CUT_DAYS)

    async def set_schedule(self, days: list[list[TimePeriod]]) -> None:
        if len(days) != 7 or any(len(d) != 2 for d in days):
            raise ValueError("schedule needs 7 days x 2 periods")
        await self.send(Cmd.SET_SCHEDULE, encode_schedule(days))
        await self.send(Cmd.GET_SCHEDULE)

    async def set_pin(self, pin: str) -> None:
        if len(pin) != 4 or not pin.isdigit():
            raise ValueError("PIN must be 4 digits")
        await self.send(Cmd.SET_PIN, bytes(int(ch) for ch in pin))

    async def sync_clock(self, now: datetime) -> None:
        await self.send(
            Cmd.SET_DATE, now.year.to_bytes(2, "big") + bytes([now.month, now.day])
        )
        await self.send(Cmd.SET_TIME, bytes([now.hour, now.minute]))
        await self.send(Cmd.GET_DATE)
        await self.send(Cmd.GET_TIME)

    @property
    def mower_datetime(self) -> datetime | None:
        d, t = self.data.mower_date, self.data.mower_time
        return datetime.combine(d, t) if d and t else None
