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
  - dashboard live updates no longer rebuild the full DOM on every telemetry/poll message
  - current/frequency inputs now preserve user focus while live updates continue
  - dashboard monitoring view now also shows frequency, resistance, power, and battery voltage as gauges
- Polling UX hardening:
  - backend `G` poll commands are now silent for the UI
  - `last_command_hex` is no longer overwritten by background `G`
  - poll loop publishes `devices.snapshot` only when online/offline state actually changes
- UI language is now Hebrew.
- App title was renamed to `משדר זרנוק`.
- Device management was added to the app:
  - create device from overview screen
  - delete device from device dashboard
  - delete device directly from overview cards
  - `online/offline` indication remains visible
  - default seed list was reduced to a single device: `663E8435`
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
  - backend telemetry state now carries `frequency`
  - backend also derives:
    - `resistance = V1 / Ir`
    - `power = V1 * Ir`

### MQTT Decisions
- Initial target broker was HiveMQ Cloud.
- Current working broker for development is HiveMQ public broker.
- Backend is configured to support real MQTT through `.env`.
- Current working topics chosen for the modem path are:
  - device publish telemetry to `basa/663E8435/telemetry`
  - device subscribe for commands on `basa/663E8435/command`
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
  - `AT+MQTTCID:basa-663E8435-modem`
  - publish topic: `basa/663E8435/telemetry`
  - subscribe topic: `basa/663E8435/command`
  - MQTT serial mode is now confirmed working in `Distribution mode`
- Verified modem status:
  - `AT+MQTTSTA:Connected`
  - rechecked successfully after topic migration to `basa/...`

### Verified Backend MQTT Flow
- Backend `.env` now targets:
  - host: `broker.hivemq.com`
  - port: `1883`
  - TLS: `OFF`
  - command topic: `basa/663E8435/command`
  - telemetry topic: `basa/663E8435/telemetry`
- Confirmed live telemetry ingestion:
  - publishing JSON telemetry to `basa/663E8435/telemetry` updates device `663E8435` in the backend API
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
- Additional local end-to-end validation on `2026-04-05`:
  - local FastAPI app started successfully with real startup path
  - login API succeeded with `Admin / Admin123`
  - authenticated `GET /api/devices` succeeded
  - authenticated WebSocket `/ws` succeeded
  - sending `watch` for `663E8435` caused automatic polling activity
  - `POST /api/devices/663E8435/output` returned frame `01 53 2C 53 2C 31 2C 30 00`
  - `POST /api/devices/663E8435/controls` returned frames for current and frequency updates
  - backend device state updated `target_current=1.2` and `target_frequency=2.5`
  - backend `last_command_hex` ended at `01 47 00`, confirming automatic `G` poll activity
  - no fresh telemetry returned during this test window, so the device eventually appeared offline
  - direct serial verification on `COM3` was blocked because the port was already in use by another process
- Additional deployed end-to-end verification on `2026-04-16`:
  - Render site login succeeded at `https://zarnuk-1.onrender.com`
  - deployed `GET /api/devices/663E8435` succeeded
  - deployed `POST /api/devices/663E8435/output` published `01 53 2C 53 2C 31 2C 30 00`
  - local MQTT subscriber received that exact frame on `basa/663E8435/command`
  - publishing test telemetry `1,4.20,228.0,1500.0,3` to `basa/663E8435/telemetry` updated the deployed site state to `online=true`
  - therefore deployed site <-> broker communication is confirmed working in both directions

### Latest Modem/Broker Verification
- On `2026-04-16`, modem AT checks showed:
  - `AT+MQTTSTA:Connected`
  - publish topic still set to `basa/663E8435/telemetry`
  - subscribe topic still set to `basa/663E8435/command`
- A 12-second broker listen window on `basa/663E8435/telemetry` received no live modem/controller messages
- Injecting `01 53 2C 53 2C 31 2C 30 00` to `basa/663E8435/command` did not produce observable bytes on `COM3` during the check window
- Current strongest suspicion:
  - the missing path is now modem/controller-side forwarding or controller-originated telemetry generation, not the website/broker path
- Clean-port verification on `2026-04-16` after fully closing `USR-CAT1`:
  - `COM3` opened successfully with no contention
  - injecting `01 47 00`, `01 53 2C 53 2C 31 2C 30 00`, and `01 53 2C 49 2C 31 2C 31 2E 32 30 30 00` to `basa/663E8435/command` still produced no bytes on `COM3`
  - simultaneous 15-second listening on `COM3` and `basa/663E8435/telemetry` produced no serial bytes and no telemetry messages
  - this strengthens the conclusion that the currently configured modem path is not forwarding MQTT traffic onto RS485 and is not publishing controller data back to MQTT
- Transparent-mode retest loops on `2026-04-16`:
  - loop 1: verified `AT+MQTTMOD:0`, `AT+MQTTSTA:Connected`, and correct `basa/...` topics, then injected binary MQTT frames to `basa/663E8435/command`; no bytes appeared on `COM3`
  - loop 2: after the modem appeared back in data path, injected both ASCII and binary MQTT payloads to `basa/663E8435/command`; still no bytes appeared on `COM3`
  - loop 3: wrote serial payloads directly to `COM3` while listening on `basa/663E8435/telemetry`; no telemetry was published
  - conclusion: in the current real setup, `Transparent mode` is not functioning as a live bridge in either direction
- Distribution-mode breakthrough on `2026-04-16`:
  - after switching the modem MQTT serial mode to `Distribution mode`, subscribed MQTT data started appearing on serial as `1,<payload>`
  - observed examples from the website poll loop:
    - `1,\x01G`
  - this confirms the modem does bridge broker -> serial in `Distribution mode`
  - architectural implication:
    - broker-to-controller path can work if the controller strips the `1,` topic symbol prefix
    - controller-to-broker path can work if the controller publishes serial data in the format `1,<payload>` so the modem maps it to topic 1
  - current preferred direction is to keep `Distribution mode` and adapt the controller/protocol handling around the `1,` prefix

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
