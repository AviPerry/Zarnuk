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
- Device create/delete flow
- Per-device MQTT command and telemetry topics
- Legacy controller protocol compatibility

## Default Login

- Username: `Admin`
- Password: `Admin123`

Change these in production with environment variables.

## Protocol Model

Outgoing controller command frames are built as:

```text
0x01 + command + 0x00
```

Examples:

- Poll status: `G`
- Output on: `S,S,1,1`
- Output off: `S,S,1,0`
- Set current: `S,I,1,<value>`
- Set frequency: `S,F,1,<value>`

Device identity is no longer embedded in the payload. Routing is topic-based.

## Telemetry Support

The backend supports legacy controller telemetry in this format:

```text
ch,I,V,F,STATUS
```

Example:

```text
1,4.20,228.0,1500.0,3
```

`STATUS` is interpreted as a bitmask for controller alerts such as `SHORT`, `PWR-LIM`, and `NO-LOAD`.

## MQTT Setup

The current working development broker is:

- Host: `broker.hivemq.com`
- Port: `1883`
- TLS: `false`

Example device topics:

- Command topic: `basa/663E8435/command`
- Telemetry topic: `basa/663E8435/telemetry`

Each device can define its own:

- `command_topic`
- `telemetry_topic`

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
AUTH_USERNAME=Admin
AUTH_PASSWORD=Admin123
SESSION_SECRET=replace-with-a-long-random-secret
```

Use `.env.example` as the starting point.

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
- `SESSION_SECRET`

Optional MQTT environment variables:

- `MQTT_ENABLED`
- `MQTT_HOST`
- `MQTT_PORT`
- `MQTT_TLS`
- `MQTT_CLIENT_ID`

## Public vs Private on Render

If you deploy this as a `Web Service`, it is publicly reachable through a Render `onrender.com` URL.

If you do not want public internet access, Render's official guidance is to use a `Private Service` instead. A private service is reachable only from your other Render services on the same private network and does not get a public `onrender.com` URL.

For this project:

- Use `Web Service` if you want to open the dashboard from your browser or phone
- Use `Private Service` only if another public service will sit in front of it

Application-level login is still recommended even for a public web service.

## Hardware Notes

Current modem used during development:

- Model: `USR-G771-E`
- Port: `COM3`
- Serial: `115200 8N1`
- Interface: `RS485`

Verified:

- modem AT communication
- modem MQTT connectivity to HiveMQ public broker
- command delivery from MQTT to serial path
- backend telemetry ingest from MQTT

Still pending:

- full end-to-end validation with the real controller behavior under live hardware conditions
