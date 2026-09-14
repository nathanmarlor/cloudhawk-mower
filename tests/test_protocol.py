"""Protocol parser tests against frames captured from a real MB400."""

from datetime import date, datetime, time

from custom_components.cloudhawk.protocol import (
    Cmd,
    MowerData,
    MowerState,
    TimePeriod,
    apply_frame,
    build_frame,
    encode_cut_days,
    encode_schedule,
    parse_cut_days,
    parse_frames,
    parse_schedule,
)


def feed(*hexes: str) -> MowerData:
    d = MowerData()
    for h in hexes:
        for f in parse_frames(bytes.fromhex(h)):
            apply_frame(d, f, datetime(2026, 9, 14, 9, 0))
    return d


def test_build_frame():
    assert build_frame(Cmd.GET_BATTERY).hex() == "55aa02808304"
    assert build_frame(Cmd.SET_PIN, bytes([1, 2, 3, 4])).hex() == "55aa0680040102030493"
    assert build_frame(Cmd.SET_TRIMMING, b"\x01").hex() == "55aa038008018b"


def test_parse_rejects_bad_checksum_and_splits_concatenated():
    assert parse_frames(bytes.fromhex("55aa0380810b0f")) == []
    frames = parse_frames(bytes.fromhex("55aa0380810b0e55aa0880830100ce64000441"))
    assert [f.cmd for f in frames] == [0x81, 0x83]


def test_identity_and_battery():
    d = feed(
        "55aa188001524d2056362e30315f3230323128323431313231294254",
        "55aa0c80023031393031303437323186",
        "55aa0880830100ce64000441",
        "55aa0380810b0e",
    )
    assert d.firmware == "RM V6.01_2021(241121)B"
    assert d.serial == "0190104721"
    assert (d.charging, d.voltage, d.battery_level, d.current, d.voltage_status) == (
        True,
        20.6,
        100,
        0.0,
        4,
    )
    assert d.state_name == "charging" and d.activity is MowerState.DOCKED


def test_settings_and_clock():
    d = feed(
        "55aa03800b028f",
        "55aa038007018a",
        "55aa0380561ef6",
        "55aa0480320001b6",
        "55aa06801907ea090ea6",
        "55aa04801b091fc6",
        "55aa0380110093",
        "55aa03807a00fc",
    )
    assert (
        d.signal == 2
        and d.trimming is True
        and d.ultrasonic_distance == 30
        and d.rain_delay == 1
    )
    assert d.mower_date == date(2026, 9, 14) and d.mower_time == time(9, 31)
    assert d.cut_days == [False] * 7 and d.mowing_time_mode is False


def test_records():
    d = feed(
        "55aa07801800a5130092e8",
        "55aa1e801507ea090c122b0307ea090c0f260307ea090c0e2f0307ea0810120406a1",
        "55aa1a801607ea090d100207ea090d110d07ea090c122207ea090c132969",
        "55aa10801707ea090d10021407ea090c12211420",
    )
    assert (d.work_hours, d.work_minutes, d.charge_time) == (165, 19, 146)
    assert len(d.fault_records) == 4
    assert (
        d.fault_records[0].timestamp == datetime(2026, 9, 12, 18, 43)
        and d.fault_records[0].name == "outside_boundary"
    )
    assert d.fault_records[3].name == "lifted"
    assert d.cutting_records[0] == datetime(2026, 9, 13, 16, 2)
    assert d.charging_records[1].value == 20


def test_notifications():
    d = feed("55aa0580840401000d", "55aa038088010b", "55aa03808a000c", "55aa0380820307")
    assert d.last_heartbeat is not None
    assert (
        d.blade_running is True
        and d.cover_open is False
        and d.error_name == "outside_boundary"
    )


def test_schedule_roundtrip():
    days = [
        [TimePeriod(time(9, 0), time(12, 0)), TimePeriod(time(0), time(0))]
        for _ in range(7)
    ]
    raw = encode_schedule(days)
    assert len(raw) == 56 and parse_schedule(raw) == days
    assert encode_cut_days([True, False, False, False, True, False, False]) == 0b10001
    assert parse_cut_days(0b10001) == [True, False, False, False, True, False, False]
