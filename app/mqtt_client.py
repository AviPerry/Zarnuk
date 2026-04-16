from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any, Optional

import paho.mqtt.client as mqtt

from .config import (
    MQTT_CLIENT_ID,
    MQTT_ENABLED,
    MQTT_HOST,
    MQTT_KEEPALIVE,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_TLS,
    MQTT_USERNAME,
    START_TLM,
)
from .device_manager import DeviceManager

logger = logging.getLogger(__name__)


class HiveMQClient:
    def __init__(self, manager: DeviceManager) -> None:
        self.manager = manager
        self.client: Optional[mqtt.Client] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connected = asyncio.Event()

    @property
    def enabled(self) -> bool:
        return MQTT_ENABLED

    @property
    def ready(self) -> bool:
        return self.enabled

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if not self.enabled:
            logger.info("MQTT disabled. Using simulator mode.")
            return

        self.client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if MQTT_TLS:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.connect_async(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
        self.client.loop_start()
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning("MQTT connection timed out. Falling back to simulator mode.")

    async def stop(self) -> None:
        if self.client is None:
            return
        self.client.loop_stop()
        self.client.disconnect()
        self.client = None

    async def publish_command(self, sn: str, frame: bytes, command: str) -> None:
        if not self.client or not self.ready:
            return
        device = await self.manager.get_device(sn)
        payload = frame
        properties = mqtt.Properties(mqtt.PacketTypes.PUBLISH)
        properties.UserProperty = [("sn", sn), ("command", command)]
        result = self.client.publish(device.command_topic, payload=payload, qos=1, properties=properties)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("MQTT publish failed for %s: rc=%s", sn, result.rc)

    async def sync_subscriptions(self) -> None:
        if not self.client or not self.ready:
            return
        topics = {(device.telemetry_topic, 1) for device in self.manager.devices.values() if device.telemetry_topic}
        for topic, qos in topics:
            self.client.subscribe(topic, qos=qos)

    def _on_connect(self, client: mqtt.Client, _: Any, __: Any, reason_code: Any, ___: Any = None) -> None:
        logger.info("MQTT connected with reason code %s", reason_code)
        topics = {(device.telemetry_topic, 1) for device in self.manager.devices.values() if device.telemetry_topic}
        for topic, qos in topics:
            client.subscribe(topic, qos=qos)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._connected.set)

    def _on_disconnect(self, _: mqtt.Client, __: Any, reason_code: Any, ___: Any = None) -> None:
        logger.info("MQTT disconnected with reason code %s", reason_code)

    def _on_message(self, _: mqtt.Client, __: Any, msg: mqtt.MQTTMessage) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(asyncio.create_task, self._handle_message(msg.topic, msg.payload))

    async def _handle_message(self, topic: str, payload: bytes) -> None:
        data = self._decode_payload(topic, payload)
        if not data:
            return
        try:
            await self.manager.update_from_telemetry(
                data["sn"],
                vin=float(data["vin"]) if data.get("vin") is not None else None,
                v1=float(data.get("v1", 0.0)),
                ir=float(data.get("ir", 0.0)),
                frequency=float(data.get("frequency", 0.0)),
                battery_voltage=(
                    float(data["battery_voltage"])
                    if data.get("battery_voltage") is not None
                    else None
                ),
                short=bool(data.get("short", False)),
                pwr_lim=bool(data.get("pwr_lim", False)),
                no_load=bool(data.get("no_load", False)),
            )
        except Exception as exc:
            logger.warning("Failed to process telemetry payload: %s", exc)

    def _decode_payload(self, topic: str, payload: bytes) -> Optional[dict[str, Any]]:
        if not payload:
            return None

        if payload[0] == START_TLM:
            payload = payload[1:]

        try:
            text = payload.decode("utf-8", errors="ignore")
        except UnicodeDecodeError:
            logger.warning("Telemetry payload is not UTF-8 decodable yet")
            return None

        text = self._sanitize_text(text)
        if not text:
            return None

        if text.startswith("{"):
            data = json.loads(text)
            if "sn" not in data:
                data["sn"] = self._infer_sn_from_topic(topic)
            return data

        legacy = self._decode_legacy_csv(text, topic)
        if legacy:
            return legacy

        if "," in text:
            sn, raw = text.split(",", 1)
            data: dict[str, Any] = {"sn": sn.strip().upper()}
            for chunk in raw.split(","):
                if "=" not in chunk:
                    continue
                key, value = chunk.split("=", 1)
                normalized_key = key.strip().lower()
                normalized_value = value.strip()
                if normalized_value.lower() in {"true", "false"}:
                    data[normalized_key] = normalized_value.lower() == "true"
                else:
                    data[normalized_key] = normalized_value
            if "battery_voltage" not in data and "battery" in data:
                data["battery_voltage"] = data["battery"]
            return data

        return None

    def _decode_legacy_csv(self, text: str, topic: str) -> Optional[dict[str, Any]]:
        parts = [part.strip() for part in text.split(",")]
        if len(parts) >= 6 and self._looks_like_distribution_prefixed_legacy(parts):
            parts = parts[1:]

        if len(parts) < 5:
            return None
        try:
            channel = int(float(parts[0]))
            current = float(parts[1])
            voltage = float(parts[2])
            frequency_raw = float(parts[3])
            status = int(float(parts[4]))
        except ValueError:
            return None

        sn = self._infer_sn_from_topic(topic)
        return {
            "sn": sn,
            "channel": channel,
            "ir": current,
            "v1": voltage,
            "vin": None,
            "battery_voltage": None,
            "frequency": frequency_raw / 1000.0,
            "short": bool(status & 1),
            "pwr_lim": bool(status & 2),
            "no_load": bool(status & 4),
        }

    def _sanitize_text(self, text: str) -> str:
        return "".join(ch for ch in text if ch == "\n" or ch == "\r" or 32 <= ord(ch) <= 126).strip()

    def _looks_like_distribution_prefixed_legacy(self, parts: list[str]) -> bool:
        try:
            topic_index = int(float(parts[0]))
            channel = int(float(parts[1]))
            float(parts[2])
            float(parts[3])
            float(parts[4])
            int(float(parts[5]))
        except ValueError:
            return False
        return 1 <= topic_index <= 10 and channel in {0, 1, 2}

    def _infer_sn_from_topic(self, topic: str) -> str:
        for device in self.manager.devices.values():
            if device.telemetry_topic == topic or device.command_topic == topic:
                return device.sn
        for part in topic.split("/"):
            candidate = part.strip().upper()
            if len(candidate) == 8 and candidate.isalnum():
                return candidate
        return "663E8435"
