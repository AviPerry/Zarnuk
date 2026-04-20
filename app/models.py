from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .protocol import normalize_sn, validate_sn


class AlertName(str, Enum):
    SHORT = "SHORT"
    PWR_LIM = "PWR-LIM"
    NO_LOAD = "NO-LOAD"
    LOW_BAT = "LOW-BAT"


class DeviceTelemetry(BaseModel):
    vin: float = 12.8
    v1: float = 0.0
    ir: float = 0.0
    frequency: float = 0.0
    resistance: float = 0.0
    power: float = 0.0
    battery_voltage: float = 12.8
    healthy: bool = True
    alerts: list[AlertName] = Field(default_factory=list)
    output_enabled: bool = False
    target_current: float = 0.0
    target_frequency: float = 50.0


class DeviceState(BaseModel):
    sn: str
    name: str = ""
    command_topic: str = ""
    telemetry_topic: str = ""
    online: bool = False
    telemetry: DeviceTelemetry = Field(default_factory=DeviceTelemetry)
    last_seen_epoch: float = 0.0
    last_command_hex: Optional[str] = None

    @field_validator("sn")
    @classmethod
    def validate_device_sn(cls, value: str) -> str:
        validate_sn(value)
        return normalize_sn(value)


class CommandRequest(BaseModel):
    command: str


class CreateDeviceRequest(BaseModel):
    sn: str
    name: str = ""
    command_topic: str
    telemetry_topic: str

    @field_validator("sn")
    @classmethod
    def validate_new_device_sn(cls, value: str) -> str:
        validate_sn(value)
        return normalize_sn(value)

    @field_validator("command_topic", "telemetry_topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Topic is required")
        return cleaned

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.strip()


class UpdateDeviceRequest(BaseModel):
    name: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.strip()


class ControlUpdateRequest(BaseModel):
    current: Optional[float] = None
    frequency: Optional[float] = None


class DeviceListResponse(BaseModel):
    devices: list[DeviceState]


class EventEnvelope(BaseModel):
    type: str
    payload: dict[str, Any]
