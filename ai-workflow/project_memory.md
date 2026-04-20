## Project Memory

### Goal
Build a web system for monitoring and controlling STM32-based devices through a cellular modem path.

### Stack
- FastAPI backend
- Static SPA frontend served by FastAPI
- WebSocket for live updates
- `paho-mqtt` for MQTT integration
- Local serial/modem tooling in Python

### Key Decisions
- Login protection is enabled with cookie-based auth.
- Default credentials are `Admin / Admin123`.
- Controller command frames include the device SN:
  - `0x01 + SN + ',' + command + 0x00`
- Channel control currently targets channel `2`.
- Shared MQTT topics are now the default architecture:
  - `basa/command`
  - `basa/telemetry`
- Device list and friendly names are persisted locally in:
  - `app/data/devices.json`
- UI no longer allows per-device topic editing.

### Current Device/UI Behavior
- Overview page shows devices with:
  - SN
  - friendly name
  - online/offline state
  - quick health metrics
- Dashboard shows:
  - Ir, V1, frequency, resistance, power, battery voltage
  - channel 2 ON/OFF
  - current/frequency setpoints
  - alert state
  - editable friendly name

### Telemetry Handling
- Backend supports:
  - legacy CSV telemetry: `ch,I,V,F,STATUS`
  - distribution-mode prefixed CSV: `1,ch,I,V,F,STATUS`
  - SN-framed packets on shared topics
  - JSON payloads
- Legacy voltage field is treated as `V1`, not battery voltage.
- Battery voltage is kept separate in the dashboard model.
- Backend computes:
  - `resistance = V1 / Ir`
  - `power = V1 * Ir`

### MQTT/Modem Findings
- HiveMQ public broker works with the modem.
- Distribution mode is the preferred modem path.
- Transparent mode was tested repeatedly and treated as blocked.
- Shared-topic telemetry requires SN in the payload/frame for safe routing when multiple devices are active.

### Deployment
- Render web service config exists in `render.yaml`.
- Repo is on GitHub:
  - `https://github.com/AviPerry/Zarnuk.git`

### Current Focus
- Keep the web app aligned with the shared-topic modem setup.
- Finish full real-hardware end-to-end validation on the updated architecture.
