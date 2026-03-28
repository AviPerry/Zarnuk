## Project Memory

### Goal
Build a web system for monitoring and controlling STM32-based devices through a cellular modem path.

### Stack Chosen
- Backend: FastAPI
- Frontend: static SPA served by FastAPI
- Realtime: WebSocket
- MQTT client in backend: paho-mqtt
- Local modem tooling: Python scripts with pyserial

### Current App State
- MVP web app exists with:
  - Systems Overview screen
  - Per-device dashboard
  - live updates via WebSocket
  - command routing and telemetry simulation
- Backend validates 8-char uppercase alphanumeric SN values.
- Backend builds protocol frames as:
  - `0x01 + command + 0x00`
- Backend expects telemetry beginning with `0x05`.
- Low battery protection is implemented in backend and UI.
- Backend is now reconfigured to use the working public broker path from `.env`.
- Frontend cleanup performed:
  - fixed repeated device `watch` registration during live re-renders
  - preserved overview search text during live updates
  - added inline command feedback area in the dashboard
  - improved device card button styling/consistency
- UI language is now Hebrew.
- App title was renamed to `משדר זרנוק`.
- Device management was added to the app:
  - create device from overview screen
  - delete device from device dashboard
  - `online/offline` indication remains visible
- Device creation now requires per-device MQTT topics:
  - `command_topic`
  - `telemetry_topic`
- This allows coordination with multiple modems/devices without embedding SN in the payload.
- App authentication was added:
  - login page at `/login`
  - cookie-based session protection
  - default credentials: `Admin / Admin123`
  - API and WebSocket now require authentication
- Deployment prep was added:
  - `.gitignore`
  - `render.yaml`
  - `.python-version` pinned to `3.11.11` for Render compatibility
  - `README.md` updated in English with current GitHub + Render deployment instructions
  - local git repository initialized with `git init`
  - project was pushed to GitHub repository `https://github.com/AviPerry/Zarnuk.git`
  - local branch `main` now tracks `origin/main`
- Backend/controller alignment update:
  - current command now uses `S,I,1,<value>`
  - frequency command now uses `S,F,1,<value>`
  - backend telemetry parser now supports legacy controller payload format `ch,I,V,F,STATUS`

### MQTT Decisions
- Initial target broker was HiveMQ Cloud.
- Current working broker for development is HiveMQ public broker.
- Backend is configured to support real MQTT through `.env`.
- Current working topics chosen for the modem path are:
  - device publish telemetry to `zeliger/663E8435/telemetry`
  - device subscribe for commands on `zeliger/663E8435/command`
- Device routing is now topic-based.
- Command payloads no longer include the serial number.
- Each device now owns its own command/telemetry topics in the backend model.

### Modem Findings
- Modem is USR-G771-E on `COM3`.
- Serial settings confirmed:
  - `115200 8N1`
  - interface type reported as `RS485`
- Modem responds to AT commands when terminated with `CRLF` (`\r\n`).
- Cellular side is alive:
  - `AT+SYSINFO -> LTE`
  - `AT+CIP` returns IP
  - `AT+CSQ` returns signal (`18,99`)

### Modem Reconfiguration Performed
- Changed modem MQTT server from old EMQX host to HiveMQ host.
- Enabled SSL.
- Changed MQTT topic mapping to:
  - publish: `stm32/telemetry`
  - subscribe: `stm32/command`
- Tried both broker usernames:
  - `Admin`
  - `USR-G771`
- Set SSL auth to `NONE`.
- Saved settings with `AT+S`.

### Current Blocking Issue
- Full modem-path end-to-end verification is still pending.
- Backend-to-broker verification now works.
- Public deployment hardening started with login/session protection.

### Likely Causes To Investigate
- HiveMQ credentials are no longer the primary suspect.
- HiveMQ Cloud TLS requirements may not fully match the modem's SSL/TLS capabilities.
- Broker-side constraints may differ from the modem's older MQTT/SSL implementation.
- The modem's LTE-side connectivity or TLS handshake behavior is now the most likely failure point.

### New Verified Findings On Home Network
- PC-side access to HiveMQ works from the home network.
- Both usernames successfully receive MQTT CONNACK over HiveMQ WebSocket TLS:
  - `Admin`
  - `USR-G771`
- Pub/Sub from the PC to real broker topics works:
  - tested topic: `stm32/telemetry`
- Therefore HiveMQ broker reachability, account validity, and topic permissions are confirmed from the PC.
- The modem still reports `AT+MQTTSTA:Disconnected` even after these confirmations.

### Additional Modem Diagnostics
- Firmware version:
  - `V1.3.25.000000.0000`
- Build time:
  - `2022-10-13 11:22:58`
- TLS mode on modem:
  - `AT+SSLVER:TLS12`
- Diagnostic control tests:
  - modem connected successfully to `broker.hivemq.com:1883` with `SSLEN=OFF`
  - modem connected successfully to `broker.hivemq.com:8883` with `SSLEN=ON`, `SSLVER=TLS12`, `SSLAUTH=NONE`
- Therefore:
  - modem MQTT over LTE works
  - modem TLS 1.2 over LTE works
  - remaining incompatibility is specific to the target HiveMQ Cloud cluster rather than generic MQTT/TLS support

### Working Modem Configuration
- The modem is now configured to a working development broker:
  - `broker.hivemq.com:1883`
- Current modem MQTT configuration:
  - `AT+SSLEN:OFF`
  - `AT+MQTTUSER:zeliger`
  - `AT+MQTTPSW:zeliger123`
  - `AT+MQTTCID:zeliger-663E8435-modem`
  - publish topic: `zeliger/663E8435/telemetry`
  - subscribe topic: `zeliger/663E8435/command`
- Verified modem status:
  - `AT+MQTTSTA:Connected`

### Verified Backend MQTT Flow
- Backend `.env` now targets:
  - host: `broker.hivemq.com`
  - port: `1883`
  - TLS: `OFF`
  - command topic: `zeliger/663E8435/command`
  - telemetry topic: `zeliger/663E8435/telemetry`
- Confirmed live telemetry ingestion:
  - publishing JSON telemetry to `zeliger/663E8435/telemetry` updates device `663E8435` in the backend API
  - publishing legacy controller telemetry like `1,4.20,228.0,1500.0,3` also updates device `663E8435`
- Confirmed live command publishing:
  - calling `POST /api/devices/663E8435/output` now publishes frames without SN in the payload
  - verified live on `COM3`:
    - `ON` -> `01 53 2C 53 2C 31 2C 31 00`
    - `OFF` -> `01 53 2C 53 2C 31 2C 30 00`
    - automatic `G` poll -> `01 47 00`
  - verified command frame shapes for controller tuning:
    - current `1.234` -> `01 53 2C 49 2C 31 2C 31 2E 32 33 34 00`
    - frequency `2.5` -> `01 53 2C 46 2C 31 2C 32 2E 35 00`
- Confirmed device management API flow:
  - `POST /api/devices` creates a new device with explicit command/telemetry topics
  - `DELETE /api/devices/{sn}` removes it

### Remaining Modem-Path Uncertainty
- Command-path delivery from MQTT back onto `COM3` is now confirmed.
- The main remaining step is full hardware end-to-end validation with the actual controller behavior and telemetry parsing.

### SNI Investigation
- A focused search across the official USR-G771-E user manual and the AT command manual did not reveal any documented SNI setting or AT command.
- The documented SSL-related AT surface found was:
  - `AT+SSLEN`
  - `AT+SSLCRT`
  - `AT+SSLVER`
  - `AT+SSLAUTH`
- No official evidence of configurable SNI support was found in the reviewed documentation.
- Working assumption now: if HiveMQ Cloud requires SNI or a cloud-specific TLS behavior, the modem likely cannot be adjusted for it with documented AT commands.

### Local Tooling Added
- `tools/serial_probe.py`
- `tools/modem_at_session.py`

### Important Files
- `app/main.py`
- `app/device_manager.py`
- `app/mqtt_client.py`
- `.env`
- `tools/serial_probe.py`
- `tools/modem_at_session.py`
- `render.yaml`
