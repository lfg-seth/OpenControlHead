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
from switches import SwitchManager, SwitchType, LogicalSwitch
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
horn_ch = front_pcm.init_channel(3, label="Horn")
switches = SwitchManager()

Front_lights = switches.add(
    LogicalSwitch(
        name="Front Lights",
        type=SwitchType.CYCLE,
        channels=[front_light_left, front_light_right, grill_light],
        cycles=[
            [],
            [front_light_left],
            [front_light_left, front_light_right],
            [front_light_left, front_light_right, grill_light],
        ],
    )
)

Horn = switches.add(
    LogicalSwitch(
        name="Horn",
        type=SwitchType.MOMENTARY,
        channels=[horn_ch],
    )
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
      - SwitchManager (logical switches -> PCM channels)

    Physical buttons / SerialWorker can hook in here later, but are optional.
    """

    # Emitted so QML can react to hardware button events if desired
    picoButton = Signal(str, bool)

    def __init__(self, switches: SwitchManager, parent=None):
        super().__init__(parent)
        self._switches = switches

        # Optional mapping for future physical buttons -> logical switches
        self._button_map: dict[str, str] = {
            "LIGHT": "Front Lights",
            "HORN": "Horn",
        }

    # ---------- internals ----------

    def _get_switch(self, name: str):
        """
        Helper to fetch a LogicalSwitch by name from SwitchManager.
        Works whether SwitchManager is a dict-like or has a .get() method.
        """
        sw = None

        # SwitchManager with .get(name)
        if hasattr(self._switches, "get"):
            try:
                sw = self._switches.get(name)
            except TypeError:
                # In case .get has a different signature
                sw = None

        # Or SwitchManager *is* a dict-like
        if sw is None and isinstance(self._switches, dict):
            sw = self._switches.get(name)

        if sw is None:
            logger.warning(
                f"Unknown switch '{name}'",
                extra={"origin": "app.Bridge._get_switch"},
            )
        return sw

    # ---------- QML → Logic ----------

    @Slot(str, bool)
    def setSwitchState(self, name: str, on: bool) -> None:
        """
        Directly set a switch ON/OFF from QML.
        """
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
        """
        Toggle a switch from QML.
        """
        logger.info(
            f"QML toggleSwitch: {name}",
            extra={"origin": "app.Bridge.toggleSwitch"},
        )
        sw = self._get_switch(name)
        if sw is None:
            return

        try:
            sw.toggle()
        except AttributeError:
            logger.error(
                f"Switch '{name}' has no toggle(); add it to LogicalSwitch",
                extra={"origin": "app.Bridge.toggleSwitch"},
            )

    @Slot(str)
    def pressSwitch(self, name: str) -> None:
        """
        For QML: call when a virtual button is pressed (mouse/touch down).
        Typically mapped to LogicalSwitch.press(), which can implement
        TOGGLE / MOMENTARY / CYCLE behavior.
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
            # Reasonable fallback: just toggle
            self.toggleSwitch(name)

    @Slot(str)
    def releaseSwitch(self, name: str) -> None:
        """
        For QML: call when a virtual button is released (mouse/touch up).
        Typically mapped to LogicalSwitch.release() for momentary behavior.
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

    # ---------- Serial / physical buttons → Logic (+QML) ----------

    @Slot(str, bool)
    def handlePicoButton(self, button_name: str, pressed: bool) -> None:
        """
        Optional: called when SerialWorker reports a hardware button event.

        You can leave this unused for now; it doesn't affect QML behavior.
        """
        logger.info(
            f"Pico button event: {button_name} -> {pressed}",
            extra={"origin": "app.Bridge.handlePicoButton"},
        )

        # Re-emit to QML if UI wants to listen (optional)
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
            if hasattr(sw, "press"):
                sw.press()
            else:
                sw.toggle()
        else:
            if hasattr(sw, "release"):
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
