#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avi RS-485 Controller (v11.0 - Single Control + Robust TX)
Changes:
1) Unified controls (no channel selection). Any I/F change is applied to BOTH channels.
2) Auto Poll (G) sends "G" every 3 seconds.
3) Manual "Get Status (G)" button added.
4) TX is rate-limited to max 1 command per second and sent from a background worker to prevent UI freezes/crashes.
5) COM Port list auto-refreshes periodically (and has a manual refresh button).
"""

import threading
import time
import queue
import json
from typing import Optional

# --- UI Library ---
import tkinter as tk
try:
    import customtkinter as ctk
except ImportError:
    print("Error: Library 'customtkinter' not found.")
    print("Please run: pip install customtkinter")
    raise

# --- Serial Library ---
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

# --- Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

START_CMD = 0x01
START_TLM = 0x05
END_BYTE  = 0x00
COMMA     = 0x2C
CONFIG_FILE = "config.json"
DEBUG_RS485 = False


# --- Helper Functions (Logic) ---
def to_bytes_sn(sn: str) -> bytes:
    s = sn.strip()
    hexchars = "0123456789abcdefABCDEF"
    if len(s) == 16 and all(c in hexchars for c in s):
        return bytes.fromhex(s.upper())
    if len(s) == 8:
        return s.encode("ascii", errors="strict")
    raise ValueError("SN must be 8 ASCII or 16 HEX")

def build_frame(sn_bytes: bytes, payload_ascii: str) -> bytes:
    return bytes([START_CMD]) + sn_bytes + bytes([COMMA]) + payload_ascii.encode("ascii") + bytes([END_BYTE])

def clean_ascii(s: str) -> str:
    return "".join(ch for ch in s if 32 <= ord(ch) <= 126)

def status_flags_to_text(st: int) -> str:
    flags = []
    if st & 1: flags.append("SHORT")
    if st & 2: flags.append("PWR-LIM")
    if st & 4: flags.append("NO-LOAD")
    return "OK" if not flags else " ".join(flags)


# --- Logic Class ---
class Link:
    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self.sn: Optional[bytes] = None
        self.lock = threading.Lock()
        self.tx_lock = threading.Lock()
        self.reader_stop = threading.Event()
        self.reader_th: Optional[threading.Thread] = None
        self.debug = DEBUG_RS485
        self.en_cb = None
        self.lora_mode = False
        self.post_tx_delay_s = 0.007
        self.inter_cmd_delay_s = 0.15
        self.last_tx_time = 0.0

        self.log_cb = None
        self.payload_cb = None

    @property
    def connected(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def connect(self, port: str, baud: int, sn: str, timeout_s: float):
        if serial is None:
            raise RuntimeError("pyserial missing")
        self.sn = to_bytes_sn(sn)
        self.ser = serial.Serial(port=port, baudrate=int(baud), timeout=float(timeout_s))
        self.reader_stop.clear()
        self.reader_th = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_th.start()

    def set_lora_mode(self, enabled: bool):
        self.lora_mode = bool(enabled)
        self.post_tx_delay_s = 0.03 if self.lora_mode else 0.007
        self.inter_cmd_delay_s = 0.5 if self.lora_mode else 0.15
        if self.ser:
            self.set_timeout(1.5 if self.lora_mode else 0.2)

    def set_en_callback(self, cb):
        self.en_cb = cb

    def enable_tx(self):
        if self.en_cb:
            try:
                self.en_cb(True)
            except Exception:
                pass
        if self.debug and self.log_cb:
            self.log_cb(f"{self._ts()} EN -> TX")

    def enable_rx(self):
        if self.en_cb:
            try:
                self.en_cb(False)
            except Exception:
                pass
        if self.debug and self.log_cb:
            self.log_cb(f"{self._ts()} EN -> RX")

    def is_busy(self) -> bool:
        return self.tx_lock.locked()

    def set_timeout(self, timeout_s: float):
        if self.ser:
            try:
                self.ser.timeout = float(timeout_s)
            except Exception:
                pass

    def close(self):
        self.reader_stop.set()
        if self.ser:
            try:
                self.ser.cancel_read()
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def send(self, payload_ascii: str) -> bool:
        """Low-level send (blocking). App-level code should call via App.enqueue_* to avoid UI blocking."""
        if not self.connected or not self.sn:
            return False
        frame = build_frame(self.sn, payload_ascii)
        try:
            with self.tx_lock:
                wait_s = self.inter_cmd_delay_s - (time.time() - self.last_tx_time)
                if wait_s > 0:
                    time.sleep(wait_s)

                self.enable_tx()
                with self.lock:
                    self.ser.write(frame)
                    self.ser.flush()
                time.sleep(self.post_tx_delay_s)
                self.enable_rx()
                self.last_tx_time = time.time()

            if self.log_cb:
                if self.debug:
                    self.log_cb(f"{self._ts()} TX > {payload_ascii}")
                else:
                    self.log_cb(f"TX > {payload_ascii}")
            return True
        except Exception as e:
            try:
                self.enable_rx()
            except Exception:
                pass
            if self.log_cb:
                self.log_cb(f"TX ERR: {e}")
            return False

    def send_seq(self, payloads, delay_ms=None):
        delay_s = self.inter_cmd_delay_s if delay_ms is None else (delay_ms / 1000.0)
        for i, pl in enumerate(payloads):
            if not self.send(pl):
                break
            if i < len(payloads) - 1:
                time.sleep(delay_s)

    def _reader_loop(self):
        state = "IDLE"
        sn_buf = bytearray()
        payload = bytearray()
        while not self.reader_stop.is_set():
            try:
                if not self.ser:
                    break
                b = self.ser.read(1)
                if not b:
                    continue
                x = b[0]

                if state == "IDLE":
                    if x == START_CMD:
                        state = "SN"
                        sn_buf.clear()
                        payload.clear()
                    elif x == START_TLM:
                        state = "TLM"
                        payload.clear()

                elif state == "SN":
                    sn_buf.append(x)
                    if len(sn_buf) == 8:
                        state = "COMMA"

                elif state == "COMMA":
                    state = "PAYLOAD" if x == COMMA else "DROP"

                elif state == "PAYLOAD":
                    if x == END_BYTE:
                        self._emit(payload, sn_buf)
                        state = "IDLE"
                        payload.clear()
                        sn_buf.clear()
                    else:
                        payload.append(x)

                elif state == "TLM":
                    if x == END_BYTE:
                        self._emit(payload, None)
                        state = "IDLE"
                        payload.clear()
                    else:
                        payload.append(x)

                elif state == "DROP":
                    if x == END_BYTE:
                        state = "IDLE"

            except Exception:
                break

    def _emit(self, payload, sn_buf):
        try:
            txt = payload.decode("ascii")
        except Exception:
            txt = ""
        txt = clean_ascii(txt)
        if not txt:
            return

        if self.debug and self.log_cb:
            self.log_cb(f"{self._ts()} RX < {txt}")

        # If it's a command response, verify SN
        if sn_buf and self.sn:
            if sn_buf != self.sn:
                return

        if self.payload_cb:
            self.payload_cb(txt)

    def _ts(self):
        return time.strftime("%H:%M:%S.") + f"{int((time.time() % 1)*1000):03d}"


# --- Single Device Card UI ---
class DeviceCard(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(self, text="DEVICE CONTROL", font=ctk.CTkFont(size=14, weight="bold"))
        title.grid(row=0, column=0, columnspan=3, pady=10, padx=10, sticky="w")

        # Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10)

        ctk.CTkLabel(ctrl_frame, text="Set Current:").grid(row=0, column=0, sticky="w")
        self.entry_i = ctk.CTkEntry(ctrl_frame, width=100, placeholder_text="A")
        self.entry_i.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.entry_i.insert(0, f"{self.app.app_state['i_desired']:.3f}")
        btn_i = ctk.CTkButton(ctrl_frame, text="Apply I", width=90, command=self.apply_i)
        btn_i.grid(row=0, column=2, padx=5)

        ctk.CTkLabel(ctrl_frame, text="Set Freq:").grid(row=1, column=0, sticky="w")
        self.entry_f = ctk.CTkEntry(ctrl_frame, width=100, placeholder_text="kHz")
        self.entry_f.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.entry_f.insert(0, f"{self.app.app_state['f_desired_khz']:.1f}")
        btn_f = ctk.CTkButton(ctrl_frame, text="Apply F", width=90, command=self.apply_f)
        btn_f.grid(row=1, column=2, padx=5)

        # Output enable (both channels)
        self.sw_enable = ctk.CTkSwitch(ctrl_frame, text="Output Enable", command=self._toggle_enable)
        self.sw_enable.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # Live Data
        self.data_frame = ctk.CTkFrame(self, fg_color=("#cfcfcf", "#2b2b2b"))
        self.data_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=15)
        self.data_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(self.data_frame, text="VOLTAGE", font=("Arial", 10)).grid(row=0, column=0, pady=(10, 0))
        self.lbl_v = ctk.CTkLabel(self.data_frame, text="-- V", font=("Arial", 24, "bold"))
        self.lbl_v.grid(row=1, column=0, pady=(0, 10))

        ctk.CTkLabel(self.data_frame, text="ACTUAL CURRENT", font=("Arial", 10)).grid(row=0, column=1, pady=(10, 0))
        self.lbl_i = ctk.CTkLabel(self.data_frame, text="-- A", font=("Arial", 24, "bold"))
        self.lbl_i.grid(row=1, column=1, pady=(0, 10))

        self.lbl_info = ctk.CTkLabel(self, text="Freq: -- kHz  |  Status: --", font=("Consolas", 12))
        self.lbl_info.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.lbl_batt = ctk.CTkLabel(self, text="Batt: -- V", font=("Consolas", 12, "bold"), text_color="#1f77b4")
        self.lbl_batt.grid(row=3, column=2, pady=10, padx=(0,10), sticky="e")

    def _toggle_enable(self):
        # Apply to BOTH channels
        en = 1 if self.sw_enable.get() else 0
        self.app.enqueue_seq([f"S,S,1,{en}", f"S,S,2,{en}", "G"])

    def apply_i(self):
        try:
            val = float(self.entry_i.get())
            self.app.app_state["i_desired"] = val
            self.app.enqueue_seq([f"S,I,1,{val:.3f}", f"S,I,2,{val:.3f}", "G"])
        except Exception:
            self.flash_error(self.entry_i)

    def apply_f(self):
        try:
            val = round(float(self.entry_f.get()), 1)
            self.entry_f.delete(0, "end")
            self.entry_f.insert(0, str(val))
            self.app.app_state["f_desired_khz"] = val

            cmds = []
            if self.app.switch_pre_off.get():
                cmds += ["S,S,1,0", "S,S,2,0"]
            cmds += [f"S,F,1,{val:.1f}", f"S,F,2,{val:.1f}", "G"]
            self.app.enqueue_seq(cmds)
        except Exception:
            self.flash_error(self.entry_f)

    def flash_error(self, entry):
        orig = entry.cget("text_color")
        entry.configure(text_color="red")
        self.after(500, lambda: entry.configure(text_color=orig))

    def update_data(self, kv):
        if "V" in kv:
            self.lbl_v.configure(text=f"{kv['V']:.1f} V")
        if "I" in kv:
            self.lbl_i.configure(text=f"{kv['I']:.2f} A")
            
        self.lbl_batt.configure(text=f"Batt: {kv['V']:.1f} V")

        f_txt = f"{kv['F']/1000:.1f} kHz" if "F" in kv and kv["F"] != -1 else "--"
        s_txt = status_flags_to_text(kv["STATUS"]) if "STATUS" in kv else "--"
        self.lbl_info.configure(text=f"Freq: {f_txt}  |  Status: {s_txt}")

        if "STATUS" in kv and kv["STATUS"] != 0:
            self.lbl_info.configure(text_color="#ffcc00")
        else:
            self.lbl_info.configure(text_color="gray70")


# --- Main App ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Avi RS-485 Controller Pro")
        self.geometry("1050x700")

        self.gui_queue = queue.Queue()

        # TX worker (prevents UI blocking and rate-limits to 1 cmd/sec)
        self.tx_queue = queue.Queue()
        self.tx_stop = threading.Event()
        self.tx_min_interval_s = 1.0
        self._tx_last_monotonic = 0.0
        self.tx_th = threading.Thread(target=self._tx_worker, daemon=True)
        self.tx_th.start()

        self.link = Link()
        self.link.log_cb = lambda m: self.gui_queue.put(("LOG", m))
        self.link.payload_cb = self._parse_worker

        self.app_state = {"i_desired": 1.0, "f_desired_khz": 1.0}
        self.config = self.load_config()

        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(self.sidebar, text="CONNECTION", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(20, 10)
        )

        ports = self.get_ports()
        self.cb_port = ctk.CTkComboBox(self.sidebar, values=ports, width=170)
        self.cb_port.grid(row=1, column=0, padx=20, pady=(10, 5))
        self.cb_port.set(self.config.get("port", ""))

        self.btn_refresh_ports = ctk.CTkButton(self.sidebar, text="Refresh Ports", command=self.refresh_ports, width=170)
        self.btn_refresh_ports.grid(row=2, column=0, padx=20, pady=(0, 10))

        self.entry_baud = ctk.CTkEntry(self.sidebar, width=170, placeholder_text="Baud")
        self.entry_baud.grid(row=3, column=0, padx=20, pady=10)
        self.entry_baud.insert(0, str(self.config.get("baud", 115200)))

        self.entry_sn = ctk.CTkEntry(self.sidebar, width=170, placeholder_text="SN")
        self.entry_sn.grid(row=4, column=0, padx=20, pady=10)
        self.entry_sn.insert(0, self.config.get("sn", "663E8435"))

        self.btn_connect = ctk.CTkButton(self.sidebar, text="CONNECT", fg_color="green", command=self.toggle_connect)
        self.btn_connect.grid(row=5, column=0, padx=20, pady=20)

        ctk.CTkLabel(self.sidebar, text="SETTINGS", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=6, column=0, padx=20, pady=(10, 10)
        )

        self.switch_lora = ctk.CTkSwitch(self.sidebar, text="LoRa Timeout")
        self.switch_lora.select()
        self.switch_lora.grid(row=7, column=0, padx=20, pady=10, sticky="w")

        self.switch_auto = ctk.CTkSwitch(self.sidebar, text="Auto Poll (G) - 3s")
        self.switch_auto.select()
        self.switch_auto.grid(row=8, column=0, padx=20, pady=10, sticky="w")

        self.switch_pre_off = ctk.CTkSwitch(self.sidebar, text="Safe Freq (Pre-Off)")
        self.switch_pre_off.grid(row=9, column=0, padx=20, pady=10, sticky="w")

        self.btn_g = ctk.CTkButton(self.sidebar, text="Get Status (G)", command=lambda: self.enqueue_cmd("G"), width=170)
        self.btn_g.grid(row=10, column=0, padx=20, pady=(15, 10))

        # --- Main Area ---
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        self.device_card = DeviceCard(self.main_area, self)
        self.device_card.grid(row=0, column=0, sticky="nsew")

        # --- Log Area ---
        self.log_box = ctk.CTkTextbox(self, height=160, font=("Consolas", 12))
        self.log_box.grid(row=1, column=1, sticky="nsew", padx=20, pady=(0, 20))
        self.log_box.insert("0.0", "--- SYSTEM READY ---\n")

        # loops
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.process_queue)
        self.after(5000, self.auto_poll_loop)      # (G) every 3 seconds
        self.after(2000, self.ports_refresh_loop)  # refresh ports periodically

    # --- TX enqueue API (thread-safe, non-blocking UI) ---
    def enqueue_cmd(self, cmd: str):
        self.tx_queue.put(("CMD", cmd))

    def enqueue_seq(self, cmds):
        self.tx_queue.put(("SEQ", list(cmds)))

    def _tx_worker(self):
        while not self.tx_stop.is_set():
            try:
                kind, payload = self.tx_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self.tx_stop.is_set():
                break

            if not self.link.connected:
                # drain quietly but inform user once per item
                self.gui_queue.put(("LOG", "Not connected (TX skipped)"))
                continue

            # Rate-limit: max 1 command per second (global)
            def rate_wait():
                now = time.monotonic()
                dt = now - self._tx_last_monotonic
                if dt < self.tx_min_interval_s:
                    time.sleep(self.tx_min_interval_s - dt)
                self._tx_last_monotonic = time.monotonic()

            try:
                if kind == "CMD":
                    rate_wait()
                    self.link.send(payload)
                elif kind == "SEQ":
                    for i, cmd in enumerate(payload):
                        rate_wait()
                        ok = self.link.send(cmd)
                        if not ok:
                            break
                else:
                    self.gui_queue.put(("LOG", f"TX worker: unknown item {kind}"))
            except Exception as e:
                self.gui_queue.put(("LOG", f"TX worker error: {e}"))

    # --- Actions ---
    def toggle_connect(self):
        if not self.link.connected:
            try:
                p = self.cb_port.get()
                b = self.entry_baud.get()
                s = self.entry_sn.get()
                t = 1.5 if self.switch_lora.get() else 0.2
                self.link.set_lora_mode(self.switch_lora.get())
                self.link.connect(p, b, s, t)
                self.btn_connect.configure(text="DISCONNECT", fg_color="red")
                self.gui_queue.put(("LOG", f"Connected to {p}"))
                self.save_config()
            except Exception as e:
                self.gui_queue.put(("LOG", f"Error: {e}"))
        else:
            self.link.close()
            self.btn_connect.configure(text="CONNECT", fg_color="green")
            self.gui_queue.put(("LOG", "Disconnected"))

    # --- Loops ---
    def auto_poll_loop(self):
        if self.switch_auto.get() and self.link.connected:
            # "G" status every 3 seconds
            if not self.link.is_busy():
                self.enqueue_cmd("G")
        self.after(5000, self.auto_poll_loop)

    def refresh_ports(self):
        ports = self.get_ports()
        cur = self.cb_port.get()
        self.cb_port.configure(values=ports)
        if cur in ports:
            self.cb_port.set(cur)
        self.gui_queue.put(("LOG", f"Ports refreshed ({len(ports)})"))

    def ports_refresh_loop(self):
        # Auto refresh (silent)
        try:
            ports = self.get_ports()
            cur_values = list(self.cb_port.cget("values")) if hasattr(self.cb_port, "cget") else []
            if ports != cur_values:
                cur = self.cb_port.get()
                self.cb_port.configure(values=ports)
                if cur in ports:
                    self.cb_port.set(cur)
        except Exception:
            pass
        self.after(2000, self.ports_refresh_loop)

    # --- Processing ---
    def process_queue(self):
        try:
            while True:
                kind, data = self.gui_queue.get_nowait()
                if kind == "LOG":
                    self.log_box.insert("end", f"{data}\n")
                    self.log_box.see("end")
                elif kind == "UPDATE":
                    kv = data
                    self.device_card.update_data(kv)
        except queue.Empty:
            pass
        finally:
            self.after(50, self.process_queue)

    def _parse_worker(self, txt):
        # Expected payload: "<ch>,<I>,<V>,<F>,<STATUS>" where ch can be 0/1/2
        try:
            txt = clean_ascii(txt).strip()
            if not self.link.debug:
                self.gui_queue.put(("LOG", f"RX < {txt}"))

            parts = [p.strip() for p in txt.split(",")]
            if len(parts) >= 2:
                # ch = int(float(parts[0]))  # not needed for UI anymore
                kv = {}
                if len(parts) >= 2: kv["I"] = float(parts[1])
                if len(parts) >= 3: kv["V"] = float(parts[2])
                if len(parts) >= 4: kv["F"] = float(parts[3])
                if len(parts) >= 5: kv["STATUS"] = int(float(parts[4]))
                self.gui_queue.put(("UPDATE", kv))
        except Exception:
            pass

    # --- Config & Utils ---
    def get_ports(self):
        return [p.device for p in list_ports.comports()] if list_ports else []

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self):
        cfg = {"port": self.cb_port.get(), "baud": self.entry_baud.get(), "sn": self.entry_sn.get()}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
        except Exception:
            pass

    def on_close(self):
        self.save_config()
        self.tx_stop.set()
        try:
            while not self.tx_queue.empty():
                self.tx_queue.get_nowait()
        except Exception:
            pass
        self.link.close()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
