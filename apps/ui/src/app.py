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
import logging
from logging_setup import setup_logging
from pcm import PCMManager, CanInterface

root_logger = setup_logging()

logger = logging.getLogger("control_head.app")


APP_DIR = Path(__file__).resolve().parents[1]
QML_DIR = APP_DIR / "qml"


class QmlLogBridge(QObject):
    logAdded = Signal(str, str, str)  # level, origin, message (optional: for UI log view)

    @Slot(str, str, str)
    def log(self, level, origin, message):
        level = level.upper()

        # Map text level → logging fn
        logger = logging.getLogger("control_head")

        extra = {"origin": origin}
        if level == "DEBUG":
            logger.debug(message, extra=extra)
        elif level == "INFO":
            logger.info(message, extra=extra)
        elif level == "WARNING":
            logger.warning(message, extra=extra)
        elif level == "ERROR":
            logger.error(message, extra=extra)
        elif level == "CRITICAL":
            logger.critical(message, extra=extra)
        else:
            logger.info(message, extra=extra)

        # Also emit to QML if you want an on-screen log console
        self.logAdded.emit(level, origin, message)


class Bridge(QObject):
    # Send Pico button events to QML
    picoButton = Signal(str, bool)

    @Slot(str)
    def sendCommand(self, cmd: str) -> None:
        logger.info(f"Command from QML: {cmd}", extra={"origin": "app.Bridge.sendCommand"})

def make_engine() -> tuple[QQmlApplicationEngine, Bridge, SerialWorker]:
    logger.info("Setting up QML engine and Bridge", extra={"origin": "app.make_engine"})
    engine = QQmlApplicationEngine()

    bridge = Bridge()
    engine.rootContext().setContextProperty("Bridge", bridge)

    # Serial worker (listens to Pico over USB CDC)
    serial = SerialWorker(
        port=None,             # None => auto-detect first ttyACM/ttyUSB on Linux
        baud=115200,
    )
    logger.info("Starting SerialWorker thread", extra={"origin": "app.make_engine"})
    serial.start()  # starts its QThread

    # forward hardware events into QML
    serial.buttonEvent.connect(lambda name, pressed: bridge.picoButton.emit(name, pressed))

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        logger.critical("Failed to load QML root object", extra={"origin": "app.make_engine"})
        raise SystemExit("Failed to load QML")

    root = engine.rootObjects()[0]
    try:
        if platform.system() == "Linux":
            # Frameless and full screen on Linux
            logger.info("Setting up Linux window flags and fullscreen", extra={"origin": "app.make_engine"})
            root.setFlags(Qt.FramelessWindowHint | Qt.Window)
            root.showFullScreen()
        else:
            # Fixed 800x480 window on Windows (non-resizable)
            logger.info("Setting up Windows fixed size window", extra={"origin": "app.make_engine"})
            root.setFlags(Qt.Window)
            root.setMinimumSize(QSize(800, 480))
            root.setMaximumSize(QSize(800, 480))
            root.resize(800, 480)
            root.show()
    except Exception:
        logger.exception("Error setting up window", extra={"origin": "app.make_engine"})
        pass
    logger.info("QML engine and Bridge setup complete", extra={"origin": "app.make_engine"})
    return engine, bridge, serial


def main() -> None:
    logger.info("Starting Control Head UI application", extra={"origin": "app.main"})
    app = QGuiApplication(sys.argv)
    if platform.system() == "Linux":
        app.setOverrideCursor(Qt.BlankCursor)
    engine, _, _ = make_engine()
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # 👈 catch Ctrl-C
    log_bridge = QmlLogBridge()
    engine.rootContext().setContextProperty("LogBridge", log_bridge)

    # Example: create PCMManager and PCMDevice instances here
    logger.info("Creating PCMManager and PCMDevice instances", extra={"origin": "app.main"})
    pcm_manager = PCMManager(CanInterface)
    pcm_manager.add_pcm(node_id=1, name="Front PCM")
    pcm_manager.add_pcm(node_id=2, name="Rear PCM")
    logger.info("PCMManager and PCMDevice instances created and started", extra={"origin": "app.main"})

    app.aboutToQuit.connect(lambda: None)
    sys.exit(app.exec())
