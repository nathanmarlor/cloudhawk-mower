# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-09-14

Rewrite of the protocol layer and Home Assistant plumbing after decompiling the CloudHawk app and verifying every
command against a live MB400. **Entity IDs change**: unique IDs are now based on the mower's MAC instead of its
name, so old entities will show as unavailable and should be deleted.

### Fixed
- State decoding: the `0x81` notification is a 22-value state code (charging, cutting, returning home, lifted,
  outside boundary, trapped, …) — previously only 4 values were known and regular mowing showed as `error`.
- Charging flag read from the wrong byte of the battery frame; voltage, current and battery status now decoded.
- Reconnect loop leaked a maintenance task per reconnect and fell back to scanning for a hard-coded device name.
- Bluetooth now goes through Home Assistant's stack (`bleak-retry-connector`), so ESPHome/Shelly proxies work.
- Notifications are checksum-validated and multi-frame safe; commands wait for their reply.
- Setup no longer spawns an untracked task; unload disconnects cleanly.
- Switches actually switch.

### Added
- Lawn mower entity with proper activity mapping (mowing / returning / docked / paused / error).
- Error code sensor, blade / cover / problem / connected binary sensors, voltage & current sensors.
- Total work time, charge time, fault log, last cut and last charge from the mower's own records.
- Switches: boundary trimming, ultrasonic sensor, rain sensor, mowing-time mode. Select: boundary signal.
  Numbers: ultrasonic distance, rain delay, cut width. Buttons: mow once, sync clock, refresh.
- Services `set_schedule`, `set_cut_days`, `set_pin`.
- Heartbeat-based availability and automatic reconnect.
- `PROTOCOL.md` — the full reverse-engineered protocol including undocumented opcodes and the BLE module's AT console.
- Unit and integration tests.

### Removed
- Fictional fault-record parser, unused services, `EXTENDED_PROTOCOL_DISCOVERY.md`.

## [1.0.0] - 2025-01-21

### Added
- Initial release of CloudHawk Lawn Mower integration
- Bluetooth Low Energy (BLE) connectivity
- 8 sensor entities for monitoring mower status
- 4 button entities for mower control commands
- 2 switch entities for feature status display
- Automatic Bluetooth discovery and manual configuration
- Config flow for easy setup
- HACS compatibility
- Complete documentation and examples

### Features
- **Sensors:**
  - Battery level with charging status
  - GPS signal type (S1, S2, etc.)
  - Firmware version and serial number
  - Current date and time
  - Working hours counter
  - Rain delay setting
  - Fault records with recent details
  
- **Controls:**
  - Start regular mowing
  - Start single mowing session
  - Stop mowing immediately
  - Return to charging dock
  
- **Status:**
  - Boundary trimming enabled/disabled
  - Ultrasonic sensor enabled/disabled

### Technical
- Reverse-engineered CloudHawk Bluetooth protocol
- Robust connection management with auto-reconnect
- 60-second update interval with command-triggered refresh
- Proper Home Assistant device integration
- Error handling and logging
