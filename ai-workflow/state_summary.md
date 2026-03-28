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
  - delete device flow
  - per-device MQTT topic inputs on creation
- Recent UI fixes:
  - search no longer resets during live updates
  - repeated watch subscriptions were fixed
  - inline command feedback was added

Authentication status:
- Cookie-based session auth is implemented.
- Frontend, API, and WebSocket are protected.
- Login is handled by `/api/auth/login`.

Protocol status:
- Outgoing command payloads no longer include the serial number.
- Device routing is topic-based.
- Current command frame format is:
  - `0x01 + command + 0x00`
- Verified live command outputs on `COM3`:
  - `ON` -> `01 53 2C 53 2C 31 2C 31 00`
  - `OFF` -> `01 53 2C 53 2C 31 2C 30 00`
  - automatic `G` poll -> `01 47 00`

Controller compatibility status:
- Backend control commands were aligned to the legacy RS485 reference format:
  - current: `S,I,1,<value>`
  - frequency: `S,F,1,<value>`
- Backend telemetry parser now supports legacy controller payload format:
  - `ch,I,V,F,STATUS`
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
  - SN: `663E8435`
  - command topic: `zeliger/663E8435/command`
  - telemetry topic: `zeliger/663E8435/telemetry`
