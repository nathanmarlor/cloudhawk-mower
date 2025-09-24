# CloudHawk Home Assistant Integration - Installation Guide

## Quick Start

### Prerequisites
- Home Assistant 2023.8 or newer
- Bluetooth adapter on Home Assistant host
- CloudHawk lawn mower with Bluetooth connectivity

### 1. Installation

#### Option A: Copy Files Manually
1. Download/copy the `custom_components/cloudhawk` folder to your Home Assistant installation:
   ```
   /config/custom_components/cloudhawk/
   ```

#### Option B: Git Clone
```bash
cd /config/custom_components/
git clone https://github.com/your-username/cloudhawk-homeassistant.git cloudhawk
```

### 2. Restart Home Assistant
```bash
# Container/Docker
docker restart homeassistant

# Home Assistant OS
# Restart from UI: Settings → System → Restart
```

### 3. Find Your Mower's Address

#### Method 1: Bluetooth Scanner (Included)
```bash
# Copy the scanner to your Home Assistant host
python3 bluetooth_scanner.py
```

#### Method 2: Home Assistant Bluetooth Integration
1. Go to **Settings** → **Devices & Services**
2. Look for Bluetooth devices
3. Find device named like "SN0190104721"

#### Method 3: Command Line Tools

**Linux:**
```bash
bluetoothctl
scan on
# Look for CloudHawk device
```

**macOS:**
```bash
system_profiler SPBluetoothDataType | grep -A 5 "SN[0-9]"
```

### 4. Add Integration

#### Automatic Discovery (Recommended)
1. Go to **Settings** → **Devices & Services**
2. Look for "CloudHawk Lawn Mower" in discovered devices
3. Click **Configure**
4. Follow setup wizard

#### Manual Setup
1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "CloudHawk"
4. Enter mower's Bluetooth address (format: `XX:XX:XX:XX:XX:XX` or similar)
5. Enter friendly name (optional)
6. Click **Submit**

### 5. Verify Installation

After setup, you should see:

**Entities Created:**
- `sensor.cloudhawk_mower_battery_level`
- `sensor.cloudhawk_mower_signal_type`
- `sensor.cloudhawk_mower_firmware_version`
- `sensor.cloudhawk_mower_serial_number`
- `button.cloudhawk_mower_start_mowing`
- `button.cloudhawk_mower_stop_mowing`
- And more...

**Device Information:**
- Go to **Settings** → **Devices & Services** → **CloudHawk**
- Click on your mower device
- Verify sensors are showing data

## Troubleshooting

### "Integration not found"
- Ensure files are in `/config/custom_components/cloudhawk/`
- Restart Home Assistant
- Check logs for errors: **Settings** → **System** → **Logs**

### "Cannot connect to mower"
1. **Check mower power**: Ensure mower is on and not sleeping
2. **Check distance**: Move HA host closer to mower (< 10 meters)
3. **Check Bluetooth**: Verify HA host has working Bluetooth
   ```bash
   # Test Bluetooth availability
   hcitool dev
   ```
4. **Check interference**: Other Bluetooth devices may interfere
5. **Try pairing manually**: Some devices need manual pairing first

### Connection keeps dropping
1. **Signal strength**: Move HA host closer to typical mower location
2. **Power management**: Disable Bluetooth power saving
   ```bash
   # Linux: Disable USB auto-suspend
   echo -1 > /sys/module/usbcore/parameters/autosuspend
   ```
3. **Update interval**: Increase scan interval in integration options

### Wrong Bluetooth address format
Different systems show addresses differently:
- **Linux**: `XX:XX:XX:XX:XX:XX`
- **macOS**: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`
- **Windows**: `XX:XX:XX:XX:XX:XX`

Use the format shown by your system.

### Sensors showing "Unknown" or "Unavailable"
1. Check connection status in device info
2. Look at integration logs:
   ```yaml
   # Add to configuration.yaml
   logger:
     logs:
       custom_components.cloudhawk: debug
   ```
3. Restart integration: **Settings** → **Devices & Services** → **CloudHawk** → **⋮** → **Reload**

### Services not working
1. Verify entities exist and are available
2. Check service calls in **Developer Tools** → **Services**
3. Test with simple button press first
4. Check mower is in correct state (on, not charging, etc.)

## Advanced Configuration

### Custom Update Interval
```yaml
# configuration.yaml
cloudhawk:
  scan_interval: 30  # seconds (default: 60)
```

### Bluetooth Adapter Selection
If you have multiple Bluetooth adapters:
```yaml
# configuration.yaml
bluetooth:
  adapter: hci1  # Use specific adapter
```

### Debug Logging
```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.cloudhawk: debug
    bleak: debug  # For Bluetooth debugging
```

## Performance Tips

1. **Reduce update frequency** for battery savings
2. **Use automations** instead of frequent manual commands
3. **Group related entities** in dashboards
4. **Use templates** for derived sensors

## Integration with Other Systems

### Node-RED
Use Home Assistant nodes to call CloudHawk services:
```json
{
  "service": "button.press",
  "target": {
    "entity_id": "button.cloudhawk_mower_start_mowing"
  }
}
```

### ESPHome Bluetooth Proxy
For extended range, use ESP32 as Bluetooth proxy:
```yaml
# esphome config
esp32_ble_tracker:
  scan_parameters:
    interval: 1100ms
    window: 1100ms
    active: true

bluetooth_proxy:
  active: true
```

### MQTT Bridge
Publish mower state to MQTT:
```yaml
# automation
automation:
  - alias: "Publish Mower State"
    trigger:
      platform: state
      entity_id: sensor.cloudhawk_mower_battery_level
    action:
      service: mqtt.publish
      data:
        topic: "mower/battery"
        payload: "{{ states('sensor.cloudhawk_mower_battery_level') }}"
```

## Security Considerations

1. **Network isolation**: Consider separate VLAN for IoT devices
2. **Access control**: Limit who can control mower functions
3. **Monitoring**: Set up alerts for unexpected mower activity
4. **Updates**: Keep Home Assistant and integration updated

## Getting Help

1. **Check logs**: **Settings** → **System** → **Logs**
2. **Community forum**: [Home Assistant Community](https://community.home-assistant.io/)
3. **GitHub issues**: Report bugs and feature requests
4. **Discord**: Home Assistant Discord server

## Next Steps

After successful installation:
1. [Create dashboard cards](README.md#lovelace-dashboard-cards)
2. [Set up automations](README.md#automations)
3. [Configure notifications](README.md#automations)
4. Explore advanced features
