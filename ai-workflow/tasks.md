## Current Tasks

- [x] Build FastAPI + frontend MVP
- [x] Add backend MQTT support and `.env` config
- [x] Confirm modem serial communication on `COM3`
- [x] Prepare project for GitHub + Render deployment
- [x] Translate UI to Hebrew and rename the app
- [x] Add login page and protect frontend/API/WebSocket
- [x] Align backend control commands and telemetry parsing with the legacy controller protocol
- [x] Restore SN-prefixed command frames and move control to channel 2
- [x] Stop dashboard rerender churn during background `G` polling
- [x] Add device create/delete flow
- [x] Add friendly device names persisted for the web UI
- [x] Move app from per-device MQTT topics to fixed shared topics `basa/command` and `basa/telemetry`
- [x] Keep command routing by SN while using shared topics
- [ ] Validate full shared-topic end-to-end behavior with the real controller and modem
- [ ] Deploy the latest shared-topic build to Render and verify it live
