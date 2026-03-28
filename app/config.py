from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

START_CMD = 0x01
START_TLM = 0x05
SEPARATOR = b","
TERMINATOR = b"\x00"

LOW_BAT_THRESHOLD = 11.2
DEFAULT_POLL_SECONDS = 5
ONLINE_TIMEOUT_SECONDS = 15

MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
MQTT_HOST = os.getenv("MQTT_HOST", "8ff996d961eb4122ab06d0f84b2f5de6.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_WEBSOCKET_PORT = int(os.getenv("MQTT_WEBSOCKET_PORT", "8884"))
MQTT_TLS = os.getenv("MQTT_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "stm32-control-center")
MQTT_COMMAND_TOPIC = os.getenv("MQTT_COMMAND_TOPIC", "stm32/command")
MQTT_TELEMETRY_TOPIC = os.getenv("MQTT_TELEMETRY_TOPIC", "stm32/telemetry")
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "Admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Admin123")
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "mashder_session")
AUTH_COOKIE_VALUE = os.getenv("AUTH_COOKIE_VALUE", "authenticated-admin-session")
