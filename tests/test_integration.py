"""Smoke test: set up the entry with a mocked BLE mower, check entities and a setter."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloudhawk.protocol import apply_frame, parse_frames

ADDR = "85:20:00:13:D8:E5"
FRAMES = [
    "55aa188001524d2056362e30315f3230323128323431313231294254",
    "55aa0c80023031393031303437323186",
    "55aa0380810b0e",
    "55aa0880830100ce64000441",
    "55aa03800b028f",
    "55aa038007018a",
    "55aa03805401d7",
    "55aa0380561ef6",
    "55aa03802001a3",
    "55aa0480320000b5",
    "55aa06801907ea090ea6",
    "55aa04801b091fc6",
    "55aa07801800a5130092e8",
    "55aa1e801507ea090c122b0307ea090c0f260307ea090c0e2f0307ea0810120406a1",
    "55aa0580840401000d",
]


@pytest.fixture
def mock_bt():
    with (
        patch(
            "custom_components.cloudhawk.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(address=ADDR),
        ),
        patch(
            "custom_components.cloudhawk.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        yield


async def test_setup_entities(hass: HomeAssistant, mock_bt):
    entry = MockConfigEntry(
        domain="cloudhawk",
        data={"address": ADDR, "name": "Mower"},
        unique_id=ADDR.lower(),
        title="Mower",
    )
    entry.add_to_hass(hass)

    async def fake_connect(self):
        self._client = MagicMock(is_connected=True)
        for h in FRAMES:
            for f in parse_frames(bytes.fromhex(h)):
                apply_frame(self.data, f, datetime.now())

    sent = []

    async def fake_send(self, cmd, content=b"", wait_reply=True):
        sent.append((int(cmd), content))
        if int(cmd) == 0x32:  # rain delay read-back echoes last write
            self.data.rain_delay = (
                sent[-2][1][1]
                if len(sent) > 1 and sent[-2][0] == 0x33
                else self.data.rain_delay
            )
        return b""

    with (
        patch(
            "custom_components.cloudhawk.cloudhawk_mower.CloudHawkMower.connect",
            fake_connect,
        ),
        patch(
            "custom_components.cloudhawk.cloudhawk_mower.CloudHawkMower.send", fake_send
        ),
        patch(
            "custom_components.cloudhawk.cloudhawk_mower.CloudHawkMower.disconnect",
            AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        for _ in range(5):
            await hass.async_block_till_done()

        states = {s.entity_id: s.state for s in hass.states.async_all()}
        assert states["lawn_mower.mower"] == "docked"
        assert states["sensor.mower_battery"] == "100"
        assert states["sensor.mower_state"] == "charging"
        assert states["sensor.mower_battery_voltage"] == "20.6"
        assert states["binary_sensor.mower_charging"] == "on"
        assert states["binary_sensor.mower_connected"] == "on"
        assert states["switch.mower_boundary_trimming"] == "on"
        assert states["select.mower_boundary_signal"] == "S2"
        assert states["number.mower_rain_delay"] == "0"
        assert states["sensor.mower_fault_count"] == "4"
        assert states["sensor.mower_serial_number"] == "0190104721"
        assert states["sensor.mower_total_work_time"].startswith(
            "165.3"
        )  # hours (165h19m)

        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.mower_rain_delay", "value": 5},
            blocking=True,
        )
        assert (0x33, bytes([0, 5])) in sent
        assert hass.states.get("number.mower_rain_delay").state == "5"

        await hass.services.async_call(
            "lawn_mower", "dock", {"entity_id": "lawn_mower.mower"}, blocking=True
        )
        assert (0x06, b"") in sent
        await hass.services.async_call(
            "cloudhawk",
            "set_cut_days",
            {"device_id": _device_id(hass, entry), "days": ["monday", "friday"]},
            blocking=True,
        )
        assert (0x12, bytes([0b10001])) in sent

        assert await hass.config_entries.async_unload(entry.entry_id)


def _device_id(hass, entry):
    from homeassistant.helpers import device_registry as dr

    dev = dr.async_get(hass).async_get_device(identifiers={("cloudhawk", ADDR)})
    return dev.id
