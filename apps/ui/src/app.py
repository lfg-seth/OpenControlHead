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
from switches import SwitchManager, ChannelBinding, SwitchType
from pcm import PCMManager, CanInterface


root_logger = setup_logging()
logger = logging.getLogger("control_head.app")

APP_DIR = Path(__file__).resolve().parents[1]
QML_DIR = APP_DIR / "qml"

# --- hardware / logical layer ---
pcm_mgr = PCMManager(CanInterface)
front_pcm = pcm_mgr.add_pcm(node_id=1, name="Front PCM")
rear_pcm  = pcm_mgr.add_pcm(node_id=2, name="Rear PCM")

# Define channels by what they actually go to
front_light_left  = front_pcm.init_channel(0, label="Front Light Left")
front_light_right = front_pcm.init_channel(1, label="Front Light Right")
grill_light       = front_pcm.init_channel(2, label="Grill Light")

switches = SwitchManager(pcm_mgr)

front_lights = switches.register_switch(
    name="Front Lights",
    type=SwitchType.CYCLE,
    bindings=[
        front_light_left,
        front_light_right,
        grill_light,
    ],
    cycles=[
        [],  # all OFF
        [front_light_left],
        [front_light_left, front_light_right],
        [front_light_left, front_light_right, grill_light],
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
            "LIGHT": "Front Lights",
            "HORN": "Horn",
            # "BTN_3": "Some Other Switch",
        }

    # ---------- internals ----------

    def _get_switch(self, name: str):
        sw = self._switches.get_switch(name) if hasattr(self._switches, "get_switch") else None
        if sw is None:
            logger.warning(
                f"Unknown switch '{name}'",
                extra={"origin": "app.Bridge._get_switch"},
            )
        return sw

    # ---------- QML → Logic ----------

    @Slot(str, bool)
    def setSwitchState(self, name: str, on: bool) -> None:
        logger.info(
            f"QML setSwitchState: {name} -> {on}",
            extra={"origin": "app.Bridge.setSwitchState"},
        )
        sw = self._get_switch(name)
        if sw is None:
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
        sw = self._get_switch(name)
        if sw is None:
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

    @Slot(str)
    def pressSwitch(self, name: str) -> None:
        """
        For QML: call when a virtual button is pressed.
        Delegates to LogicalSwitch.press() if available, else falls back to toggle.
        """
        logger.info(
            f"QML pressSwitch: {name}",
            extra={"origin": "app.Bridge.pressSwitch"},
        )
        sw = self._get_switch(name)
        if sw is None:
            return

        if hasattr(sw, "press"):
            sw.press()
        else:
            # Reasonable fallback
            self.toggleSwitch(name)

    @Slot(str)
    def releaseSwitch(self, name: str) -> None:
        """
        For QML: call when a virtual button is released.
        Delegates to LogicalSwitch.release() if available, else no-op.
        """
        logger.info(
            f"QML releaseSwitch: {name}",
            extra={"origin": "app.Bridge.releaseSwitch"},
        )
        sw = self._get_switch(name)
        if sw is None:
            return

        if hasattr(sw, "release"):
            sw.release()

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

        sw = self._get_switch(logical_name)
        if sw is None:
            return

        if pressed:
            sw.press()
        else:
            sw.release()


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
