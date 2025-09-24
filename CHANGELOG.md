# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
