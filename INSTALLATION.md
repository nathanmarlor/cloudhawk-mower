# Installation

## HACS

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/nathanmarlor/cloudhawk-mower`, category **Integration**.
3. Install **CloudHawk Lawn Mower** and restart Home Assistant.

## Manual

1. Copy `custom_components/cloudhawk` into `<config>/custom_components/`.
2. Restart Home Assistant.

## Reaching the mower

The integration uses Home Assistant's Bluetooth stack, so any of these work:

- A USB Bluetooth adapter on the HA host (only if the dock is close to it).
- An **ESPHome Bluetooth proxy** near the dock:

  ```yaml
  esp32_ble_tracker:
  bluetooth_proxy:
    active: true
  ```

- A Shelly Plus/Pro device with its Bluetooth gateway enabled.

The mower advertises only while it is not connected to something else, and only accepts one connection. Close the
CloudHawk phone app before setting up.

## Adding the mower

Power the mower on. Within a minute HA shows a **CloudHawk Lawn Mower** discovery under
Settings → Devices & services; click **Configure**, optionally give it a name, and submit. HA connects once to read
the serial number, then the entry keeps a persistent connection.

If nothing is discovered, **Add integration → CloudHawk** lists mowers currently in range of any adapter or proxy.

## Upgrading from 1.x

Entity unique IDs changed from name-based to MAC-based. After upgrading, delete the old unavailable entities from
the device page; the config entry itself does not need to be re-created.
