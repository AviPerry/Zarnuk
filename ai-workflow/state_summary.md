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
- Overview supports:
  - search by SN or friendly name
  - add device with topic inputs
  - delete device
- Device dashboard supports:
  - live gauges
  - channel 2 control
  - editable friendly name
- Friendly names are persisted in `app/data/devices.json`.

Protocol status:
- Outgoing command frame format is:
  - `0x01 + SN + ',' + command + 0x00`
- SN remains controller-specific per selected device.
- Control commands currently target channel `2`.

MQTT status:
- Working development broker is `broker.hivemq.com:1883`.
- Working per-device topic model remains:
  - command: `basa/<SN>/command`
  - telemetry: `basa/<SN>/telemetry`

Hardware/modem status:
- Modem: `USR-G771-E`
- Port: `COM3`
- Serial: `115200 8N1`
- Distribution mode is currently the viable modem direction.

Main remaining gap:
- Full end-to-end validation with the real controller is still pending after each deployed update.
