## State Summary

Project goal:
- Build a web control and monitoring system for STM32-based devices communicating through a cellular modem path.

Current architecture:
- Backend: FastAPI
- Frontend: static single-page app served by FastAPI
- Realtime: WebSocket
- MQTT: `paho-mqtt`
- Local modem/debug tools: Python + `pyserial`

Frontend status:
- UI is fully translated to Hebrew.
- App title is `משדר זרנוק`.
- There is a login page at `/login`.
- Credentials are currently:
  - username: `Admin`
  - password: `Admin123`
- Frontend includes:
  - overview screen
  - per-device dashboard
  - `online/offline` indication
  - add device flow
  - delete device flow from dashboard and overview cards
  - per-device MQTT topic inputs on creation
  - monitoring gauges for `Ir`, `V1`, frequency, resistance, power, and battery voltage
  - battery voltage now appears only in the gauge area; the old bottom `VIN`/battery summary row was removed
  - frontend now has API fallback fetches and device-state merging to reduce empty-topic/stale-state issues
- Default seeded device list now includes only:
  - `6673842E`
- Recent UI fixes:
  - search no longer resets during live updates
  - repeated watch subscriptions were fixed
  - inline command feedback was added
  - dashboard now updates live values in place instead of full-screen rerender on each poll
  - background `G` polling is now silent in the UI unless online/offline state changes

Authentication status:
- Cookie-based session auth is implemented.
- Frontend, API, and WebSocket are protected.
- Login is handled by `/api/auth/login`.

Protocol status:
- Outgoing command frames now include the serial number again.
- Device routing is topic-based.
- Current command frame format is:
  - `0x01 + SN + ',' + command + 0x00`
- Verified live command outputs on `COM3`:
  - `ON` -> `01 53 2C 53 2C 31 2C 31 00`
  - `OFF` -> `01 53 2C 53 2C 31 2C 30 00`
  - automatic `G` poll -> `01 47 00`

Controller compatibility status:
- Backend control commands were aligned to the legacy RS485 reference format:
  - output enable: `S,S,2,<0|1>`
  - current: `S,I,2,<value>`
  - frequency: `S,F,2,<value>`
- Backend telemetry parser now supports legacy controller payload format:
  - `ch,I,V,F,STATUS`
- Backend telemetry model now also carries:
  - frequency
  - derived resistance
  - derived power
  - battery voltage in the dashboard gauge view
- Legacy `G` telemetry compatibility was tightened:
  - control bytes like `0x05` and `0x00` are stripped
  - controller frequency in `Hz` is converted to dashboard `kHz`
  - Distribution-mode prefixed payloads like `1,ch,I,V,F,STATUS` are accepted
  - the legacy voltage field is treated as `V1` only, not as battery voltage
- Example verified legacy telemetry:
  - `1,4.20,228.0,1500.0,3`

MQTT status:
- Initial target was HiveMQ Cloud.
- HiveMQ Cloud worked from the PC but not from the modem.
- Focused investigation strongly suggested a cloud-specific compatibility issue, likely related to missing modem-side support for required TLS behavior such as SNI.
- Working development broker is now:
  - `broker.hivemq.com:1883`
- Current modem status:
  - `AT+MQTTSTA:Connected`

Modem status:
- Modem: `USR-G771-E`
- Port: `COM3`
- Serial config:
  - `115200`
  - `8N1`
  - `RS485`
- Cellular side is alive:
  - LTE present
  - IP assigned
  - signal available
- Modem MQTT/TLS capability was verified against public HiveMQ brokers.
- After the topic migration to `basa/...`, the modem still reports:
  - `AT+MQTTSTA:Connected`

Per-device topic model:
- Each device now owns:
  - `command_topic`
  - `telemetry_topic`
- This supports multiple devices/modems without SN embedded in payload.

Verified backend behavior:
- Backend ingests live telemetry from MQTT.
- Backend publishes live command frames to MQTT.
- Device creation API works with explicit topics.
- Device deletion API works.
- Additional local end-to-end check on `2026-04-05`:
  - login, API, and authenticated WebSocket all worked
  - automatic watch-based polling triggered `G`
  - command and control POSTs returned the expected frame hex
  - no return telemetry arrived during that run
  - `COM3` could not be inspected because it was busy
- Additional deployed check on `2026-04-16`:
  - deployed site <-> broker path works in both directions
  - modem is connected to MQTT with the correct `basa/...` topics
  - no live telemetry was seen from the modem/controller during the observation window
  - injected command traffic did not appear on `COM3` during the forwarding check
- Clean-port recheck on `2026-04-16`:
  - `COM3` was confirmed free
  - injected MQTT command frames still did not appear on `COM3`
  - no telemetry appeared on the broker during a simultaneous listen window
- Transparent-mode loop result on `2026-04-16`:
  - three clean-port loops were run
  - MQTT-to-COM3 failed in both binary and ASCII tests
  - COM3-to-MQTT failed in a direct serial publish test
  - `Transparent mode` is therefore currently a proven blocker
- Distribution-mode result on `2026-04-16`:
  - after switching the modem to `Distribution mode`, serial started receiving broker data as `1,<payload>`
  - example observed from the site poller: `1,\x01G`
  - chosen direction is now to support bidirectional work in `Distribution mode`

Deployment readiness:
- Project is prepared for GitHub + Render deployment.
- Added:
  - `.gitignore`
  - `.python-version` pinned to `3.11.11`
  - `render.yaml`
  - updated `README.md` with deploy steps
- Local git repository is initialized.
- Project is pushed to GitHub:
  - `https://github.com/AviPerry/Zarnuk.git`
- Branch:
  - `main`

Current main gap:
- Final full hardware end-to-end validation with the real controller behavior and real telemetry interpretation is still pending.

Important defaults currently in use:
- Login:
  - `Admin / Admin123`
- Example working device/topics:
  - SN: `6673842E`
  - command topic: `basa/6673842E/command`
  - telemetry topic: `basa/6673842E/telemetry`
