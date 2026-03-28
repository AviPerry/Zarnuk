from __future__ import annotations

import asyncio
import math
import random
import time
from contextlib import suppress
from typing import Optional

from .device_manager import DeviceManager


class TelemetrySimulator:
    def __init__(self, manager: DeviceManager) -> None:
        self.manager = manager
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        phase = 0.0
        while True:
            await asyncio.sleep(1.0)
            phase += 0.35
            now = time.time()
            for index, device in enumerate(await self.manager.list_devices()):
                online = index != 2 or int(now) % 20 < 8
                if not online:
                    continue

                base = phase + index
                enabled = device.telemetry.output_enabled
                target_current = device.telemetry.target_current or 4.0
                ir = max(0.0, target_current + math.sin(base) * 0.7) if enabled else 0.0
                v1 = max(0.0, 220.0 + math.cos(base) * 8.0) if enabled else 0.0
                battery = max(10.6, device.telemetry.battery_voltage - random.uniform(-0.05, 0.04))
                vin = max(10.8, battery + random.uniform(-0.12, 0.15))

                await self.manager.update_from_telemetry(
                    device.sn,
                    vin=round(vin, 2),
                    v1=round(v1, 1),
                    ir=round(ir, 2),
                    battery_voltage=round(battery, 2),
                    short=enabled and ir > 5.7,
                    pwr_lim=enabled and v1 < 216.0,
                    no_load=enabled and ir < 0.4,
                )
