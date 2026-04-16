from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from contextlib import suppress
from typing import Awaitable, Callable, Optional

from .config import DEFAULT_POLL_SECONDS, LOW_BAT_THRESHOLD, ONLINE_TIMEOUT_SECONDS
from .models import AlertName, DeviceState, DeviceTelemetry, EventEnvelope
from .protocol import build_command_frame, frame_to_hex, validate_sn


class DeviceManager:
    def __init__(self) -> None:
        self.devices: dict[str, DeviceState] = {}
        self.watchers: dict[str, int] = defaultdict(int)
        self.events: asyncio.Queue[EventEnvelope] = asyncio.Queue()
        self._poll_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._command_sender: Optional[Callable[[str, bytes, str], Awaitable[None]]] = None
        self._seed_devices()

    def _seed_devices(self) -> None:
        for sn, vin, battery, online in [
            ("663E8435", 12.7, 12.6, True),
        ]:
            alerts = [AlertName.LOW_BAT] if battery < LOW_BAT_THRESHOLD else []
            self.devices[sn] = DeviceState(
                sn=sn,
                command_topic=f"basa/{sn}/command",
                telemetry_topic=f"basa/{sn}/telemetry",
                online=online,
                telemetry=DeviceTelemetry(
                    vin=vin,
                    v1=0.0,
                    ir=0.0,
                    battery_voltage=battery,
                    healthy=not alerts,
                    alerts=alerts,
                ),
                last_seen_epoch=time.time() if online else 0.0,
            )

    async def start(self) -> None:
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._poll_loop())

    def set_command_sender(self, sender: Optional[Callable[[str, bytes, str], Awaitable[None]]]) -> None:
        self._command_sender = sender

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._poll_task

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(DEFAULT_POLL_SECONDS)
            watched = [sn for sn, count in self.watchers.items() if count > 0]
            for sn in watched:
                await self.send_command(sn, "G")

            now = time.time()
            status_changed = False
            for device in self.devices.values():
                next_online = (now - device.last_seen_epoch) <= ONLINE_TIMEOUT_SECONDS
                if device.online != next_online:
                    device.online = next_online
                    status_changed = True
            if status_changed:
                await self._publish_devices()

    async def list_devices(self) -> list[DeviceState]:
        return list(self.devices.values())

    async def add_device(self, sn: str, command_topic: str, telemetry_topic: str) -> DeviceState:
        valid_sn = validate_sn(sn)
        if valid_sn in self.devices:
            raise ValueError(f"Device {valid_sn} already exists")
        for device in self.devices.values():
            if device.command_topic == command_topic.strip():
                raise ValueError(f"Command topic already in use: {command_topic}")
            if device.telemetry_topic == telemetry_topic.strip():
                raise ValueError(f"Telemetry topic already in use: {telemetry_topic}")
        device = DeviceState(
            sn=valid_sn,
            command_topic=command_topic.strip(),
            telemetry_topic=telemetry_topic.strip(),
        )
        self.devices[valid_sn] = device
        await self._publish_devices()
        return device

    async def remove_device(self, sn: str) -> None:
        valid_sn = validate_sn(sn)
        if valid_sn not in self.devices:
            raise KeyError(valid_sn)
        self.devices.pop(valid_sn)
        self.watchers.pop(valid_sn, None)
        await self._publish_devices()

    async def get_device(self, sn: str) -> DeviceState:
        valid_sn = validate_sn(sn)
        device = self.devices.get(valid_sn)
        if device is None:
            raise KeyError(valid_sn)
        return device

    async def watch_device(self, sn: str) -> None:
        valid_sn = validate_sn(sn)
        async with self._lock:
            self.watchers[valid_sn] += 1

    async def unwatch_device(self, sn: str) -> None:
        valid_sn = validate_sn(sn)
        async with self._lock:
            self.watchers[valid_sn] = max(0, self.watchers[valid_sn] - 1)

    async def send_command(self, sn: str, command: str) -> bytes:
        device = await self.get_device(sn)
        frame = build_command_frame(device.sn, command)
        is_poll_command = command.strip().upper() == "G"
        if not is_poll_command:
            device.last_command_hex = frame_to_hex(frame)
        if self._command_sender is not None:
            await self._command_sender(device.sn, frame, command)
        if not is_poll_command:
            await self.events.put(
                EventEnvelope(
                    type="command.sent",
                    payload={"sn": device.sn, "command": command, "frameHex": device.last_command_hex},
                )
            )
            await self._publish_device(device.sn)
        return frame

    async def set_output(self, sn: str, enabled: bool) -> bytes:
        device = await self.get_device(sn)
        if enabled and device.telemetry.battery_voltage < LOW_BAT_THRESHOLD:
            raise ValueError("Remote start blocked: battery voltage is below the configured threshold")
        device.telemetry.output_enabled = enabled
        return await self.send_command(sn, "S,S,1,1" if enabled else "S,S,1,0")

    async def update_controls(self, sn: str, current: Optional[float], frequency: Optional[float]) -> list[bytes]:
        device = await self.get_device(sn)
        frames: list[bytes] = []
        if current is not None:
            device.telemetry.target_current = current
            frames.append(await self.send_command(sn, f"S,I,1,{current:.3f}"))
        if frequency is not None:
            device.telemetry.target_frequency = frequency
            frames.append(await self.send_command(sn, f"S,F,1,{frequency:.1f}"))
        await self._publish_device(device.sn)
        return frames

    async def update_from_telemetry(
        self,
        sn: str,
        *,
        vin: float,
        v1: float,
        ir: float,
        battery_voltage: float,
        short: bool,
        pwr_lim: bool,
        no_load: bool,
    ) -> None:
        valid_sn = validate_sn(sn)
        device = self.devices.setdefault(valid_sn, DeviceState(sn=valid_sn))
        alerts: list[AlertName] = []
        if short:
            alerts.append(AlertName.SHORT)
        if pwr_lim:
            alerts.append(AlertName.PWR_LIM)
        if no_load:
            alerts.append(AlertName.NO_LOAD)
        if battery_voltage < LOW_BAT_THRESHOLD:
            alerts.append(AlertName.LOW_BAT)

        device.telemetry = DeviceTelemetry(
            vin=vin,
            v1=v1,
            ir=ir,
            battery_voltage=battery_voltage,
            healthy=not any(alert in alerts for alert in [AlertName.SHORT, AlertName.PWR_LIM]),
            alerts=alerts,
            output_enabled=device.telemetry.output_enabled,
            target_current=device.telemetry.target_current,
            target_frequency=device.telemetry.target_frequency,
        )
        device.online = True
        device.last_seen_epoch = time.time()
        await self._publish_device(valid_sn)

    async def _publish_device(self, sn: str) -> None:
        device = await self.get_device(sn)
        await self.events.put(
            EventEnvelope(type="device.updated", payload={"device": device.model_dump(mode="json")})
        )

    async def _publish_devices(self) -> None:
        await self.events.put(
            EventEnvelope(
                type="devices.snapshot",
                payload={"devices": [device.model_dump(mode="json") for device in self.devices.values()]},
            )
        )

    async def next_event(self) -> EventEnvelope:
        return await self.events.get()
