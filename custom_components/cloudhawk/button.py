"""CloudHawk buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CloudHawkConfigEntry, CloudHawkCoordinator
from .entity import CloudHawkEntity


@dataclass(frozen=True, kw_only=True)
class CloudHawkButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[CloudHawkCoordinator], Awaitable[None]]


BUTTONS: tuple[CloudHawkButtonDescription, ...] = (
    CloudHawkButtonDescription(key="start", press_fn=lambda c: c.mower.start_mowing()),
    CloudHawkButtonDescription(
        key="start_once", press_fn=lambda c: c.mower.start_mowing_once()
    ),
    CloudHawkButtonDescription(
        key="spiral_cut", press_fn=lambda c: c.mower.spiral_cut()
    ),
    CloudHawkButtonDescription(key="edge_cut", press_fn=lambda c: c.mower.edge_cut()),
    CloudHawkButtonDescription(key="stop", press_fn=lambda c: c.mower.stop()),
    CloudHawkButtonDescription(key="dock", press_fn=lambda c: c.mower.return_to_dock()),
    CloudHawkButtonDescription(
        key="sync_clock",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.mower.sync_clock(dt_util.now().replace(tzinfo=None)),
    ),
    CloudHawkButtonDescription(
        key="refresh",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda c: c.mower.refresh_all(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(CloudHawkButton(entry.runtime_data, d) for d in BUTTONS)


class CloudHawkButton(CloudHawkEntity, ButtonEntity):
    entity_description: CloudHawkButtonDescription

    def __init__(self, coordinator, description: CloudHawkButtonDescription) -> None:
        super().__init__(coordinator, description)
        self._attr_translation_key = description.key

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
