# src/app.py
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtCore import QUrl, QObject, Slot, Signal, Qt, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from .serial_worker import SerialWorker
import signal
import platform
import resources_rc  # this line makes the qrc resources available


APP_DIR = Path(__file__).resolve().parents[1]
QML_DIR = APP_DIR / "qml"



class Bridge(QObject):
    # Send Pico button events to QML
    picoButton = Signal(str, bool)

    @Slot(str)
    def sendCommand(self, cmd: str) -> None:
        print(f"QML requested command: {cmd}")

def make_engine() -> tuple[QQmlApplicationEngine, Bridge, SerialWorker]:
    engine = QQmlApplicationEngine()

    bridge = Bridge()
    engine.rootContext().setContextProperty("Bridge", bridge)

    # Serial worker (listens to Pico over USB CDC)
    serial = SerialWorker(
        port=None,             # None => auto-detect first ttyACM/ttyUSB on Linux
        baud=115200,
    )
    serial.start()  # starts its QThread

    # forward hardware events into QML
    serial.buttonEvent.connect(lambda name, pressed: bridge.picoButton.emit(name, pressed))

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        raise SystemExit("Failed to load QML")

    root = engine.rootObjects()[0]
    try:
        if platform.system() == "Linux":
            # Frameless and full screen on Linux
            root.setFlags(Qt.FramelessWindowHint | Qt.Window)
            root.showFullScreen()
        else:
            # Fixed 800x480 window on Windows (non-resizable)
            root.setFlags(Qt.Window)
            root.setMinimumSize(QSize(800, 480))
            root.setMaximumSize(QSize(800, 480))
            root.resize(800, 480)
            root.show()
    except Exception:
        pass
    return engine, bridge, serial


def main() -> None:
    app = QGuiApplication(sys.argv)
    if platform.system() == "Linux":
        app.setOverrideCursor(Qt.BlankCursor)
    engine, _, _ = make_engine()
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # 👈 catch Ctrl-C
    # Keep Python refs alive
    app.aboutToQuit.connect(lambda: None)
    sys.exit(app.exec())
