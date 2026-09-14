# CloudHawk BLE Protocol Reference

Derived from decompiling CloudHawk Android app 2.1.3 (`com.cloudhawk.lawnmower_ble_wifi_manager.*`,
`ui/dashboard/device_name/CHDeviceInfoPresenter`) with jadx, then verified live against an MB400
(`SN0190104721`, firmware `RM V6.01_2021(241121)B`) on 2026-09-14, including a sweep of every opcode `00`–`EF`.
Items marked **(unverified)** were not exercised live.

## Transport

| | |
|---|---|
| Advertising | random static address (`85:20:…`), service UUID `ff12` in the advert, no name in the advert; GAP name (`2a00`) = `SN<serial>` |
| Service | `0000ff12-0000-1000-8000-00805f9b34fb` |
| Write characteristic | `0000ff01-…` — **write-without-response** only |
| Notify characteristic | `0000ff02-…` |
| MTU | app requests 500; module reports 241 |
| Auth | none. There is no BLE pairing or PIN handshake; `03`/`04` only read/write the keypad PIN. |
| Unsolicited | `81` state every 30 s, `83` battery every 30 s, `84` heartbeat every 60 s |

Full GATT table of the MB400:

| Service | Characteristics | Notes |
|---------|-----------------|-------|
| `1800` GAP | `2a00` name = `SN0190104721`, `2a01`, `2a04` | |
| `180a` Device Info | `2a25` serial = BLE MAC, `2a28` ×2 = `V127.0.12` (BLE module fw) / `WLT8266BMG` (module model), `2a27` = `V1.0.0`, `2a29` = `WLT` | the BLE module, not the mower |
| `ff12` | `ff01` write-no-rsp, `ff02` notify | **the mower protocol** |
| `ffe0` | `ffe2` write-no-rsp, `ffe1` notify | AT console of the BLE module (see below) |
| `00010203-0405-0607-0809-0a0b0c0d1912` | `…2b12` read/write | Telink OTA service — **do not touch** |

A second protocol (`0000abf0` / `abf1` / `abf2`, `util.ble.MowerCommand`) exists in the app for newer WiFi/RTK
"two-in-one" models with a different framing. Not relevant to the MB400.

## Framing

```
55 AA LL 80 CC [content …] CS
```

- `LL` = number of bytes from `80` through end of content (i.e. `2 + len(content)`).
- `80` = BLE command prefix (`BLE_C1`).
- `CC` = command byte.
- `CS` = sum of all preceding bytes (from `55`) mod 256.

Replies use the same framing; `CC` echoes the command, and unsolicited notifications use their own `CC`.
"Content" below always means the bytes between `CC` and `CS`.

## Control commands

| CC | Name | Content | Reply / notes |
|----|------|---------|---------------|
| `05` | START | — | Regular start (respects schedule). Ack is bare `80 05`. |
| `7D` | START_ONCE | — | "Instant mowing": mows until battery low, ignores schedule. State code becomes `38`. |
| `29` | STOP | — | Ack `80 29`. |
| `06` | CHARGE | — | Return to dock. Ack `80 06`. |
| `79` | SPIRAL_CUT | — | Reply content: `01` success, `02` need PIN, `03` not in working mode. |
| `7C` | EDGE_CUT_ONCE | — | Reply content: `02` need PIN, `03` not in station, `04` high temperature, `05` outside working time, `06` rain sensor, `07` low battery. |
| `0F` | RESET | — | Factory/system reset. **Do not send casually.** |
| `2A` | *undocumented* | — | Replies with a bare ack like the control commands above; state unchanged while docked. Meaning unknown. |
| `5A`, `66` | *undocumented* | — | Bare acks. Meaning unknown. |

## Settings (get / set pairs)

All "on/off" setters take a single byte `01` / `00`. All getters reply with content whose first byte is the value.

| Get | Set | Name | Value encoding |
|-----|-----|------|----------------|
| `07` | `08` | Boundary trimming (edge cut on start) | `01` = on |
| `54` | `55` | Ultrasonic obstacle sensor | `01` = on |
| `56` | `57` | Ultrasonic distance | 1 byte (units from the app slider, **unverified**) |
| `20` | `21` | Rain sensor | `01` = on |
| `32` | `33` | Rain delay | Set: 2 bytes `[00][delay]`. Get: 2 bytes, byte 1 is the delay (verified: set `00 01` → get `00 01`). |
| `0B` | `0C` | Boundary signal | 1 byte N → "S{N}" (S1/S2/S3) |
| `09` | `0A` | Cut width | 1 byte, value × 10 = cm |
| `11` | `12` | Cut days | 1 byte bitmask; bit *i* = day *i* (LSB first, 7 bits). Day order per app week list, **assumed Mon = bit 0**. |
| `70` | `71` | Cut time schedule | 7 × 8 bytes (verified 56-byte reply): per day, two periods of `[startH][startM][endH][endM]`. Set sends the full block. |
| `7A` | `7B` | Mowing-time ("pause mowing time mode") | `01` = enabled. When disabled the state code reads `39`. |
| `19` | `1A` | System date | Get: `[year u16][month][day]`. Set: same 4 bytes. |
| `1B` | `1C` | System time | `[hour][minute]` |
| `03` | `04` | Keypad PIN | 4 bytes, one decimal digit each (e.g. `01 02 03 04`). |
| `0D` | `0E` | Multi-area | Get: 12 bytes = 4 areas × `[len u16][percent]` (**unverified** field order; all zero on this unit). Set (per area): `[area 0–3][length u16][percent]`. |
| `13` | — | *undocumented* | 12 zero bytes, same shape as `0D`. |
| `2F` | — | *undocumented* | 8 bytes: `00 0a 0a 21 21 0c 05 e4` on this unit. Looks like a parameter block (two pairs of equal bytes, a u16 = 1508). |
| `59` | — | *undocumented* | 1 byte, `00`. |
| `1D` | `1E` | Language | 1 byte, mapping unknown |
| `4D`* | `41` | Push-report enable | Get reply byte 0 = `01` reporting. (*`4D` is also defined as SET_LOW_VOLTAGE; the app treats the reply as the report flag. `4C` GET_LOW_VOLTAGE is defined but never parsed.) |
| `31` | — | PUK | Reply not parsed by app |
| `1F` | — | SET_INSTALL | Unknown, never sent by the dashboard UI |

## Info commands

| CC | Name | Reply content |
|----|------|---------------|
| `01` | Firmware version | ASCII string |
| `02` | Serial number | ASCII string |
| `83` | Battery status (also pushed unsolicited) | `[charging 01/00][voltage u16][percent][current ÷10][voltage_status]` — voltage_status: `0` normal, `1` low, `2` under-voltage, `3` full, `4` overcharged |
| `18` | Health record | `[total_work_hours u16][total_work_minutes][charger_time u16]` — e.g. `00a5 13 0092` = 165 h 19 m, 146 |
| `15` | Fault records | n × 7 bytes `[year u16][month][day][hour][min][error code]` — codes as in the `82` table. Never used by the app but works. |
| `16` | Cutting records | n × 6 bytes `[year u16][month][day][hour][min]` |
| `17` | Charging records | n × 7 bytes `[year u16][month][day][hour][min][value]` — value was `0x14` in both entries; meaning **unverified** |
| `10` | "Review" | 17 bytes, app defines but never parses: `00×13 01 01 00 00` on this unit. Unknown. |
| `40` | BLE module version | ASCII `V127.0.12` (same as `2a28`) |
| `72` | BLE MAC | 6 bytes |
| `46` / `48` | Credential slots | 64 / 32 bytes, all `0xFF` (erased) — presumably WiFi SSID/password or server token storage for the WiFi models |
| `47` / `49` / `4E` | Flags | `01` / `01` / `03`. Unknown. |
| `2C` | RK info | ASCII `"sn,ver,camver"` (RTK models only; **no reply** on MB400) |
| `3B`, `4C`, `4D`, `81` | — | **No reply** on MB400 |
| `F0` `F1` `F3` `F4` | Firmware upgrade | Do not send. |

Every other opcode `00`–`EF` is silently ignored (swept 2026-09-14 with empty content).

## Notifications (unsolicited)

| CC | Name | Content |
|----|------|---------|
| `81` | Device display / state | 1 byte state code — see table below |
| `82` | Error code | 1 byte — see table below |
| `83` | Battery status | as above |
| `84` | Heartbeat | 3 bytes, `04 01 00` while docked and charging — plausibly `[voltage_status][charging][error]`, **unverified** |
| `87` | Work time | `01` working, `00` not working |
| `88` | Blade | `01` blade spinning, `00` stopped |
| `8A` | Front cover | `01` open, `00` closed |
| `85` | Lift | Defined, app ignores it (lift also appears as state `04`) |
| `86` | Signal status | Defined, app ignores it |

### State codes (`81`)

| Code | App text | Suggested HA activity |
|------|----------|-----------------------|
| `00` | Running (starting to mow) | mowing |
| `01` | Returning to charging station | returning |
| `02` | Out of boundary | error |
| `03` | No boundary signal | error |
| `04` | Lifted | error |
| `05` | Tilted / slope | error |
| `06` | Stuck (pit) | error |
| `07` | Low battery | returning / paused |
| `08` | Waiting | paused |
| `09` | Spare time (outside schedule, on dock) | docked |
| `0A` | Please close the lid | paused |
| `0B` | Charging | docked |
| `0C` | Cutting | mowing |
| `0D` | Trapped | error |
| `0E` | Standby / stopping | paused |
| `0F` | Please operate manually | error |
| `10` | Turned over | error |
| `11` | M1 brake | error |
| `12` | M2 brake | error |
| `37` | High temperature (edge cut refused) | error |
| `38` | Instant-mowing mode (from `7D`) | mowing |
| `39` | Pause-mowing-time mode active | paused |

### Error codes (`82`)

`00` none · `01` low battery · `02` no signal · `03` outside · `04` pit · `05` slope · `06` lift ·
`07` M1 brake · `08` M2 brake · `09` turned over · `10` ERROR1 · `11` ERROR20L · `12` ERROR21 · `13` ERROR22 ·
`14` ERROR23 · `15` ERROR24 · `16` ERROR3 · `17` ERROR4 · `18` trapped · `19` ERROR20M · `20` 12C ERROR ·
`28` ERROR20R

## The `ffe0` AT console (BLE module)

`ffe2` accepts `AT+<VERB>[=<arg>]\r\n`; `ffe1` answers `+OK[=value]\r\n`, `+ERR=Invalid Command` (unknown verb) or
`+ERR=Function Error` (bad argument). Verbs found: `AT+GETNAME` (`SN0190104721`), `AT+GETBAUD` (`9600`, the UART to
the mower MCU), `AT+GETPOWER` (`0`), `AT+GETMTU` (`241`), and the matching `SET` forms. The app's soft-AP WiFi
provisioning command `AT+SETWLAN=<ssid>,<pwd>` is **not** recognised by this module (`Invalid Command`), so the
MB400's BLE module has no WiFi despite the `8266` in its model name; WiFi models carry a separate module.

## What the app sends on connect

After service discovery and enabling notify on `ff02`, the dashboard sends (spaced ~1 s apart):
`11` cut days → `01` firmware → `83` battery → `7A` mowing-time, then on demand `70` schedule, `18` health,
`19` date, `1B` time. The settings screen additionally sends `03` PIN, `07`, `0D`, `0B`, `09`, `54`, `56`,
`20`, `32`, `4D`.

## Worked examples

```
55AA02 8083 04                → request battery
55AA08 8083 01 00CE 64 00 04 41 → charging=1, 20.6 V, 100 %, 0.0 A, status 4 (overcharged/full)
55AA03 8008 01 8B             → set trimming ON
55AA03 800C 02 90             → set boundary signal S2
55AA04 8033 00 05 BB          → rain delay 5
55AA06 8004 01 02 03 04 93    → set PIN 1234
```
