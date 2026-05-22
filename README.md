# CloudHawk Lawn Mower - Home Assistant Integration

A Home Assistant custom integration for CloudHawk lawn mowers using Bluetooth Low Energy (BLE) communication.

**⚠️ Testing Status**: This integration has been tested with the CloudHawk MB400 model. Compatibility with other CloudHawk models is not guaranteed.

## Features

### 📊 Sensors
- **Status** - Current mower operation status (IDLE, MOWING, RETURNING, CHARGING)
- **Battery Level** - Current battery percentage with charging status
- **Signal Type** -  Boundary signal selection (S1, S2, etc.)
- **Firmware Version** - Current mower firmware
- **Serial Number** - Device serial number
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

## Installation

### Method 1: Manual Installation

1. Copy the `custom_components/cloudhawk` folder to your Home Assistant `custom_components` directory:
   ```
   homeassistant/
   └── custom_components/
       └── cloudhawk/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           ├── sensor.py
           ├── button.py
           ├── switch.py
           ├── services.yaml
           └── cloudhawk_mower.py
   ```

2. Restart Home Assistant

3. Go to **Settings** → **Devices & Services** → **Add Integration**

4. Search for "CloudHawk" and select it

### Method 2: HACS (Future)

*This integration will be available through HACS in the future. For now, please use manual installation.*

## Configuration

### Automatic Discovery (Recommended)

If your CloudHawk mower is discoverable via Bluetooth, it should appear automatically:

1. Go to **Settings** → **Devices & Services**
2. Look for "CloudHawk Lawn Mower" in discovered devices
3. Click **Configure** and follow the setup wizard

### Manual Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "CloudHawk"
3. Enter the mower's Bluetooth MAC address
4. Enter a friendly name (optional)
5. Click **Submit**

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

Or use the included scanner:
```python
python3 bluetooth_scanner.py
```

## Usage

### Lovelace Dashboard Cards

#### Status Card
```yaml
type: entities
title: CloudHawk Mower
entities:
  - entity: sensor.cloudhawk_mower_battery_level
  - entity: sensor.cloudhawk_mower_signal_type
  - entity: switch.cloudhawk_mower_boundary_trimming
  - entity: sensor.cloudhawk_mower_working_hours
  - entity: sensor.cloudhawk_mower_fault_records
```

#### Control Card
```yaml
type: horizontal-stack
cards:
  - type: button
    tap_action:
      action: call-service
      service: button.press
      target:
        entity_id: button.cloudhawk_mower_start_mowing
    icon: mdi:play
    name: Mow Now
  - type: button
    tap_action:
      action: call-service
      service: button.press
      target:
        entity_id: button.cloudhawk_mower_stop_mowing
    icon: mdi:stop
    name: Stop
  - type: button
    tap_action:
      action: call-service
      service: button.press
      target:
        entity_id: button.cloudhawk_mower_return_to_dock
    icon: mdi:home
    name: Dock
```

### Automations

#### Start Mowing on Schedule
```yaml
automation:
  - alias: "Start Mowing Weekdays"
    trigger:
      platform: time
      at: "09:00:00"
    condition:
      condition: time
      weekday:
        - mon
        - tue
        - wed
        - thu
        - fri
    action:
      service: button.press
      target:
        entity_id: button.cloudhawk_mower_start_mowing
```

#### Stop on Low Battery
```yaml
automation:
  - alias: "Stop Mowing on Low Battery"
    trigger:
      platform: numeric_state
      entity_id: sensor.cloudhawk_mower_battery_level
      below: 20
    action:
      service: button.press
      target:
        entity_id: button.cloudhawk_mower_return_to_dock
```

#### Alert on Faults
```yaml
automation:
  - alias: "Mower Fault Alert"
    trigger:
      platform: state
      entity_id: sensor.cloudhawk_mower_fault_records
    condition:
      condition: template
      value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      service: notify.mobile_app_your_phone
      data:
        title: "Mower Fault"
        message: "CloudHawk mower has {{ trigger.to_state.state }} fault records"
```

## Services

The integration provides services that can be called from automations or scripts:

- `cloudhawk.start` - Start regular mowing
- `cloudhawk.start_once` - Start single mowing session  
- `cloudhawk.stop` - Stop mowing
- `cloudhawk.dock` - Return to dock

Example service call:
```yaml
service: cloudhawk.start_once
target:
  device_id: your_device_id
```

## Troubleshooting

### Connection Issues

1. **Mower not discovered**: Ensure Bluetooth is enabled
2. **Connection timeout**: Move Home Assistant closer to the mower
3. **Intermittent disconnections**: Check Bluetooth interference from other devices

### Debugging

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.cloudhawk: debug
```

### Common Issues

- **"Cannot connect"**: Mower may be off or out of range
- **Sensors showing "Unknown"**: Connection may be unstable, check distance
- **Commands not working**: Ensure mower is powered on and within range

## Technical Details

### Protocol
- Uses Bluetooth Low Energy (BLE)
- Custom protocol with `55AA` header
- Service UUID: `0000ff12-0000-1000-8000-00805f9b34fb`
- Write UUID: `0000ff01-0000-1000-8000-00805f9b34fb`
- Notify UUID: `0000ff02-0000-1000-8000-00805f9b34fb`

### Update Frequency
- Real-time data updates via BLE notifications (no polling)
- Commands trigger immediate data refresh
- Background connection maintenance

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration created through reverse engineering. Use at your own risk. The developers are not affiliated with CloudHawk.

## Support

- [Issues](https://github.com/your-username/cloudhawk-homeassistant/issues)
- [Discussions](https://github.com/your-username/cloudhawk-homeassistant/discussions)
- [Home Assistant Community](https://community.home-assistant.io/)
