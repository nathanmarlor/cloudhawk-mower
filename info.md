# CloudHawk Lawn Mower Integration

A Home Assistant custom integration for CloudHawk lawn mowers using Bluetooth Low Energy (BLE) communication.

**⚠️ Testing Status**: This integration has been tested with the CloudHawk MB400 model. Compatibility with other CloudHawk models is not guaranteed.

## Features

### 📊 Sensors
- **Status** - Current mower operation status (IDLE, MOWING, RETURNING, DOCKED, STOPPED, ERROR)
- **Battery Level** - Current battery percentage with charging status
- **Signal Type** - GPS signal strength (S1, S2, etc.)
- **Firmware Version** - Current mower firmware
- **Serial Number** - Device serial number
- **Working Hours** - Total operating time
- **Fault Records** - Number of fault records with recent details

### 🎛️ Controls
- **Mow Now** - Begin regular mowing cycle
- **Spiral Cut** - Start spiral cutting pattern
- **Edge Cut** - Start edge cutting along boundaries
- **Stop Mowing** - Immediately stop the mower
- **Return to Dock** - Send mower back to charging station

### ⚙️ Status Switches (Read-only)
- **Boundary Trimming** - Shows if edge trimming is enabled
- **Ultrasonic Sensor** - Shows if ultrasonic obstacle detection is enabled

## Requirements

- Home Assistant 2023.8 or newer
- Bluetooth adapter on Home Assistant host
- CloudHawk lawn mower with Bluetooth connectivity

## Installation

1. **Find your mower's Bluetooth address** using the included scanner or Home Assistant's Bluetooth integration
2. **Add the integration** through Settings → Devices & Services → Add Integration
3. **Enter the mower's address** and follow the setup wizard
4. **Configure dashboard cards** and automations as needed

## Installation

### Manual Installation

1. Copy the `custom_components/cloudhawk` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "CloudHawk" and select it

### Configuration

#### Finding Your Mower's Bluetooth Address

You can find your mower's address using:

```bash
# On Linux/macOS with bluetoothctl
bluetoothctl
scan on
# Look for device named like "SN0190104721"

# On macOS with system_profiler
system_profiler SPBluetoothDataType
```

## Supported Models

This integration has been tested with CloudHawk MB400 mowers. Your mower should have:

- Bluetooth Low Energy (BLE) connectivity
- Service UUID: `0000ff12-0000-1000-8000-00805f9b34fb`
- A device name starting with "SN" followed by numbers

## Quick Start

After installation, you'll have these entities:

**Sensors:**
- `sensor.cloudhawk_mower_status`
- `sensor.cloudhawk_mower_battery_level`
- `sensor.cloudhawk_mower_signal_type`
- `sensor.cloudhawk_mower_firmware_version`
- And more...

**Controls:**
- `button.cloudhawk_mower_start_mowing` (Mow Now)
- `button.cloudhawk_mower_spiral_cut` (Spiral Cut)
- `button.cloudhawk_mower_edge_cut` (Edge Cut)
- `button.cloudhawk_mower_stop_mowing`
- `button.cloudhawk_mower_return_to_dock`

## Automation Examples

**Start mowing on schedule:**
```yaml
automation:
  - alias: "Start Mowing Weekdays"
    trigger:
      platform: time
      at: "09:00:00"
    condition:
      condition: time
      weekday: [mon, tue, wed, thu, fri]
    action:
      service: button.press
      target:
        entity_id: button.cloudhawk_mower_start_mowing
```

**Alert on low battery:**
```yaml
automation:
  - alias: "Mower Low Battery"
    trigger:
      platform: numeric_state
      entity_id: sensor.cloudhawk_mower_battery_level
      below: 20
    action:
      service: notify.mobile_app_your_phone
      data:
        message: "Mower battery low: {{ trigger.to_state.state }}%"
```

## Support

- [Documentation](https://github.com/your-username/cloudhawk-homeassistant)
- [Issues](https://github.com/your-username/cloudhawk-homeassistant/issues)
- [Home Assistant Community](https://community.home-assistant.io/)

---

**Note:** This is an unofficial integration created through reverse engineering. The developers are not affiliated with CloudHawk.
