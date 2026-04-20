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
- UI is in Hebrew.
- App title is `משדר זרנוק`.
- Login page exists at `/login`.
- Credentials are currently `Admin / Admin123`.
- Overview screen supports:
  - search by SN or friendly name
  - add device by SN
  - delete device
- Device dashboard supports:
  - live gauges for `Ir`, `V1`, frequency, resistance, power, and battery voltage
  - channel 2 control
  - editable friendly name per device
  - fixed read-only MQTT topic display
- Device names and list are persisted in `app/data/devices.json`.

Protocol status:
- Outgoing command frame format is:
  - `0x01 + SN + ',' + command + 0x00`
- Control commands currently target channel `2`:
  - `S,S,2,<0|1>`
  - `S,I,2,<value>`
  - `S,F,2,<value>`
- Legacy telemetry parsing supports:
  - `ch,I,V,F,STATUS`
  - `1,ch,I,V,F,STATUS` in distribution mode
  - SN-framed payloads on shared MQTT topics
- Frequency is converted from controller `Hz` to dashboard `kHz`.
- Resistance and power are derived in the backend.

MQTT status:
- Working development broker is `broker.hivemq.com:1883`.
- Shared topics are now:
  - command: `basa/command`
  - telemetry: `basa/telemetry`
- Commands are routed by SN inside the frame.
- Shared telemetry attribution is reliable when the payload/frame includes the device SN.
- Backend now avoids guessing SN across multiple devices on the same shared topic.

Hardware/modem status:
- Modem: `USR-G771-E`
- Port: `COM3`
- Serial: `115200 8N1`
- Distribution mode is the currently viable modem direction.
- Transparent mode was previously proven unreliable in both directions.

Deployment status:
- Project is prepared for GitHub + Render deployment.
- Repo: `https://github.com/AviPerry/Zarnuk.git`
- `render.yaml` now uses shared MQTT topics.

Main remaining gap:
- Full end-to-end validation with the real controller on the shared-topic setup is still pending.
