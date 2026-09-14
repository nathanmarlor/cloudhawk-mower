"""CloudHawk BLE protocol: framing, command table and payload parsers.

Pure functions only - no I/O - so this module is unit-testable without a mower.
Layouts were taken from the decompiled CloudHawk 2.1.3 app and verified against an
MB400 (firmware RM V6.01_2021(241121)B). See PROTOCOL.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum, IntEnum

HEAD = b"\x55\xaa"
BLE_PREFIX = 0x80

SERVICE_UUID = "0000ff12-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"


class Cmd(IntEnum):
    """Command / notification codes (the byte after the 0x80 prefix)."""

    # control
    START = 0x05
    START_ONCE = 0x7D
    STOP = 0x29
    CHARGE = 0x06
    SPIRAL_CUT = 0x79
    EDGE_CUT_ONCE = 0x7C
    RESET = 0x0F
    # info
    GET_FIRMWARE = 0x01
    GET_SERIAL = 0x02
    GET_BATTERY = 0x83
    GET_HEALTH = 0x18
    GET_FAULT_RECORDS = 0x15
    GET_CUTTING_RECORDS = 0x16
    GET_CHARGING_RECORDS = 0x17
    # settings
    GET_TRIMMING = 0x07
    SET_TRIMMING = 0x08
    GET_WIDTH = 0x09
    SET_WIDTH = 0x0A
    GET_SIGNAL = 0x0B
    SET_SIGNAL = 0x0C
    GET_MULTI_AREA = 0x0D
    SET_MULTI_AREA = 0x0E
    GET_CUT_DAYS = 0x11
    SET_CUT_DAYS = 0x12
    GET_DATE = 0x19
    SET_DATE = 0x1A
    GET_TIME = 0x1B
    SET_TIME = 0x1C
    GET_LANGUAGE = 0x1D
    SET_LANGUAGE = 0x1E
    GET_RAIN = 0x20
    SET_RAIN = 0x21
    GET_RAIN_DELAY = 0x32
    SET_RAIN_DELAY = 0x33
    GET_PIN = 0x03
    SET_PIN = 0x04
    GET_PUK = 0x31
    GET_ULTRASONIC = 0x54
    SET_ULTRASONIC = 0x55
    GET_ULTRASONIC_DISTANCE = 0x56
    SET_ULTRASONIC_DISTANCE = 0x57
    GET_SCHEDULE = 0x70
    SET_SCHEDULE = 0x71
    GET_MOWING_TIME = 0x7A
    SET_MOWING_TIME = 0x7B
    # notifications
    NOTIFY_STATE = 0x81
    NOTIFY_ERROR = 0x82
    NOTIFY_HEARTBEAT = 0x84
    NOTIFY_WORKING = 0x87
    NOTIFY_BLADE = 0x88
    NOTIFY_COVER = 0x8A


class MowerState(str, Enum):
    """High-level activity derived from the 0x81 state code."""

    UNKNOWN = "unknown"
    MOWING = "mowing"
    RETURNING = "returning"
    DOCKED = "docked"
    PAUSED = "paused"
    ERROR = "error"


# 0x81 state code -> (name, activity)
STATE_CODES: dict[int, tuple[str, MowerState]] = {
    0x00: ("running", MowerState.MOWING),
    0x01: ("returning_home", MowerState.RETURNING),
    0x02: ("outside_boundary", MowerState.ERROR),
    0x03: ("no_signal", MowerState.ERROR),
    0x04: ("lifted", MowerState.ERROR),
    0x05: ("tilted", MowerState.ERROR),
    0x06: ("stuck", MowerState.ERROR),
    0x07: ("low_battery", MowerState.RETURNING),
    0x08: ("waiting", MowerState.PAUSED),
    0x09: ("spare_time", MowerState.DOCKED),
    0x0A: ("close_cover", MowerState.PAUSED),
    0x0B: ("charging", MowerState.DOCKED),
    0x0C: ("cutting", MowerState.MOWING),
    0x0D: ("trapped", MowerState.ERROR),
    0x0E: ("standby", MowerState.PAUSED),
    0x0F: ("manual_operation", MowerState.ERROR),
    0x10: ("turned_over", MowerState.ERROR),
    0x11: ("m1_brake", MowerState.ERROR),
    0x12: ("m2_brake", MowerState.ERROR),
    0x37: ("high_temperature", MowerState.ERROR),
    0x38: ("instant_mowing", MowerState.MOWING),
    0x39: ("pause_mode", MowerState.PAUSED),
}

# 0x82 error code -> name
ERROR_CODES: dict[int, str] = {
    0x00: "none",
    0x01: "low_battery",
    0x02: "no_signal",
    0x03: "outside_boundary",
    0x04: "stuck",
    0x05: "tilted",
    0x06: "lifted",
    0x07: "m1_brake",
    0x08: "m2_brake",
    0x09: "turned_over",
    0x10: "error1",
    0x11: "error20l",
    0x12: "error21",
    0x13: "error22",
    0x14: "error23",
    0x15: "error24",
    0x16: "error3",
    0x17: "error4",
    0x18: "trapped",
    0x19: "error20m",
    0x20: "i2c_error",
    0x28: "error20r",
}

VOLTAGE_STATUS = {
    0: "normal",
    1: "low",
    2: "under_voltage",
    3: "full",
    4: "overcharged",
}

SPIRAL_RESULTS = {0x01: "started", 0x02: "pin_required", 0x03: "not_in_working_mode"}
EDGE_RESULTS = {
    0x02: "pin_required",
    0x03: "not_in_station",
    0x04: "high_temperature",
    0x05: "outside_working_time",
    0x06: "rain_sensor",
    0x07: "low_battery",
}


# --------------------------------------------------------------------------- framing


def build_frame(cmd: int, content: bytes = b"") -> bytes:
    """55 AA LL 80 CC content CS, CS = sum(all previous bytes) & 0xFF."""
    body = HEAD + bytes([2 + len(content), BLE_PREFIX, cmd]) + content
    return body + bytes([sum(body) & 0xFF])


@dataclass(frozen=True)
class Frame:
    cmd: int
    content: bytes


def parse_frames(data: bytes) -> list[Frame]:
    """Split a notification into frames, dropping anything with a bad checksum."""
    frames: list[Frame] = []
    i = 0
    while i + 4 <= len(data):
        if data[i : i + 2] != HEAD:
            i += 1
            continue
        length = data[i + 2]
        end = i + 3 + length + 1
        if end > len(data) or length < 2:
            break
        body = data[i:end]
        if sum(body[:-1]) & 0xFF != body[-1] or body[3] != BLE_PREFIX:
            i += 1
            continue
        frames.append(Frame(body[4], bytes(body[5:-1])))
        i = end
    return frames


# --------------------------------------------------------------------------- records


@dataclass(frozen=True)
class FaultRecord:
    timestamp: datetime
    code: int

    @property
    def name(self) -> str:
        return ERROR_CODES.get(self.code, f"unknown_{self.code:02x}")


@dataclass(frozen=True)
class ChargingRecord:
    timestamp: datetime
    value: int  # meaning unverified (observed 0x14)


@dataclass(frozen=True)
class TimePeriod:
    start: time
    end: time

    @property
    def enabled(self) -> bool:
        return self.start != self.end

    def to_bytes(self) -> bytes:
        return bytes(
            [self.start.hour, self.start.minute, self.end.hour, self.end.minute]
        )


DAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _ts(b: bytes) -> datetime | None:
    try:
        return datetime(int.from_bytes(b[0:2], "big"), b[2], b[3], b[4], b[5])
    except ValueError:
        return None


def parse_fault_records(c: bytes) -> list[FaultRecord]:
    out = []
    for i in range(0, len(c) - 6, 7):
        if ts := _ts(c[i : i + 6]):
            out.append(FaultRecord(ts, c[i + 6]))
    return out


def parse_cutting_records(c: bytes) -> list[datetime]:
    return [ts for i in range(0, len(c) - 5, 6) if (ts := _ts(c[i : i + 6]))]


def parse_charging_records(c: bytes) -> list[ChargingRecord]:
    out = []
    for i in range(0, len(c) - 6, 7):
        if ts := _ts(c[i : i + 6]):
            out.append(ChargingRecord(ts, c[i + 6]))
    return out


def parse_schedule(c: bytes) -> list[list[TimePeriod]]:
    """7 days x 2 periods x [startH startM endH endM]."""
    days: list[list[TimePeriod]] = []
    for d in range(0, min(len(c), 56), 8):
        periods = []
        for p in (0, 4):
            b = c[d + p : d + p + 4]
            try:
                periods.append(TimePeriod(time(b[0], b[1]), time(b[2], b[3])))
            except (ValueError, IndexError):
                periods.append(TimePeriod(time(0), time(0)))
        days.append(periods)
    return days


def encode_schedule(days: list[list[TimePeriod]]) -> bytes:
    return b"".join(p.to_bytes() for day in days for p in day)


def parse_cut_days(b: int) -> list[bool]:
    """Bit i (LSB first) = day i, Monday first."""
    return [bool(b >> i & 1) for i in range(7)]


def encode_cut_days(days: list[bool]) -> int:
    return sum(1 << i for i, on in enumerate(days) if on)


# --------------------------------------------------------------------------- state


@dataclass
class MowerData:
    """Everything we know about the mower. Updated in place as frames arrive."""

    firmware: str | None = None
    serial: str | None = None

    state_code: int | None = None
    error_code: int | None = None

    battery_level: int | None = None
    charging: bool | None = None
    voltage: float | None = None  # volts
    current: float | None = None  # amps
    voltage_status: int | None = None

    signal: int | None = None
    trimming: bool | None = None
    cut_width: int | None = None  # raw setting value (app shows value*10 cm)
    ultrasonic: bool | None = None
    ultrasonic_distance: int | None = None
    rain_sensor: bool | None = None
    rain_delay: int | None = None
    mowing_time_mode: bool | None = None
    language: int | None = None
    cut_days: list[bool] | None = None
    schedule: list[list[TimePeriod]] | None = None

    mower_date: date | None = None
    mower_time: time | None = None

    work_hours: int | None = None
    work_minutes: int | None = None
    charge_time: int | None = None

    blade_running: bool | None = None
    cover_open: bool | None = None
    working: bool | None = None
    last_heartbeat: datetime | None = None

    fault_records: list[FaultRecord] = field(default_factory=list)
    cutting_records: list[datetime] = field(default_factory=list)
    charging_records: list[ChargingRecord] = field(default_factory=list)

    last_spiral_result: str | None = None
    last_edge_result: str | None = None

    @property
    def state_name(self) -> str | None:
        if self.state_code is None:
            return None
        return STATE_CODES.get(
            self.state_code, (f"unknown_{self.state_code:02x}", None)
        )[0]

    @property
    def activity(self) -> MowerState:
        if self.state_code is None:
            return MowerState.UNKNOWN
        return STATE_CODES.get(self.state_code, ("", MowerState.UNKNOWN))[1]

    @property
    def error_name(self) -> str | None:
        if self.error_code is None:
            return None
        return ERROR_CODES.get(self.error_code, f"unknown_{self.error_code:02x}")


def apply_frame(data: MowerData, frame: Frame, now: datetime | None = None) -> bool:
    """Fold one frame into `data`. Returns True if it carried something we understand."""
    c = frame.content
    cmd = frame.cmd
    b0 = c[0] if c else None

    if cmd == Cmd.GET_FIRMWARE:
        data.firmware = c.decode("ascii", "ignore").strip("\x00 ")
    elif cmd == Cmd.GET_SERIAL:
        data.serial = c.decode("ascii", "ignore").strip("\x00 ")
    elif cmd == Cmd.NOTIFY_STATE and c:
        data.state_code = b0
    elif cmd == Cmd.NOTIFY_ERROR and c:
        data.error_code = b0
    elif cmd == Cmd.GET_BATTERY and len(c) >= 6:
        data.charging = c[0] == 1
        data.voltage = int.from_bytes(c[1:3], "big") / 10
        data.battery_level = c[3]
        data.current = c[4] / 10
        data.voltage_status = c[5]
    elif cmd == Cmd.NOTIFY_HEARTBEAT:
        data.last_heartbeat = now or datetime.now()
    elif cmd == Cmd.NOTIFY_WORKING and c:
        data.working = b0 == 1
    elif cmd == Cmd.NOTIFY_BLADE and c:
        data.blade_running = b0 == 1
    elif cmd == Cmd.NOTIFY_COVER and c:
        data.cover_open = b0 == 1
    elif cmd == Cmd.GET_SIGNAL and c:
        data.signal = b0
    elif cmd == Cmd.GET_TRIMMING and c:
        data.trimming = b0 == 1
    elif cmd == Cmd.GET_WIDTH and c:
        data.cut_width = b0
    elif cmd == Cmd.GET_ULTRASONIC and c:
        data.ultrasonic = b0 == 1
    elif cmd == Cmd.GET_ULTRASONIC_DISTANCE and c:
        data.ultrasonic_distance = b0
    elif cmd == Cmd.GET_RAIN and c:
        data.rain_sensor = b0 == 1
    elif cmd == Cmd.GET_RAIN_DELAY and len(c) >= 2:
        data.rain_delay = c[1]
    elif cmd == Cmd.GET_MOWING_TIME and c:
        data.mowing_time_mode = b0 == 1
    elif cmd == Cmd.GET_LANGUAGE and c:
        data.language = b0
    elif cmd == Cmd.GET_CUT_DAYS and c:
        data.cut_days = parse_cut_days(b0)
    elif cmd == Cmd.GET_SCHEDULE and len(c) >= 56:
        data.schedule = parse_schedule(c)
    elif cmd == Cmd.GET_DATE and len(c) >= 4:
        try:
            data.mower_date = date(int.from_bytes(c[0:2], "big"), c[2], c[3])
        except ValueError:
            return False
    elif cmd == Cmd.GET_TIME and len(c) >= 2:
        try:
            data.mower_time = time(c[0], c[1])
        except ValueError:
            return False
    elif cmd == Cmd.GET_HEALTH and len(c) >= 5:
        data.work_hours = int.from_bytes(c[0:2], "big")
        data.work_minutes = c[2]
        data.charge_time = int.from_bytes(c[3:5], "big")
    elif cmd == Cmd.GET_FAULT_RECORDS:
        data.fault_records = parse_fault_records(c)
    elif cmd == Cmd.GET_CUTTING_RECORDS:
        data.cutting_records = parse_cutting_records(c)
    elif cmd == Cmd.GET_CHARGING_RECORDS:
        data.charging_records = parse_charging_records(c)
    elif cmd == Cmd.SPIRAL_CUT and c:
        data.last_spiral_result = SPIRAL_RESULTS.get(b0, f"unknown_{b0:02x}")
    elif cmd == Cmd.EDGE_CUT_ONCE and c:
        data.last_edge_result = EDGE_RESULTS.get(b0, f"unknown_{b0:02x}")
    else:
        return False
    return True
