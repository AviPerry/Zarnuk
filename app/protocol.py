from __future__ import annotations

import re

from .config import START_CMD, TERMINATOR

SN_PATTERN = re.compile(r"^[A-Z0-9]{8}$")


def normalize_sn(sn: str) -> str:
    return sn.strip().upper()


def validate_sn(sn: str) -> str:
    normalized = normalize_sn(sn)
    if not SN_PATTERN.fullmatch(normalized):
        raise ValueError("SN must be exactly 8 uppercase alphanumeric characters")
    return normalized


def build_command_frame(sn: str, command: str) -> bytes:
    normalized = validate_sn(sn)
    return bytes([START_CMD]) + normalized.encode("ascii") + b"," + command.encode("ascii") + TERMINATOR


def frame_to_hex(frame: bytes) -> str:
    return frame.hex(" ").upper()
