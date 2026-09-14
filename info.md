# CloudHawk Lawn Mower

Local Bluetooth LE control and monitoring for CloudHawk robotic mowers (tested on the MB400). Works through
Home Assistant's Bluetooth stack, including ESPHome Bluetooth proxies.

- Lawn mower entity (start / pause / dock) with real activity states
- Battery, voltage, current, state, error, work time, fault log, last cut/charge
- Blade, cover, charging, problem and connectivity binary sensors
- Switches for trimming, ultrasonic, rain sensor, mowing-time mode; boundary signal select; numeric settings
- Services to program the weekly schedule, cut days and PIN

See the README for setup and PROTOCOL.md for the reverse-engineered protocol.
