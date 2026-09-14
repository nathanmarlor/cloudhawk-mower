"""CloudHawk lawn mower entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CloudHawkConfigEntry
from .entity import CloudHawkEntity
from .protocol import DAY_NAMES, MowerState

ACTIVITY = {
    MowerState.MOWING: LawnMowerActivity.MOWING,
    MowerState.RETURNING: LawnMowerActivity.RETURNING,
    MowerState.DOCKED: LawnMowerActivity.DOCKED,
    MowerState.PAUSED: LawnMowerActivity.PAUSED,
    MowerState.ERROR: LawnMowerActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CloudHawkLawnMower(entry.runtime_data)])


class CloudHawkLawnMower(CloudHawkEntity, LawnMowerEntity):
    _attr_name = None  # takes the device name
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    @property
    def activity(self) -> LawnMowerActivity | None:
        return ACTIVITY.get(self.data.activity)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.data
        attrs: dict[str, Any] = {
            "state_code": d.state_code,
            "state_name": d.state_name,
            "error": d.error_name,
        }
        if d.cut_days is not None:
            attrs["cut_days"] = [
                name for name, on in zip(DAY_NAMES, d.cut_days, strict=False) if on
            ]
        if d.schedule is not None:
            attrs["schedule"] = {
                name: [f"{p.start:%H:%M}-{p.end:%H:%M}" for p in periods if p.enabled]
                for name, periods in zip(DAY_NAMES, d.schedule, strict=False)
            }
        return attrs

    async def async_start_mowing(self) -> None:
        await self.coordinator.mower.start_mowing()

    async def async_pause(self) -> None:
        await self.coordinator.mower.stop()

    async def async_dock(self) -> None:
        await self.coordinator.mower.return_to_dock()
