"""
pcm.py

Scaffolding for controlling one or more Power Control Modules (PCMs)
from a Raspberry Pi (Python/Qt app) over CAN, using the 29-bit
ID layout described in the Accessory Control Network spec.

29-bit ID layout:

+------------+------------+----------------+----------------+------------+
| 28 .. 26   | 25 .. 21   | 20 .. 13       | 12 .. 5        | 4 .. 0     |
+------------+------------+----------------+----------------+------------+
| PRIORITY   | MSG_CLASS  | SRC_NODE_ID    | DST_NODE_ID    | SUBJECT    |
| (3 bits)   | (5 bits)   | (8 bits)       | (8 bits)       | (5 bits)   |
+------------+------------+----------------+----------------+------------+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, Callable, Dict, List, Optional, Iterable
import logging

logger = logging.getLogger("control_head.pcm")


# ---------- Protocol constants ----------

# Node IDs
CONTROL_HEAD_NODE_ID = 0x90  # Pi-based control head default

# Priorities (3 bits, lower = higher priority)
PRIO_CRITICAL = 0b000
PRIO_FAULT    = 0b001
PRIO_CONTROL  = 0b010
PRIO_SENSOR   = 0b011
PRIO_HB       = 0b100  # heartbeat / discovery / config

# Message classes (MSG_CLASS)
MSG_CLASS_PCM_CONTROL = 0x01
MSG_CLASS_PCM_STATUS  = 0x02
MSG_CLASS_PCM_ADC_IO  = 0x03
MSG_CLASS_SENSOR_DATA = 0x04
MSG_CLASS_CONFIG      = 0x05
MSG_CLASS_HB_DISC     = 0x06

# Subjects within PCM Control (CLASS = 0x01)
SUBJECT_PCM_SINGLE_CMD   = 0x00
SUBJECT_PCM_BULK_CMD     = 0x01
SUBJECT_PCM_PWM_CONFIG   = 0x02
SUBJECT_PCM_REQ_SNAPSHOT = 0x03

# Subjects within PCM Status (CLASS = 0x02)
SUBJECT_PCM_SINGLE_STATUS = 0x00
SUBJECT_PCM_BULK_STATUS   = 0x01
SUBJECT_PCM_FAULT_REPORT  = 0x02
SUBJECT_PCM_BOARD_METRICS = 0x03

# Subjects within PCM ADC/IO (CLASS = 0x03)
SUBJECT_PCM_ADC_READING  = 0x00
SUBJECT_PCM_GPIO_STATE   = 0x01

# Heartbeat / discovery (CLASS = 0x06)
SUBJECT_HB_HEARTBEAT = 0x00
SUBJECT_HB_DISC_REQ  = 0x01


# ---------- 29-bit ID helpers ----------

def build_arb_id(
    priority: int,
    msg_class: int,
    src_node_id: int,
    dst_node_id: int,
    subject: int,
) -> int:
    """
    Encode the 29-bit identifier according to the spec.
    """
    return (
        ((priority   & 0x7)  << 26)
        | ((msg_class   & 0x1F) << 21)
        | ((src_node_id & 0xFF) << 13)
        | ((dst_node_id & 0xFF) << 5)
        | (subject      & 0x1F)
    )


@dataclass(frozen=True)
class IdFields:
    priority: int
    msg_class: int
    src_node_id: int
    dst_node_id: int
    subject: int


def parse_arb_id(arb_id: int) -> IdFields:
    """
    Decode a 29-bit identifier into its fields.
    """
    priority    = (arb_id >> 26) & 0x7
    msg_class   = (arb_id >> 21) & 0x1F
    src_node_id = (arb_id >> 13) & 0xFF
    dst_node_id = (arb_id >> 5)  & 0xFF
    subject     = arb_id & 0x1F
    return IdFields(
        priority=priority,
        msg_class=msg_class,
        src_node_id=src_node_id,
        dst_node_id=dst_node_id,
        subject=subject,
    )


# ---------- CAN Abstractions ----------

class CanMessage:
    """
    Simple container for CAN frames inside the PCM layer.
    """
    def __init__(self, arbitration_id: int, data: bytes):
        self.arbitration_id = arbitration_id
        self.data = data

        # Decode fields for convenience
        fields = parse_arb_id(arbitration_id)
        self.priority = fields.priority
        self.msg_class = fields.msg_class
        self.src_node_id = fields.src_node_id
        self.dst_node_id = fields.dst_node_id
        self.subject = fields.subject

    def __repr__(self) -> str:
        return (
            f"<CanMessage prio={self.priority} class=0x{self.msg_class:02X} "
            f"src=0x{self.src_node_id:02X} dst=0x{self.dst_node_id:02X} "
            f"subj=0x{self.subject:02X} data={self.data.hex()}>"
        )


class CanInterface(Protocol):
    """
    Abstract CAN interface used by PCMDevice/PCMManager.

    Implement this with python-can, socketcan, a CAN HAT driver, etc.
    Your Qt app should create a concrete implementation and pass it in.
    """

    def send(self, msg: CanMessage) -> None:
        """Transmit a CAN message onto the bus."""
        ...

    def add_rx_callback(self, callback: Callable[[CanMessage], None]) -> None:
        """
        Register a function that is called for every received CAN message.
        """
        ...


# ---------- Concrete CAN implementation for can0 ----------

class SocketCanInterface:
    """
    Concrete CanInterface implementation using python-can + socketcan.

    Assumes you've already brought up can0, e.g.:
        sudo ip link set can0 up type can bitrate 500000

    Uses *extended* (29-bit) IDs as required by the protocol spec.
    """

    def __init__(self, channel: str = "can0", interface: str = "socketcan"):
        try:
            import can  # type: ignore[import-not-found]
        except ImportError:
            logger.error(
                "python-can is not installed. Install with 'pip install python-can'.",
                extra={"origin": "pcm.SocketCanInterface.__init__"},
            )
            raise

        self._can_mod = can
        self._bus = can.Bus(channel=channel, interface=interface)
        self._callbacks: list[Callable[[CanMessage], None]] = []

        # Notifier will call our internal _on_message for each frame.
        self._notifier = can.Notifier(self._bus, [self._on_message])
        logger.info(
            f"SocketCanInterface initialized on {interface}:{channel}",
            extra={"origin": "pcm.SocketCanInterface.__init__"},
        )

    def send(self, msg: CanMessage) -> None:
        """Transmit a CanMessage onto the bus."""
        can_msg = self._can_mod.Message(
            arbitration_id=msg.arbitration_id,
            data=msg.data,
            is_extended_id=True,  # 29-bit IDs
        )
        logger.debug(
            f"TX CAN arb=0x{msg.arbitration_id:08X} data={msg.data.hex()}",
            extra={"origin": "pcm.SocketCanInterface.send"},
        )
        self._bus.send(can_msg)

    def add_rx_callback(self, callback: Callable[[CanMessage], None]) -> None:
        self._callbacks.append(callback)

    # ----- internal -----

    def _on_message(self, can_msg) -> None:
        """
        Adapter from python-can's Message -> our CanMessage class.
        """
        msg = CanMessage(
            arbitration_id=can_msg.arbitration_id,
            data=bytes(can_msg.data),
        )
        logger.debug(
            f"RX CAN {msg!r}",
            extra={"origin": "pcm.SocketCanInterface._on_message"},
        )
        for cb in list(self._callbacks):
            try:
                cb(msg)
            except Exception:
                logger.exception(
                    "Error in CAN RX callback",
                    extra={"origin": "pcm.SocketCanInterface._on_message"},
                )


# ---------- Channel / ADC / GPIO Models ----------

class ChannelHealth(Enum):
    UNKNOWN = auto()
    OFF = auto()
    ON = auto()
    SHORT = auto()
    OPEN = auto()


@dataclass
class ChannelState:
    """
    Represents the last-known state of a single high-side channel.
    """
    index: int
    health: ChannelHealth = ChannelHealth.UNKNOWN
    current_amps: float = 0.0
    requested_on: bool = False  # what we *asked* for
    actual_on: bool = False     # what PCM reports


@dataclass
class AdcChannel:
    """
    Represents a single ADC input on the PCM.
    """
    index: int
    raw_value: int = 0        # raw ADC counts
    voltage: float = 0.0      # scaled to volts (if known)


@dataclass
class GpioPinState:
    """
    Represents a single GPIO pin on the PCM expansion header.
    Direction/config can be extended later.
    """
    index: int
    is_output: bool = False
    level: bool = False       # True = high, False = low. For outputs, shows actual state.
    target_level: Optional[bool] = None  # for outputs, shows desired state


# ---------- PCM Device ----------

class PCMDevice:
    """
    Represents a single PCM in the engine bay.

    Responsibilities:
    - Encode/decode CAN frames for this module according to the spec.
    - Track per-channel state (ON/OFF/SHORT/OPEN/current).
    - Expose methods used by the UI / application logic.
    - Handle ADC reads and GPIO expansion (future use).

    This class does NOT know about Qt; keep it pure logic so it’s testable.
    """

    NUM_CHANNELS = 26

    def __init__(
        self,
        node_id: int,
        can: CanInterface,
        controller_node_id: int,
        name: Optional[str] = None,
    ):
        """
        :param node_id: Logical/module ID used on the bus for this PCM.
        :param can:     Shared CAN interface.
        :param controller_node_id: Node ID of the control head (SRC for commands).
        :param name:    Friendly label (e.g. 'Front PCM', 'Rear PCM').
        """
        self.node_id = node_id
        self.controller_node_id = controller_node_id
        self.name = name or f"PCM-{node_id:02X}"
        self._can = can
        logger.info(
            f"Creating PCMDevice node_id=0x{node_id:02X}, name={self.name}",
            extra={"origin": "pcm.PCMDevice.__init__"},
        )

        self.channels: list[PCMChannel] = [
            PCMChannel(self, i) for i in range(self.NUM_CHANNELS)
        ]
        self.adc_channels: Dict[int, AdcChannel] = {}
        self.gpio_pins: Dict[int, GpioPinState] = {}

        # Any housekeeping state (heartbeat, firmware version, etc.)
        self.online: bool = False

    def channel(self, index: int, name: str | None = None) -> "PCMChannel":
        ch = self.channels[index]
        if name:
            ch.name = name
        return ch

    # ----- CAN encoding helpers for this device -----

    def _send_pcm_control(
        self,
        subject: int,
        payload: bytes,
        priority: int = PRIO_CONTROL,
    ) -> None:
        """
        Build and send a PCM Control message (MSG_CLASS = 0x01) to this PCM.
        """
        arb_id = build_arb_id(
            priority=priority,
            msg_class=MSG_CLASS_PCM_CONTROL,
            src_node_id=self.controller_node_id,
            dst_node_id=self.node_id,
            subject=subject,
        )
        msg = CanMessage(arb_id, payload)
        logger.debug(
            f"{self.name} TX CONTROL subject=0x{subject:02X} payload={payload.hex()} "
            f"arb=0x{arb_id:08X}",
            extra={"origin": "pcm.PCMDevice._send_pcm_control"},
        )
        self._can.send(msg)

    # ----- Public control API -----

    def init_channel(
        self,
        channel_index: int,
        label: Optional[str] = None,
        pwm_capable: bool = False,
    ) -> "PCMChannel":
        """
        Initialize and return a PCMChannel instance for the given index.
        Optionally set a label and/or mark as PWM-capable.
        """
        ch = self.channels[channel_index]
        if label:
            ch.name = label
        # pwm_capable can be stored/used later as needed
        logger.info(
            f"Initialized PCMChannel index={channel_index}, label={label}, pwm_capable={pwm_capable}",
            extra={"origin": "pcm.PCMDevice.init_channel"},
        )
        return ch

    def get_voltage(self) -> float:
        """
        Return the last-known supply voltage for this PCM.
        """
        logger.info(
            f"Getting voltage for PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.get_voltage"},
        )
        # Placeholder implementation until board metrics are wired up.
        return 12.0

    def set_channel_on(self, channel: int) -> None:
        """
        Request: turn the given channel ON via Single Channel Command.
        Payload (DLC=3):
          Byte 0: channel index
          Byte 1: command (0x01 = ON)
          Byte 2: PWM = 0 (unused)
        """
        ch = self.channels[channel]
        logger.info(
            f"Request to turn ON channel {channel} on PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.set_channel_on"},
        )
        ch.requested_on = True

        payload = bytes([channel & 0xFF, 0x01, 0x00])
        self._send_pcm_control(SUBJECT_PCM_SINGLE_CMD, payload)

    def set_channel_off(self, channel: int) -> None:
        """
        Request: turn the given channel OFF via Single Channel Command.
        """
        ch = self.channels[channel]
        logger.info(
            f"Request to turn OFF channel {channel} on PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.set_channel_off"},
        )
        ch.requested_on = False

        payload = bytes([channel & 0xFF, 0x00, 0x00])
        self._send_pcm_control(SUBJECT_PCM_SINGLE_CMD, payload)

    def toggle_channel(self, channel: int) -> None:
        """
        Request: toggle channel state (command 0x02).
        """
        ch = self.channels[channel]
        logger.info(
            f"Request to TOGGLE channel {channel} on PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.toggle_channel"},
        )
        payload = bytes([channel & 0xFF, 0x02, 0x00])
        # requested_on will flip when we get status back; for now, just optimistic:
        ch.requested_on = not ch.requested_on
        self._send_pcm_control(SUBJECT_PCM_SINGLE_CMD, payload)

    def set_channel_pwm(self, channel: int, duty_cycle: float) -> None:
        """
        Optionally support dimming/PWM. Uses Single Channel Command with
        Command = 0x03 (SET_PWM), Byte2 = duty 0-255.
        duty_cycle: 0.0 - 1.0
        """
        duty = max(0.0, min(1.0, duty_cycle))
        duty_byte = int(duty * 255) & 0xFF
        logger.info(
            f"Request to set PWM on channel {channel} to {duty:.3f} ({duty_byte})",
            extra={"origin": "pcm.PCMDevice.set_channel_pwm"},
        )
        payload = bytes([channel & 0xFF, 0x03, duty_byte])
        self._send_pcm_control(SUBJECT_PCM_SINGLE_CMD, payload)

    def request_status_snapshot(self) -> None:
        """
        Controller → PCM: send status/ADC/GPIO snapshot.
        Uses SUBJECT = 0x03 (Request Status Snapshot).
        For now, just request channel snapshot (0x01).
        """
        logger.info(
            f"Requesting status snapshot from PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.request_status_snapshot"},
        )
        payload = bytes([0x01])  # 0x01 = request channel snapshot per spec
        self._send_pcm_control(SUBJECT_PCM_REQ_SNAPSHOT, payload)

    def get_channel_state(self, channel: int) -> ChannelState:
        """
        Return a ChannelState snapshot for channel `channel`.
        Uses the underlying PCMChannel's state.
        """
        ch = self.channels[channel]
        return ch.to_state()

    # ----- ADC / GPIO API (scaffolding) -----

    def request_adc_snapshot(self) -> None:
        """
        Request ADC snapshot via Request Status (type 0x02).
        """
        logger.info(
            f"Requesting ADC snapshot from PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.request_adc_snapshot"},
        )
        payload = bytes([0x02])  # 0x02 = request ADC snapshot
        self._send_pcm_control(SUBJECT_PCM_REQ_SNAPSHOT, payload)

    def get_adc_channels(self) -> Iterable[AdcChannel]:
        """
        Return all last-known ADC channel values.
        """
        return self.adc_channels.values()

    def configure_gpio_pin(self, index: int, is_output: bool) -> None:
        """
        Configure a GPIO pin's direction (scaffolding; exact payload TBD).
        """
        logger.info(
            f"Configuring GPIO pin {index} on PCM {self.name} is_output={is_output}",
            extra={"origin": "pcm.PCMDevice.configure_gpio_pin"},
        )
        # When defined, this should use MSG_CLASS = 0x03 / SUBJECT = 0x01 or CONFIG class.
        # Placeholder: no-op.

    def write_gpio_pin(self, index: int, level: bool) -> None:
        """
        Set an output GPIO pin high or low (scaffolding).
        """
        logger.info(
            f"Writing GPIO pin {index} on PCM {self.name} level={level}",
            extra={"origin": "pcm.PCMDevice.write_gpio_pin"},
        )
        # Placeholder: no-op.

    def read_gpio_pin(self, index: int) -> Optional[GpioPinState]:
        """
        Return the last-known state for the given GPIO pin.
        """
        return self.gpio_pins.get(index)

    # ----- Internal: CAN frame handling -----

    def handle_can_message(self, msg: CanMessage) -> None:
        """
        Called by PCMManager when a CAN frame from this PCM arrives.

        This is where we parse PCM Status / ADC / GPIO messages and
        update local state.
        """
        logger.debug(
            f"{self.name} handling CAN msg: {msg!r}",
            extra={"origin": "pcm.PCMDevice.handle_can_message"},
        )

        # For now, just stub out some obvious cases:
        if msg.msg_class == MSG_CLASS_PCM_STATUS:
            if msg.subject == SUBJECT_PCM_SINGLE_STATUS and len(msg.data) >= 5:
                ch_index = msg.data[0]
                if ch_index < len(self.channels):
                    state_byte = msg.data[1]
                    current_ma = (msg.data[2] << 8) | msg.data[3]

                    ch = self.channels[ch_index]
                    ch.actual_on = bool(state_byte & 0x01)
                    ch.requested_on = bool(state_byte & 0x02)
                    fault = bool(state_byte & 0x04)
                    short_detected = bool(state_byte & 0x08)
                    open_load = bool(state_byte & 0x10)
                    overcurrent = bool(state_byte & 0x20)
                    overtemp = bool(state_byte & 0x40)

                    # Simple mapping for now:
                    if fault or short_detected or overcurrent or overtemp:
                        ch.health = ChannelHealth.SHORT  # TODO: refine based on bits
                    elif open_load:
                        ch.health = ChannelHealth.OPEN
                    elif ch.actual_on:
                        ch.health = ChannelHealth.ON
                    else:
                        ch.health = ChannelHealth.OFF

                    ch.current_amps = current_ma / 1000.0

                    logger.info(
                        f"{self.name} CH{ch_index} status: "
                        f"actual_on={ch.actual_on}, requested_on={ch.requested_on}, "
                        f"health={ch.health.name}, current={ch.current_amps:.3f}A",
                        extra={"origin": "pcm.PCMDevice.handle_can_message"},
                    )

            # Bulk status, fault reports, board metrics can be hooked here later.

        elif msg.msg_class == MSG_CLASS_PCM_ADC_IO:
            if msg.subject == SUBJECT_PCM_ADC_READING and len(msg.data) >= 4:
                adc_index = msg.data[0]
                raw = (msg.data[1] << 8) | msg.data[2]
                ch = self.adc_channels.get(adc_index) or AdcChannel(index=adc_index)
                ch.raw_value = raw
                # voltage scaling is PCM-specific; leave at 0.0 for now.
                self.adc_channels[adc_index] = ch
                logger.info(
                    f"{self.name} ADC{adc_index} raw={raw}",
                    extra={"origin": "pcm.PCMDevice.handle_can_message"},
                )

            # GPIO state could be handled similarly.

        # Heartbeats / discovery could set self.online, FW version, etc.

    # ----- Utility / lifecycle -----

    def refresh_status(self) -> None:
        """
        Optionally send a poll/heartbeat request for all channels.
        Uses Request Status Snapshot (type 0x01).
        """
        logger.info(
            f"Refreshing status for PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.refresh_status"},
        )
        payload = bytes([0x01])  # 0x01 = request channel snapshot
        self._send_pcm_control(SUBJECT_PCM_REQ_SNAPSHOT, payload)

    def __repr__(self) -> str:
        return f"<PCMDevice name={self.name!r} node_id=0x{self.node_id:02X}>"


class PCMChannel:
    """
    Represents a single high-side channel on a PCMDevice.
    Owns its own state and forwards control calls to the parent PCMDevice.
    """

    def __init__(self, pcm: "PCMDevice", index: int, name: str = ""):
        self.pcm = pcm
        self.index = index
        self.name = name or f"CH{index}"

        # State that used to live in ChannelState
        self.health: ChannelHealth = ChannelHealth.UNKNOWN
        self.current_amps: float = 0.0
        self.requested_on: bool = False  # what we asked the PCM to do
        self.actual_on: bool = False     # what the PCM reports back

    # ----- control helpers -----

    def on(self) -> None:
        """Request to turn this channel ON."""
        self.pcm.set_channel_on(self.index)

    def off(self) -> None:
        """Request to turn this channel OFF."""
        self.pcm.set_channel_off(self.index)

    def toggle(self) -> None:
        """Convenience toggle using the parent PCMDevice."""
        self.pcm.toggle_channel(self.index)

    # ----- convenience view -----

    def to_state(self) -> ChannelState:
        """
        Return a ChannelState snapshot for this channel.
        Useful if other code still wants the dataclass view.
        """
        return ChannelState(
            index=self.index,
            health=self.health,
            current_amps=self.current_amps,
            requested_on=self.requested_on,
            actual_on=self.actual_on,
        )


# ---------- PCM Manager (multiple modules) ----------

class PCMManager:
    """
    Owns:
    - Shared CAN interface
    - A set of PCMDevice instances (e.g. front/rear PCMs)

    Responsibilities:
    - Subscribe to incoming CAN frames.
    - Route each frame to the appropriate PCMDevice by SRC_NODE_ID.
    - Provide convenience helpers for the UI / higher-level code.
    """

    def __init__(self, can_iface: CanInterface, local_node_id: int = CONTROL_HEAD_NODE_ID):
        self._can = can_iface
        self._pcms: Dict[int, PCMDevice] = {}
        self.local_node_id = local_node_id

        logger.info(
            f"PCMManager created local_node_id=0x{local_node_id:02X}",
            extra={"origin": "pcm.PCMManager.__init__"},
        )

        # Register global RX callback so we see all frames.
        self._can.add_rx_callback(self._on_can_message)

    def add_pcm(self, node_id: int, name: Optional[str] = None) -> PCMDevice:
        """
        Create and register a PCMDevice for the given node_id.
        Returns the created instance.
        """
        logger.info(
            f"Creating PCMDevice node_id=0x{node_id:02X}, name={name}",
            extra={"origin": "pcm.PCMManager.add_pcm"},
        )
        device = PCMDevice(
            node_id=node_id,
            can=self._can,
            controller_node_id=self.local_node_id,
            name=name,
        )
        self._pcms[node_id] = device
        logger.info(
            f"PCMDevice created: {device}",
            extra={"origin": "pcm.PCMManager.add_pcm"},
        )
        return device

    def get_pcm(self, node_id: int) -> Optional[PCMDevice]:
        """
        Return the PCMDevice for the given node_id, if any.
        """
        return self._pcms.get(node_id)

    def all_pcms(self) -> List[PCMDevice]:
        """
        Return a list of all registered PCMs.
        """
        return list(self._pcms.values())

    def _on_can_message(self, msg: CanMessage) -> None:
        """
        Global RX dispatcher.

        For PCM traffic, SRC_NODE_ID is the PCM's node ID.
        We route based on that.
        """
        src = msg.src_node_id
        pcm = self._pcms.get(src)
        if pcm is None:
            # Could be sensors, other controllers, etc.
            logger.debug(
                f"RX frame from unknown SRC=0x{src:02X}: {msg!r}",
                extra={"origin": "pcm.PCMManager._on_can_message"},
            )
            return

        pcm.handle_can_message(msg)

    # Convenience helpers for app/Qt:

    def set_channel_on(self, node_id: int, channel: int) -> None:
        logger.info(
            f"Setting channel {channel} ON for PCM node_id=0x{node_id:02X}",
            extra={"origin": "pcm.PCMManager.set_channel_on"},
        )
        pcm = self._pcms[node_id]
        pcm.set_channel_on(channel)

    def set_channel_off(self, node_id: int, channel: int) -> None:
        logger.info(
            f"Setting channel {channel} OFF for PCM node_id=0x{node_id:02X}",
            extra={"origin": "pcm.PCMManager.set_channel_off"},
        )
        pcm = self._pcms[node_id]
        pcm.set_channel_off(channel)

    def get_channel_state(self, node_id: int, channel: int) -> ChannelState:
        pcm = self._pcms[node_id]
        return pcm.get_channel_state(channel)
