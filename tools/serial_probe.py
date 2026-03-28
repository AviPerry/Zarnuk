from __future__ import annotations

import argparse
import sys
import time

import serial


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serial probe for the USR-G771-E modem line")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--bytesize", type=int, default=8)
    parser.add_argument("--stopbits", type=float, default=1)
    parser.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"])
    parser.add_argument("--timeout", type=float, default=0.2)
    parser.add_argument("--read-seconds", type=float, default=3.0)
    parser.add_argument("--send-ascii")
    parser.add_argument("--send-hex")
    parser.add_argument("--append-crlf", action="store_true")
    parser.add_argument("--enter-cmd-mode", action="store_true")
    return parser


def open_port(args: argparse.Namespace) -> serial.Serial:
    return serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
    )


def to_payload(args: argparse.Namespace) -> bytes | None:
    if args.send_ascii is not None:
        payload = args.send_ascii.encode("ascii")
        if args.append_crlf:
            payload += b"\r\n"
        return payload
    if args.send_hex is not None:
        return bytes.fromhex(args.send_hex)
    return None


def read_for(ser: serial.Serial, seconds: float) -> bytes:
    deadline = time.time() + seconds
    received = bytearray()
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            received.extend(chunk)
            print(f"RX chunk: {chunk.hex(' ').upper()}")
    return bytes(received)


def enter_command_mode(ser: serial.Serial) -> bool:
    print("Entering modem command mode with +++ / a handshake")
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    ser.write(b"+++")
    ser.flush()
    print("TX (3 bytes): 2B 2B 2B")
    first = read_for(ser, 1.5)
    if not first:
        print("No response after +++")
        return False

    ser.write(b"a")
    ser.flush()
    print("TX (1 byte): 61")
    second = read_for(ser, 1.5)
    combined = first + second
    print("Handshake total hex:", combined.hex(" ").upper())
    print("Handshake ascii:", combined.decode("ascii", errors="replace"))
    return b"+ok" in combined.lower()


def main() -> int:
    args = build_parser().parse_args()
    payload = to_payload(args)

    print(f"Opening {args.port} @ {args.baud} {args.bytesize}{args.parity}{args.stopbits}")
    with open_port(args) as ser:
        if args.enter_cmd_mode:
            success = enter_command_mode(ser)
            print("Command mode:", "OK" if success else "FAILED")

        ser.reset_input_buffer()
        ser.reset_output_buffer()

        if payload:
            ser.write(payload)
            ser.flush()
            print(f"TX ({len(payload)} bytes): {payload.hex(' ').upper()}")

        received = bytearray(read_for(ser, args.read_seconds))

        if received:
            print("RX total hex:", received.hex(" ").upper())
            try:
                print("RX ascii:", received.decode("ascii", errors="replace"))
            except Exception:
                pass
        else:
            print("No data received.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
