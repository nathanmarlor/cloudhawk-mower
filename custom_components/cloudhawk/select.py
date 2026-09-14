"""CloudHawk selects."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CloudHawkConfigEntry
from .entity import CloudHawkEntity

SIGNALS = ["S1", "S2", "S3"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CloudHawkSignalSelect(entry.runtime_data)])


class CloudHawkSignalSelect(CloudHawkEntity, SelectEntity):
    _attr_options = SIGNALS
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "boundary_signal"

    def __init__(self, coordinator) -> None:
        super().__init__(
            coordinator, SelectEntityDescription(key="boundary_signal_select")
        )

    @property
    def current_option(self) -> str | None:
        return f"S{self.data.signal}" if self.data.signal in (1, 2, 3) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.mower.set_signal(SIGNALS.index(option) + 1)
        self.async_write_ha_state()
