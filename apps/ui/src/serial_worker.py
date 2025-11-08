from __future__ import annotations
import sys
import glob
import threading
import time
import serial  # pyserial
from PySide6.QtCore import QObject, Signal, QThread


def _default_port() -> str | None:
    # Linux (Pi): /dev/ttyACM* for Pico CDC (TinyUSB), sometimes ttyUSB*
    candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    return candidates[0] if candidates else None


class _Reader(QObject):
    lineRead = Signal(str)

    def __init__(self, ser: serial.Serial):
        super().__init__()
        self._ser = ser
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        buf = bytearray()
        while not self._stop:
            try:
                b = self._ser.read(1)
                if not b:
                    continue
                if b == b"\n":
                    try:
                        self.lineRead.emit(buf.decode(errors="ignore").strip())
                    finally:
                        buf.clear()
                else:
                    buf.extend(b)
            except Exception:
                time.sleep(0.1)


class SerialWorker(QObject):
    buttonEvent = Signal(str, bool)  # (name, pressed)

    def __init__(self, port: str | None, baud: int = 115200):
        super().__init__()
        self._port = port or _default_port()
        if not self._port:
            print("[SerialWorker] No serial device found. Plug in the Pico.")
        self._baud = baud
        self._thread = QThread()
        self._reader: _Reader | None = None

    def start(self):
        if not self._port:
            return
        try:
            ser = serial.Serial(self._port, self._baud, timeout=0.1)
        except Exception as e:
            print(f"[SerialWorker] Failed to open {self._port}: {e}")
            return
        self._reader = _Reader(ser)
        self._reader.moveToThread(self._thread)
        self._thread.started.connect(self._reader.run)
        self._reader.lineRead.connect(self._on_line)
        self._thread.start()

    def stop(self):
        if self._reader:
            self._reader.stop()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)

    def _on_line(self, line: str):
        # Expect lines like: BTN GP9 DOWN  or BTN GP9 UP
        parts = line.split(",")
        if len(parts) >= 3 and parts[0] == "BTN":
            name, state = parts[1], parts[2]
            print(f"[SerialWorker] Button {name} is {state}")
            self.buttonEvent.emit(name, state.upper() == "DOWN")
        else:
            print(f"[SerialWorker] RX: {line}")
