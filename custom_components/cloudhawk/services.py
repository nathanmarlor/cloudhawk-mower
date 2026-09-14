"""Services: schedule and cut-day programming, PIN change."""

from __future__ import annotations

from datetime import time

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SERVICE_SET_CUT_DAYS, SERVICE_SET_PIN, SERVICE_SET_SCHEDULE
from .protocol import DAY_NAMES, TimePeriod

PERIOD_SCHEMA = vol.Schema(
    {vol.Required("start"): cv.time, vol.Required("end"): cv.time}
)
DAY_SCHEMA = vol.All(cv.ensure_list, [PERIOD_SCHEMA], vol.Length(max=2))

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        **{vol.Optional(day): DAY_SCHEMA for day in DAY_NAMES},
    }
)
SET_CUT_DAYS_SCHEMA = vol.Schema(
    {vol.Required("device_id"): cv.string, vol.Required("days"): [vol.In(DAY_NAMES)]}
)
SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("pin"): cv.matches_regex(r"^\d{4}$"),
    }
)


def _coordinator_for(hass: HomeAssistant, device_id: str):
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Unknown device {device_id}")
    for entry_id in device.config_entries:
        if coordinator := hass.data.get(DOMAIN, {}).get(entry_id):
            return coordinator
    raise HomeAssistantError("Device is not a CloudHawk mower")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        return

    async def set_schedule(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data["device_id"])
        current = coordinator.mower.data.schedule or [
            [TimePeriod(time(0), time(0))] * 2 for _ in range(7)
        ]
        days = []
        for i, name in enumerate(DAY_NAMES):
            if name not in call.data:
                days.append(list(current[i]))
                continue
            periods = [TimePeriod(p["start"], p["end"]) for p in call.data[name]]
            while len(periods) < 2:
                periods.append(TimePeriod(time(0), time(0)))
            days.append(periods)
        await coordinator.mower.set_schedule(days)

    async def set_cut_days(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data["device_id"])
        await coordinator.mower.set_cut_days(
            [d in call.data["days"] for d in DAY_NAMES]
        )

    async def set_pin(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data["device_id"])
        await coordinator.mower.set_pin(call.data["pin"])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULE, set_schedule, SET_SCHEDULE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CUT_DAYS, set_cut_days, SET_CUT_DAYS_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_SET_PIN, set_pin, SET_PIN_SCHEMA)
