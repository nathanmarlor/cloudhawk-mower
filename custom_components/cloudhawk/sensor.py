"""CloudHawk sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CloudHawkConfigEntry
from .entity import CloudHawkEntity
from .protocol import ERROR_CODES, STATE_CODES, VOLTAGE_STATUS, MowerData


def _local(ts: datetime | None) -> datetime | None:
    """Mower timestamps are naive local time."""
    return (
        dt_util.as_utc(ts.replace(tzinfo=dt_util.get_default_time_zone()))
        if ts
        else None
    )


@dataclass(frozen=True, kw_only=True)
class CloudHawkSensorDescription(SensorEntityDescription):
    value_fn: Callable[[MowerData], Any]
    attrs_fn: Callable[[MowerData], dict[str, Any]] | None = None


SENSORS: tuple[CloudHawkSensorDescription, ...] = (
    CloudHawkSensorDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery_level,
    ),
    CloudHawkSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.voltage,
    ),
    CloudHawkSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.current,
    ),
    CloudHawkSensorDescription(
        key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(VOLTAGE_STATUS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            VOLTAGE_STATUS.get(d.voltage_status)
            if d.voltage_status is not None
            else None
        ),
    ),
    CloudHawkSensorDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[name for name, _ in STATE_CODES.values()],
        value_fn=lambda d: d.state_name if d.state_code in STATE_CODES else None,
        attrs_fn=lambda d: {"code": d.state_code},
    ),
    CloudHawkSensorDescription(
        key="error",
        device_class=SensorDeviceClass.ENUM,
        options=list(ERROR_CODES.values()),
        value_fn=lambda d: d.error_name if d.error_code in ERROR_CODES else None,
        attrs_fn=lambda d: {"code": d.error_code},
    ),
    CloudHawkSensorDescription(
        key="boundary_signal",
        device_class=SensorDeviceClass.ENUM,
        options=["S1", "S2", "S3"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: f"S{d.signal}" if d.signal in (1, 2, 3) else None,
    ),
    CloudHawkSensorDescription(
        key="total_work_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: (
            d.work_hours * 60 + d.work_minutes if d.work_hours is not None else None
        ),
    ),
    CloudHawkSensorDescription(
        key="charge_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.charge_time,
    ),
    CloudHawkSensorDescription(
        key="fault_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.fault_records),
        attrs_fn=lambda d: {
            "faults": [
                {"time": r.timestamp.isoformat(), "code": r.code, "name": r.name}
                for r in d.fault_records
            ]
        },
    ),
    CloudHawkSensorDescription(
        key="last_fault",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _local(
            max((r.timestamp for r in d.fault_records), default=None)
        ),
        attrs_fn=lambda d: (
            {"name": max(d.fault_records, key=lambda r: r.timestamp).name}
            if d.fault_records
            else {}
        ),
    ),
    CloudHawkSensorDescription(
        key="last_cut",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _local(max(d.cutting_records, default=None)),
        attrs_fn=lambda d: {"history": [t.isoformat() for t in d.cutting_records]},
    ),
    CloudHawkSensorDescription(
        key="last_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _local(
            max((r.timestamp for r in d.charging_records), default=None)
        ),
        attrs_fn=lambda d: {
            "history": [
                {"time": r.timestamp.isoformat(), "value": r.value}
                for r in d.charging_records
            ]
        },
    ),
    CloudHawkSensorDescription(
        key="mower_clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            _local(datetime.combine(d.mower_date, d.mower_time))
            if d.mower_date and d.mower_time
            else None
        ),
    ),
    CloudHawkSensorDescription(
        key="last_heartbeat",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            dt_util.as_utc(d.last_heartbeat.astimezone()) if d.last_heartbeat else None
        ),
    ),
    CloudHawkSensorDescription(
        key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.firmware,
    ),
    CloudHawkSensorDescription(
        key="serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.serial,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudHawkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(CloudHawkSensor(entry.runtime_data, desc) for desc in SENSORS)


class CloudHawkSensor(CloudHawkEntity, SensorEntity):
    entity_description: CloudHawkSensorDescription

    def __init__(self, coordinator, description: CloudHawkSensorDescription) -> None:
        super().__init__(coordinator, description)
        self._attr_translation_key = description.key

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if fn := self.entity_description.attrs_fn:
            return fn(self.data)
        return None
