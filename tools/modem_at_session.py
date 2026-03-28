from __future__ import annotations

import argparse
import sys
import time
from typing import Iterable

import serial


def enter_command_mode(ser: serial.Serial) -> bool:
    time.sleep(1.2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(b"+++")
    ser.flush()
    first = read_until_quiet(ser, quiet_seconds=0.4, max_seconds=2.0)
    ser.write(b"a")
    ser.flush()
    second = read_until_quiet(ser, quiet_seconds=0.4, max_seconds=2.0)
    combined = (first + second).decode("ascii", errors="replace")
    print("> +++ / a")
    print(combined or "<no response>")
    return "+ok" in combined.lower()


def read_until_quiet(ser: serial.Serial, quiet_seconds: float = 0.6, max_seconds: float = 8.0) -> bytes:
    start = time.time()
    last_data = start
    buf = bytearray()
    while time.time() - start < max_seconds:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf.extend(chunk)
            last_data = time.time()
        elif time.time() - last_data >= quiet_seconds:
            break
    return bytes(buf)


def send_cmd(ser: serial.Serial, cmd: str, wait: float = 0.1, max_seconds: float = 8.0) -> str:
    payload = (cmd + "\r\n").encode("ascii")
    ser.reset_input_buffer()
    ser.write(payload)
    ser.flush()
    time.sleep(wait)
    raw = read_until_quiet(ser, max_seconds=max_seconds)
    text = raw.decode("ascii", errors="replace")
    print(f"> {cmd}")
    print(text or "<no response>")
    return text


def run_session(port: str, commands: Iterable[str], baud: int = 115200) -> int:
    with serial.Serial(port=port, baudrate=baud, bytesize=8, parity="N", stopbits=1, timeout=0.2) as ser:
        if not enter_command_mode(ser):
            print("Failed to enter AT command mode")
            return 1
        for cmd in commands:
            send_cmd(ser, cmd, max_seconds=15.0 if "AT+S" == cmd else 8.0)
            time.sleep(0.2)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("commands", nargs="+")
    args = parser.parse_args()
    return run_session(args.port, args.commands, args.baud)


if __name__ == "__main__":
    sys.exit(main())
