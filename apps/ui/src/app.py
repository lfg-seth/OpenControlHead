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
from switches import SwitchManager, ChannelBinding
from pcm import PCMManager, CanInterface


root_logger = setup_logging()
logger = logging.getLogger("control_head.app")

APP_DIR = Path(__file__).resolve().parents[1]
QML_DIR = APP_DIR / "qml"

# --- hardware / logical layer ---
pcm = PCMManager(CanInterface)
pcm.add_pcm(node_id=1)
pcm.add_pcm(node_id=2)

switches = SwitchManager(pcm)

front_switch = switches.register_switch(
    name="Front Lights",
    bindings=[
        ChannelBinding(node_id=1, channel_index=0, label="Left Grille LED"),
        ChannelBinding(node_id=1, channel_index=1, label="Right Grille LED"),
        ChannelBinding(node_id=2, channel_index=0, label="Bumper Lightbar"),
    ],
)

horn = switches.register_switch(
    name="Horn",
    bindings=[
        ChannelBinding(node_id=1, channel_index=2, label="Horn"),
    ],
)


class QmlLogBridge(QObject):
    logAdded = Signal(str, str, str)  # level, origin, message

    @Slot(str, str, str)
    def log(self, level, origin, message):
        level = level.upper()
        logger_ = logging.getLogger("control_head")
        extra = {"origin": origin}

        if level == "DEBUG":
            logger_.debug(message, extra=extra)
        elif level == "INFO":
            logger_.info(message, extra=extra)
        elif level == "WARNING":
            logger_.warning(message, extra=extra)
        elif level == "ERROR":
            logger_.error(message, extra=extra)
        elif level == "CRITICAL":
            logger_.critical(message, extra=extra)
        else:
            logger_.info(message, extra=extra)

        self.logAdded.emit(level, origin, message)


class Bridge(QObject):
    """
    Glue between:
      - QML (UI)
      - SerialWorker (physical buttons)
      - SwitchManager (logical switches -> PCM channels)
    """

    # Emitted so QML can react to physical button events if desired
    picoButton = Signal(str, bool)

    def __init__(self, switches: SwitchManager, parent=None):
        super().__init__(parent)
        self._switches = switches

        # Map physical button IDs from SerialWorker -> logical switch names
        # TODO: adjust to match actual names coming from your Pico/ESP
        self._button_map = {
            "BTN_1": "Front Lights",
            "BTN_2": "Horn",
            # "BTN_3": "Some Other Switch",
        }

    # ---------- QML → Logic ----------

    @Slot(str, bool)
    def setSwitchState(self, name: str, on: bool) -> None:
        logger.info(
            f"QML setSwitchState: {name} -> {on}",
            extra={"origin": "app.Bridge.setSwitchState"},
        )
        sw = self._switches.get_switch(name) if hasattr(self._switches, "get_switch") else None
        if sw is None:
            logger.warning(
                f"Unknown switch '{name}'",
                extra={"origin": "app.Bridge.setSwitchState"},
            )
            return

        if on:
            sw.on()
        else:
            sw.off()

    @Slot(str)
    def toggleSwitch(self, name: str) -> None:
        logger.info(
            f"QML toggleSwitch: {name}",
            extra={"origin": "app.Bridge.toggleSwitch"},
        )
        sw = self._switches.get_switch(name) if hasattr(self._switches, "get_switch") else None
        if sw is None:
            logger.warning(
                f"Unknown switch '{name}'",
                extra={"origin": "app.Bridge.toggleSwitch"},
            )
            return

        if hasattr(sw, "toggle"):
            sw.toggle()
        else:
            try:
                # assumes sw.is_on exists
                sw.off() if sw.is_on else sw.on()
            except AttributeError:
                logger.error(
                    f"Switch '{name}' has no toggle/is_on; implement as needed",
                    extra={"origin": "app.Bridge.toggleSwitch"},
                )

    # ---------- Serial → Logic (+QML) ----------

    @Slot(str, bool)
    def handlePicoButton(self, button_name: str, pressed: bool) -> None:
        """
        Called when SerialWorker reports a hardware button event.
        """
        logger.info(
            f"Pico button event: {button_name} -> {pressed}",
            extra={"origin": "app.Bridge.handlePicoButton"},
        )

        # Re-emit to QML if UI wants to listen
        self.picoButton.emit(button_name, pressed)

        logical_name = self._button_map.get(button_name)
        if logical_name is None:
            logger.warning(
                f"Unmapped button '{button_name}'",
                extra={"origin": "app.Bridge.handlePicoButton"},
            )
            return

        # Behavior choice:
        # - On press: toggle logical switch
        # - On release: ignore   (or implement momentary behavior if you prefer)
        if pressed:
            self.toggleSwitch(logical_name)


def make_engine(switches: SwitchManager) -> tuple[QQmlApplicationEngine, Bridge, SerialWorker]:
    logger.info("Setting up QML engine and Bridge", extra={"origin": "app.make_engine"})
    engine = QQmlApplicationEngine()

    bridge = Bridge(switches)
    engine.rootContext().setContextProperty("Bridge", bridge)

    serial = SerialWorker(
        port=None,
        baud=115200,
    )

    logger.info("Starting SerialWorker thread", extra={"origin": "app.make_engine"})
    serial.start()

    # Wire SerialWorker -> Bridge
    # expects SerialWorker.buttonEvent: Signal(str button_name, bool pressed)
    serial.buttonEvent.connect(bridge.handlePicoButton)

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        logger.critical("Failed to load QML root object", extra={"origin": "app.make_engine"})
        raise SystemExit("Failed to load QML")

    root = engine.rootObjects()[0]
    try:
        if platform.system() == "Linux":
            logger.info(
                "Setting up Linux window flags and fullscreen",
                extra={"origin": "app.make_engine"},
            )
            root.setFlags(Qt.FramelessWindowHint | Qt.Window)
            root.showFullScreen()
        else:
            logger.info(
                "Setting up Windows fixed size window",
                extra={"origin": "app.make_engine"},
            )
            root.setFlags(Qt.Window)
            root.setMinimumSize(QSize(800, 480))
            root.setMaximumSize(QSize(800, 480))
            root.resize(800, 480)
            root.show()
    except Exception:
        logger.exception("Error setting up window", extra={"origin": "app.make_engine"})

    logger.info("QML engine and Bridge setup complete", extra={"origin": "app.make_engine"})
    return engine, bridge, serial


def main() -> None:
    logger.info("Starting Control Head UI application", extra={"origin": "app.main"})
    app = QGuiApplication(sys.argv)

    if platform.system() == "Linux":
        app.setOverrideCursor(Qt.BlankCursor)

    engine, bridge, serial = make_engine(switches)

    # Log bridge for QML log view
    log_bridge = QmlLogBridge()
    engine.rootContext().setContextProperty("LogBridge", log_bridge)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.aboutToQuit.connect(lambda: None)
    sys.exit(app.exec())
