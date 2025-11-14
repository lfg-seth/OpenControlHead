from __future__ import annotations
import sys
import glob
import threading
import time
import serial  # pyserial
from PySide6.QtCore import QObject, Signal, QThread
import re
import logging

logger = logging.getLogger("control_head.serial_worker")
logger.info("SerialWorker module loaded", extra={"origin": "serial_worker.module"})

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
            logger.warning("No serial device found. Plug in the Pico.", extra={"origin": "serial_worker.__init__"})
        self._baud = baud
        self._thread = QThread()
        self._reader: _Reader | None = None

    def start(self):
        if not self._port:
            return
        try:
            ser = serial.Serial(self._port, self._baud, timeout=0.1)
            logger.info(f"Opened serial port {self._port} at {self._baud} baud", extra={"origin": "serial_worker.start"})
        except Exception as e:
            logger.error(f"Failed to open {self._port}: {e}", extra={"origin": "serial_worker.start"})
            return
        self._reader = _Reader(ser)
        self._reader.moveToThread(self._thread)
        self._thread.started.connect(self._reader.run)
        self._reader.lineRead.connect(self._on_line)
        self._thread.start()

    def stop(self):
        logger.info("Stopping SerialWorker", extra={"origin": "serial_worker.stop"})
        if self._reader:
            self._reader.stop()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)


    def _on_line(self, line: str):
        line = line.strip()

        # Match:
        #   1. state: PRESS or RELEASE
        #   2. name: anything (including spaces) up to the first key=value pair
        #      or end of line
        #   3. optional trailing " key=value" fields
        m = re.match(r'^(PRESS|RELEASE)\s+(.+?)(?:\s+\w+=\S+)*\s*$', line)
        if m:
            state = m.group(1)
            name = m.group(2)
            pressed = (state == "PRESS")
            logger.info(
                f"Button {name} is {state}",
                extra={"origin": "serial_worker._on_line"}
            )
            self.buttonEvent.emit(name, pressed)
            return

        # Fallback / unhandled lines
        logger.info(
            f"RX (unhandled): {line}",
            extra={"origin": "serial_worker._on_line"}
        )
