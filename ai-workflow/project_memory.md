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
- Backend validates 8-char uppercase alphanumeric SN values.
- Backend builds controller command frames as:
  - `0x01 + SN + ',' + command + 0x00`
- Remote output control targets channel `2`.
- Current command uses `S,I,2,<value>`.
- Frequency command uses `S,F,2,<value>`.
- Legacy telemetry parsing supports `ch,I,V,F,STATUS`.
- Device management supports:
  - create device
  - delete device
  - editable friendly name per SN
- Friendly names are persisted locally in:
  - `app/data/devices.json`
- Each device still owns its own MQTT topics:
  - `command_topic`
  - `telemetry_topic`
- Login protection is enabled with default credentials:
  - `Admin / Admin123`

### MQTT Decisions
- Current working broker for development is HiveMQ public broker.
- Current working example topics are:
  - `basa/6673842E/command`
  - `basa/6673842E/telemetry`
- Device routing remains topic-based.
- SN remains inside the controller frame because the real controller expects it.

### Modem Findings
- Modem is USR-G771-E on `COM3`.
- Serial settings confirmed:
  - `115200 8N1`
  - `RS485`
- Distribution mode is the currently viable modem path.
- Transparent mode was proven unreliable in both directions.

### Current Focus
- Keep the working per-device topic path intact.
- Preserve SN-specific command framing.
- Add usability improvements without breaking the modem path.
