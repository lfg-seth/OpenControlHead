"""
pcm.py

Scaffolding for controlling one or more Power Control Modules (PCMs)
from a Raspberry Pi (Python/Qt app) over CAN.

This module defines:
- CanMessage: simple container for CAN frames
- CanInterface: protocol for plug-in CAN backends
- SocketCanInterface: concrete implementation for can0 via python-can
- Data models for channel state, ADC values, GPIO state
- PCMDevice: represents a single PCM in the engine bay
- PCMManager: coordinates multiple PCMDevice instances on a shared bus
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, Callable, Dict, List, Optional, Iterable
import logging

logger = logging.getLogger("control_head.pcm")


# ---------- CAN Abstractions ----------

class CanMessage:
    """
    Simple container for CAN frames passed into/from the PCM layer.
    Adjust as needed for your actual CAN stack.
    """
    def __init__(self, arbitration_id: int, data: bytes):
        self.arbitration_id = arbitration_id
        self.data = data


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

        The PCMManager will typically register one callback and then
        dispatch frames to the appropriate PCMDevice instance.
        """
        ...


# ---------- Concrete CAN implementation for can0 ----------

class SocketCanInterface:
    """
    Concrete CanInterface implementation using python-can + socketcan.

    Assumes you've already brought up can0, e.g.:
        sudo ip link set can0 up type can bitrate 500000
    """

    def __init__(self, channel: str = "can0", interface: str = "socketcan"):
        try:
            import can  # type: ignore[import-not-found]
        except ImportError as e:
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
            is_extended_id=False,  # flip to True if you use extended IDs
        )
        logger.debug(
            f"TX CAN arb=0x{msg.arbitration_id:X} data={msg.data.hex()}",
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
            f"RX CAN arb=0x{msg.arbitration_id:X} data={msg.data.hex()}",
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
    - Encode/decode CAN frames for this module.
    - Track per-channel state (ON/OFF/SHORT/OPEN/current).
    - Expose methods used by the UI / application logic.
    - Handle ADC reads and GPIO expansion (future use).

    This class does NOT know about Qt; keep it pure logic so it’s testable.
    """

    NUM_CHANNELS = 26

    def __init__(self, node_id: int, can: CanInterface, name: Optional[str] = None):
        """
        :param node_id: Logical/module ID used in your CAN protocol
        :param can:     Shared CAN interface
        :param name:    Friendly label (e.g. 'Front PCM', 'Rear PCM')
        """
        self.node_id = node_id
        self.name = name or f"PCM-{node_id}"
        self._can = can
        logger.info(
            f"Creating PCMDevice node_id={node_id}, name={name}",
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

    # ----- CAN encoding helpers (example protocol!) -----

    def _make_arb_id(self, command_id: int) -> int:
        """
        Example arbitration ID layout:

            [ 10 bits node_id ][ 6 bits command_id ]

        Adjust this to match your actual firmware protocol.
        """
        return (self.node_id << 6) | (command_id & 0x3F)

    def _send_command(self, command_id: int, payload: bytes) -> None:
        """
        Helper to send a command to this PCM over CAN.

        This is a *placeholder* protocol. Swap it for whatever your
        actual PCM firmware expects.
        """
        arb_id = self._make_arb_id(command_id)
        msg = CanMessage(arbitration_id=arb_id, data=payload)
        logger.debug(
            f"PCM {self.name} TX cmd=0x{command_id:X} arb=0x{arb_id:X} payload={payload.hex()}",
            extra={"origin": "pcm.PCMDevice._send_command"},
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
        # Placeholder implementation
        return 12.0

    def set_channel_on(self, channel: int) -> None:
        """
        Request: turn the given channel ON.
        """
        ch = self.channels[channel]
        logger.info(
            f"Request to turn ON channel {channel} on PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.set_channel_on"},
        )
        ch.requested_on = True

        # ----- example CAN command layout -----
        # command_id 0x01 = "set channel state"
        # payload: [channel_index, 0x01]  -> ON
        payload = bytes([channel & 0xFF, 0x01])
        self._send_command(0x01, payload)

    def set_channel_off(self, channel: int) -> None:
        """
        Request: turn the given channel OFF.
        """
        ch = self.channels[channel]
        logger.info(
            f"Request to turn OFF channel {channel} on PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.set_channel_off"},
        )
        ch.requested_on = False

        # payload: [channel_index, 0x00]  -> OFF
        payload = bytes([channel & 0xFF, 0x00])
        self._send_command(0x01, payload)

    def toggle_channel(self, channel: int) -> None:
        """
        Request: toggle channel state.
        Optional convenience wrapper for UI.
        """
        ch = self.channels[channel]
        logger.info(
            f"Request to TOGGLE channel {channel} on PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.toggle_channel"},
        )
        if ch.requested_on:
            self.set_channel_off(channel)
        else:
            self.set_channel_on(channel)

    def set_channel_pwm(self, channel: int, duty_cycle: float) -> None:
        """
        Optionally support dimming/PWM if your hardware/protocol allows.
        duty_cycle: 0.0 - 1.0
        """
        logger.info(
            f"Request to set PWM on channel {channel} to {duty_cycle:.3f}",
            extra={"origin": "pcm.PCMDevice.set_channel_pwm"},
        )
        # Example: command_id 0x02 = "set PWM"
        dc = max(0.0, min(1.0, duty_cycle))
        duty_byte = int(dc * 255) & 0xFF
        payload = bytes([channel & 0xFF, duty_byte])
        self._send_command(0x02, payload)

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
        Send a CAN request asking the PCM to report current ADC values.
        """
        logger.info(
            f"Requesting ADC snapshot from PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.request_adc_snapshot"},
        )
        # Example command_id 0x10 = "request ADC snapshot"
        self._send_command(0x10, b"")

    def get_adc_channels(self) -> Iterable[AdcChannel]:
        """
        Return all last-known ADC channel values.
        """
        return self.adc_channels.values()

    def configure_gpio_pin(self, index: int, is_output: bool) -> None:
        """
        Configure a GPIO pin's direction.
        """
        logger.info(
            f"Configuring GPIO pin {index} on PCM {self.name} is_output={is_output}",
            extra={"origin": "pcm.PCMDevice.configure_gpio_pin"},
        )
        # Example: cmd 0x20 = "configure GPIO"
        payload = bytes([index & 0xFF, 0x01 if is_output else 0x00])
        self._send_command(0x20, payload)

    def write_gpio_pin(self, index: int, level: bool) -> None:
        """
        Set an output GPIO pin high or low.
        """
        logger.info(
            f"Writing GPIO pin {index} on PCM {self.name} level={level}",
            extra={"origin": "pcm.PCMDevice.write_gpio_pin"},
        )
        # Example: cmd 0x21 = "write GPIO"
        payload = bytes([index & 0xFF, 0x01 if level else 0x00])
        self._send_command(0x21, payload)

    def read_gpio_pin(self, index: int) -> Optional[GpioPinState]:
        """
        Return the last-known state for the given GPIO pin.
        """
        return self.gpio_pins.get(index)

    # ----- Internal: CAN frame handling -----

    def handle_can_message(self, msg: CanMessage) -> None:
        """
        Called by PCMManager when a CAN frame addressed to this PCM arrives.

        This is the only place that should parse raw frames for this device.
        """
        logger.debug(
            f"{self.name} handling CAN msg arb=0x{msg.arbitration_id:X} data={msg.data.hex()}",
            extra={"origin": "pcm.PCMDevice.handle_can_message"},
        )

        # TODO: decode your actual protocol here:
        # - Update self.channels[i].actual_on, health, current_amps, etc.
        # - Update ADC and GPIO state.
        # - Update self.online / heartbeat status.
        # For now it's just a stub.

    # ----- Utility / lifecycle -----

    def refresh_status(self) -> None:
        """
        Optionally send a poll/heartbeat request for all channels.
        Implementation can be protocol-specific.
        """
        logger.info(
            f"Refreshing status for PCM {self.name}",
            extra={"origin": "pcm.PCMDevice.refresh_status"},
        )
        # Example: cmd 0x30 = "heartbeat / status poll"
        self._send_command(0x30, b"")

    def __repr__(self) -> str:
        return f"<PCMDevice name={self.name!r} node_id={self.node_id}>"


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
    - Route each frame to the appropriate PCMDevice by node_id/arbitration_id.
    - Provide convenience helpers for the UI / higher-level code.
    """

    def __init__(self, can_iface: CanInterface):
        self._can = can_iface
        self._pcms: Dict[int, PCMDevice] = {}
        logger.info("PCMManager created", extra={"origin": "pcm.PCMManager.__init__"})

        # Register global RX callback so we see all frames.
        self._can.add_rx_callback(self._on_can_message)

    def add_pcm(self, node_id: int, name: Optional[str] = None) -> PCMDevice:
        """
        Create and register a PCMDevice for the given node_id.
        Returns the created instance.
        """
        logger.info(
            f"Creating PCMDevice node_id={node_id}, name={name}",
            extra={"origin": "pcm.PCMManager.add_pcm"},
        )
        device = PCMDevice(node_id=node_id, can=self._can, name=name)
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

    def _decode_node_id_from_arb(self, arb_id: int) -> Optional[int]:
        """
        Reverse of PCMDevice._make_arb_id, to figure out which PCM
        a given frame belongs to.

        Adjust this to match your actual protocol. For the example:
            node_id = arb_id >> 6
        """
        return arb_id >> 6

    def _on_can_message(self, msg: CanMessage) -> None:
        """
        Global RX dispatcher.

        - Decode which node_id / PCM this frame belongs to.
        - Find the correct PCMDevice and call device.handle_can_message(msg).
        """
        node_id = self._decode_node_id_from_arb(msg.arbitration_id)
        if node_id is None:
            logger.debug(
                f"Dropping CAN msg arb=0x{msg.arbitration_id:X}: couldn't decode node_id",
                extra={"origin": "pcm.PCMManager._on_can_message"},
            )
            return

        pcm = self._pcms.get(node_id)
        if pcm is None:
            logger.debug(
                f"Got CAN msg for unknown node_id={node_id}: arb=0x{msg.arbitration_id:X}",
                extra={"origin": "pcm.PCMManager._on_can_message"},
            )
            return

        pcm.handle_can_message(msg)

    # Convenience helpers for app/Qt:

    def set_channel_on(self, node_id: int, channel: int) -> None:
        logger.info(
            f"Setting channel {channel} ON for PCM node_id={node_id}",
            extra={"origin": "pcm.PCMManager.set_channel_on"},
        )
        pcm = self._pcms[node_id]
        pcm.set_channel_on(channel)

    def set_channel_off(self, node_id: int, channel: int) -> None:
        logger.info(
            f"Setting channel {channel} OFF for PCM node_id={node_id}",
            extra={"origin": "pcm.PCMManager.set_channel_off"},
        )
        pcm = self._pcms[node_id]
        pcm.set_channel_off(channel)

    def get_channel_state(self, node_id: int, channel: int) -> ChannelState:
        pcm = self._pcms[node_id]
        return pcm.get_channel_state(channel)
