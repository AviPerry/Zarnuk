from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import AUTH_COOKIE_NAME, AUTH_COOKIE_VALUE, AUTH_PASSWORD, AUTH_USERNAME
from .device_manager import DeviceManager
from .models import (
    CommandRequest,
    ControlUpdateRequest,
    CreateDeviceRequest,
    DeviceListResponse,
    UpdateDeviceRequest,
)
from .mqtt_client import HiveMQClient
from .simulator import TelemetrySimulator

manager = DeviceManager()
simulator = TelemetrySimulator(manager)
mqtt_client: Optional[HiveMQClient] = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global mqtt_client
    mqtt_client = HiveMQClient(manager)
    manager.set_command_sender(mqtt_client.publish_command)
    await manager.start()
    await mqtt_client.start()
    if not mqtt_client.ready:
        await simulator.start()
    try:
        yield
    finally:
        await simulator.stop()
        await mqtt_client.stop()
        await manager.stop()


app = FastAPI(title="משדר זרנוק", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

LOGIN_HTML = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>כניסה | משדר זרנוק</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(circle at top, rgba(31,122,99,0.18), transparent 30%),
        linear-gradient(180deg, #f2efe7 0%, #fbf8f2 100%);
      color: #241d16;
    }
    .card {
      width: min(420px, calc(100vw - 32px));
      background: rgba(255,252,245,0.92);
      border: 1px solid rgba(73,59,37,0.12);
      border-radius: 26px;
      box-shadow: 0 18px 45px rgba(62, 43, 20, 0.12);
      padding: 28px;
    }
    h1 { margin: 0 0 8px; font-size: 2rem; }
    p { color: #6a5b49; margin: 0 0 20px; }
    form { display: grid; gap: 14px; }
    label { display: grid; gap: 6px; font-weight: 600; }
    input {
      border: 1px solid rgba(73,59,37,0.12);
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 1rem;
      background: white;
    }
    button {
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      cursor: pointer;
      font-weight: 700;
      color: white;
      background: linear-gradient(135deg, #1f7a63, #0f5f4b);
    }
    .error {
      display: none;
      background: rgba(155,45,48,0.12);
      color: #9b2d30;
      border-radius: 14px;
      padding: 12px 14px;
      margin-bottom: 14px;
    }
  </style>
</head>
<body>
  <section class="card">
    <h1>משדר זרנוק</h1>
    <p>כניסה למערכת הניטור והשליטה.</p>
    <div id="error" class="error">שם משתמש או סיסמה שגויים.</div>
    <form id="login-form">
      <label>
        שם משתמש
        <input id="username" type="text" autocomplete="username" value="Admin" />
      </label>
      <label>
        סיסמה
        <input id="password" type="password" autocomplete="current-password" value="Admin123" />
      </label>
      <button type="submit">כניסה</button>
    </form>
  </section>
  <script>
    const form = document.getElementById("login-form");
    const errorEl = document.getElementById("error");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorEl.style.display = "none";
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value
        })
      });
      if (!response.ok) {
        errorEl.style.display = "block";
        return;
      }
      window.location.href = "/";
    });
  </script>
</body>
</html>
"""


def is_authenticated_request(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE_NAME) == AUTH_COOKIE_VALUE


def is_authenticated_ws(websocket: WebSocket) -> bool:
    return websocket.cookies.get(AUTH_COOKIE_NAME) == AUTH_COOKIE_VALUE


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    allowed_paths = {"/login", "/api/auth/login", "/healthz"}
    if request.url.path in allowed_paths:
        return await call_next(request)
    if not is_authenticated_request(request):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    if is_authenticated_request(request):
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(LOGIN_HTML)


@app.get("/healthz", include_in_schema=False)
async def healthcheck():
    return {"ok": "true"}


@app.post("/api/auth/login")
async def login(payload: dict):
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))
    if not (compare_digest(username, AUTH_USERNAME) and compare_digest(password, AUTH_PASSWORD)):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=AUTH_COOKIE_VALUE,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return response


@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.get("/api/devices", response_model=DeviceListResponse)
async def list_devices() -> DeviceListResponse:
    return DeviceListResponse(devices=await manager.list_devices())


@app.post("/api/devices", status_code=201)
async def create_device(payload: CreateDeviceRequest):
    try:
        device = await manager.add_device(payload.sn, payload.command_topic, payload.telemetry_topic, payload.name)
        if mqtt_client is not None:
            await mqtt_client.sync_subscriptions()
        return device
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/devices/{sn}")
async def get_device(sn: str):
    try:
        return await manager.get_device(sn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Device {sn} not found") from exc


@app.delete("/api/devices/{sn}", status_code=204)
async def delete_device(sn: str) -> Response:
    try:
        await manager.remove_device(sn)
        return Response(status_code=204)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Device {sn} not found") from exc


@app.patch("/api/devices/{sn}")
async def update_device(sn: str, payload: UpdateDeviceRequest):
    try:
        return await manager.update_device_name(sn, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Device {sn} not found") from exc


@app.post("/api/devices/{sn}/output")
async def set_output(sn: str, payload: CommandRequest):
    command = payload.command.strip().lower()
    if command not in {"on", "off"}:
        raise HTTPException(status_code=400, detail="Command must be 'on' or 'off'")
    try:
        frame = await manager.set_output(sn, command == "on")
        return {"ok": True, "frameHex": frame.hex(" ").upper()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Device {sn} not found") from exc


@app.post("/api/devices/{sn}/controls")
async def update_controls(sn: str, payload: ControlUpdateRequest):
    try:
        frames = await manager.update_controls(sn, payload.current, payload.frequency)
        return {"ok": True, "framesHex": [frame.hex(" ").upper() for frame in frames]}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Device {sn} not found") from exc


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not is_authenticated_ws(websocket):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    active_watch_sn: Optional[str] = None
    receive_task: Optional[asyncio.Task] = None
    event_task: Optional[asyncio.Task] = None
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "devices.snapshot",
                    "payload": {
                        "devices": [device.model_dump(mode="json") for device in await manager.list_devices()]
                    },
                }
            )
        )
        while True:
            receive_task = asyncio.create_task(websocket.receive_text())
            event_task = asyncio.create_task(manager.next_event())
            done, pending = await asyncio.wait({receive_task, event_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

            if receive_task in done:
                data = json.loads(receive_task.result())
                action = data.get("action")
                sn = data.get("sn")
                if action == "watch" and sn:
                    if active_watch_sn and active_watch_sn != sn:
                        await manager.unwatch_device(active_watch_sn)
                    active_watch_sn = sn
                    await manager.watch_device(sn)
                elif action == "unwatch" and sn:
                    await manager.unwatch_device(sn)
                    if active_watch_sn == sn:
                        active_watch_sn = None
            elif event_task in done:
                await websocket.send_text(event_task.result().model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        for task in (receive_task, event_task):
            if task:
                task.cancel()
        if active_watch_sn:
            await manager.unwatch_device(active_watch_sn)
