# Zarnuk Transmitter

Web application for monitoring and controlling STM32-based devices over MQTT through a cellular modem path.

## Current Status

The project currently includes:

- FastAPI backend
- Single-page frontend served by FastAPI
- WebSocket live updates
- Login-protected UI, API, and WebSocket
- Hebrew user interface
- Systems overview screen
- Per-device dashboard
- Add and delete device flow
- Editable friendly name per device SN
- Shared MQTT topics with device identification by SN inside the payload/frame
- Legacy controller protocol compatibility

## Default Login

- Username: `Admin`
- Password: `Admin123`

Change these in production with environment variables.

## Protocol Model

Outgoing controller command frames are built as:

```text
0x01 + SN + ',' + command + 0x00
```

Examples:

- Poll status: `G`
- Output on channel 2: `S,S,2,1`
- Output off channel 2: `S,S,2,0`
- Set current on channel 2: `S,I,2,<value>`
- Set frequency on channel 2: `S,F,2,<value>`

The MQTT topics are now shared for all devices:

- Command topic: `basa/command`
- Telemetry topic: `basa/telemetry`

Device routing is based on the controller `SN`.

## Telemetry Support

The backend supports:

- legacy controller telemetry in the format `ch,I,V,F,STATUS`
- distribution-mode payloads such as `1,ch,I,V,F,STATUS`
- SN-prefixed framed payloads that arrive on the shared telemetry topic
- JSON telemetry, ideally including an `sn` field

Example legacy telemetry:

```text
1,4.20,228.0,1500.0,3
```

`STATUS` is interpreted as a bitmask for alerts such as `SHORT`, `PWR-LIM`, and `NO-LOAD`.

Note:
If multiple controllers publish to the same shared telemetry topic, the payload should include the device `SN` or arrive in an SN-framed format so the backend can attribute telemetry to the correct device.

## Device Management

Each device record contains:

- `sn`
- editable `name`
- online/offline state
- last telemetry snapshot

The device list is persisted locally in:

```text
app/data/devices.json
```

## Local Run

Install dependencies:

```powershell
py -3.11 -m pip install -r requirements.txt
```

Run the app:

```powershell
py -3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

- `http://127.0.0.1:8000/login`

## Environment Variables

Typical configuration:

```env
MQTT_ENABLED=true
MQTT_HOST=broker.hivemq.com
MQTT_PORT=1883
MQTT_TLS=false
MQTT_CLIENT_ID=basa-web-backend
MQTT_COMMAND_TOPIC=basa/command
MQTT_TELEMETRY_TOPIC=basa/telemetry
AUTH_USERNAME=Admin
AUTH_PASSWORD=Admin123
```

## Render Deployment

This repository already includes:

- `render.yaml`
- `.python-version` pinned to `3.11.11`

Recommended Render service type:

- `Web Service`

If Render does not auto-detect settings, use:

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Required Render environment variables:

- `AUTH_USERNAME`
- `AUTH_PASSWORD`

Optional MQTT environment variables:

- `MQTT_ENABLED`
- `MQTT_HOST`
- `MQTT_PORT`
- `MQTT_TLS`
- `MQTT_CLIENT_ID`
- `MQTT_COMMAND_TOPIC`
- `MQTT_TELEMETRY_TOPIC`

## Hardware Notes

Current modem used during development:

- Model: `USR-G771-E`
- Port: `COM3`
- Serial: `115200 8N1`
- Interface: `RS485`

Verified:

- modem AT communication
- modem MQTT connectivity to HiveMQ public broker
- command delivery from MQTT to serial path in distribution mode
- backend telemetry ingest from MQTT

Still pending:

- full end-to-end validation with the real controller behavior under live hardware conditions across the shared-topic setup
