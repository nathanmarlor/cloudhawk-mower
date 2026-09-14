# CloudHawk Lawn Mower — Home Assistant integration

Local Bluetooth LE control and monitoring for CloudHawk robotic lawn mowers. No cloud, no app account.

Tested on a **CloudHawk MB400** (firmware `RM V6.01_2021`). Any CloudHawk / rebadged model that advertises the
`ff12` BLE service and speaks the `55AA` protocol should work; see [PROTOCOL.md](PROTOCOL.md) for the full
reverse-engineered command set.

## What you get

**Lawn mower entity** — `lawn_mower.<name>` with start / pause (stop) / dock and the HA activity states
mowing, returning, docked, paused, error. Cut days and the weekly schedule are exposed as attributes.

**Sensors**

| Entity | Notes |
|--------|-------|
| Battery, battery voltage, battery current, battery status | pushed by the mower every 30 s |
| State | the mower's own 22-value state code (charging, cutting, returning home, lifted, outside boundary, trapped, …) |
| Error | last error code (low battery, no signal, M1/M2 brake, ERROR20L, …) |
| Total work time, charge time | lifetime counters |
| Fault count / last fault | full fault log with timestamps as attributes |
| Last cut, last charge | from the mower's own records |
| Boundary signal, firmware, serial, mower clock, last heartbeat | diagnostics |

**Binary sensors** — charging, blade running, cover open, problem, connected.

**Controls** — switches for boundary trimming, ultrasonic sensor, rain sensor, mowing-time mode; select for
boundary signal (S1/S2/S3); numbers for ultrasonic distance, rain delay, cut width; buttons for start, mow once,
spiral cut, edge cut, stop, return to dock, sync clock, refresh.

**Services** — `cloudhawk.set_schedule`, `cloudhawk.set_cut_days`, `cloudhawk.set_pin`.

## Requirements

- Home Assistant 2024.8 or newer with the **Bluetooth** integration.
- A path to the mower: a local Bluetooth adapter, or — usually better, since mowers live outside — an
  **ESPHome Bluetooth proxy** (`bluetooth_proxy: active: true`) or Shelly near the dock. The integration uses HA's
  Bluetooth stack, so proxies work out of the box. Note that an ESPHome proxy only serves one client at a time; HA
  must be the only thing talking to it.

## Installation

**HACS**: add this repository as a custom repository (category *Integration*), install, restart HA.

**Manual**: copy `custom_components/cloudhawk` into your `config/custom_components/` directory and restart.

## Setup

The mower is discovered automatically as soon as any adapter or proxy sees it — accept the discovery under
**Settings → Devices & services**. Otherwise **Add integration → CloudHawk** lists the mowers currently in range.
The mower must be powered on; it advertises as `SN<serial>` with no name in the advertisement, so it shows up by
address.

## Behaviour

The integration keeps one BLE connection open. The mower pushes state and battery every 30 s and a heartbeat
every 60 s; settings and counters are read on connect, every 10 minutes, and after every change you make. If the
heartbeat stops the connection is dropped and re-established. Entities become unavailable while disconnected;
`binary_sensor.<name>_connected` always reports the link state.

## Example automations

```yaml
# Mow on weekday mornings
- alias: Mow weekdays
  trigger: {platform: time, at: "09:00:00"}
  condition: {condition: time, weekday: [mon, tue, wed, thu, fri]}
  action: {action: lawn_mower.start_mowing, target: {entity_id: lawn_mower.mower}}

# Tell me when it gets stuck
- alias: Mower needs help
  trigger: {platform: state, entity_id: binary_sensor.mower_problem, to: "on"}
  action:
    action: notify.mobile_app_phone
    data: {message: "Mower: {{ states('sensor.mower_state') }}"}

# Program the schedule
- action: cloudhawk.set_schedule
  data:
    device_id: !input mower
    monday: [{start: "09:00", end: "12:00"}, {start: "15:00", end: "18:00"}]
    saturday: [{start: "10:00", end: "12:00"}]
```

More in [example_automations.yaml](example_automations.yaml) and [example_dashboard.yaml](example_dashboard.yaml).

## Debugging

```yaml
logger:
  logs:
    custom_components.cloudhawk: debug
```

Debug level logs every frame sent and received (`tx 55aa…` / `rx 83 …`).

## Development

```
pip install -r requirements_test.txt
pytest
```

`tests/test_protocol.py` checks the parser against frames captured from a real MB400.
`custom_components/cloudhawk/protocol.py` is pure Python with no HA dependency and can be reused standalone.

## Disclaimer

Unofficial, reverse-engineered from the CloudHawk Android app and a live mower. Not affiliated with CloudHawk.
MIT licence.
