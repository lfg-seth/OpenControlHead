"""
pcm.py

Scaffolding for controlling one or more Power Control Modules (PCMs)
from a Raspberry Pi (Python/Qt app) over CAN.

This module defines:
- Abstract CAN interface (so you can plug in python-can, socketcan, etc.)
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

    # def add_rx_callback(self, callback: Callable[[CanMessage], None]) -> None:
    #     """
    #     Register a function that is called for every received CAN message.

    #     The PCMManager will typically register one callback and then
    #     dispatch frames to the appropriate PCMDevice instance.
    #     """
    #     ...


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
        logger.info(f"Creating PCMDevice node_id={node_id}, name={name}", extra={"origin": "pcm.PCMDevice.__init__"})

        self.channels: Dict[int, ChannelState] = {
            i: ChannelState(index=i) for i in range(self.NUM_CHANNELS)
        }
        self.adc_channels: Dict[int, AdcChannel] = {}
        self.gpio_pins: Dict[int, GpioPinState] = {}

        # Any housekeeping state (heartbeat, firmware version, etc.)
        self.online: bool = False

    # ----- Public control API -----

    def get_voltage(self) -> float:
        """
        Return the last-known supply voltage for this PCM.
        """
        logger.info(f"Getting voltage for PCM {self.name}", extra={"origin": "pcm.PCMDevice.get_voltage"})
        # Placeholder implementation
        return 12.0

    def set_channel_on(self, channel: int) -> None:
        """
        Request: turn the given channel ON.
        Implementation should:
        - Validate ch
        - Build and send appropriate CAN command
        - Update `requested_on` flag
        """
        logger.info(f"Request to turn ON channel {channel} on PCM {self.name}", extra={"origin": "pcm.PCMDevice.set_channel_on"})
        self.channels[channel].requested_on = True
        if not self.channels[channel].actual_on:
            logger.warning(f"Channel {channel} on PCM {self.name} did not turn ON as expected", extra={"origin": "pcm.PCMDevice.set_channel_on"})
        else:
            logger.info(f"Turned ON channel {channel} on PCM {self.name}", extra={"origin": "pcm.PCMDevice.set_channel_on"})
        ...

    def set_channel_off(self, channel: int) -> None:
        """
        Request: turn the given channel OFF.
        """
        logger.info(f"Request to turn OFF channel {channel} on PCM {self.name}", extra={"origin": "pcm.PCMDevice.set_channel_off"})
        self.channels[channel].requested_on = False
        if self.channels[channel].actual_on:
            logger.warning(f"Channel {channel} on PCM {self.name} did not turn OFF as expected", extra={"origin": "pcm.PCMDevice.set_channel_off"})
        else:
            logger.info(f"Turned OFF channel {channel} on PCM {self.name}", extra={"origin": "pcm.PCMDevice.set_channel_off"})
        ...

    def toggle_channel(self, channel: int) -> None:
        """
        Request: toggle channel state.
        Optional convenience wrapper for UI.
        """
        logger.info(f"Request to TOGGLE channel {channel} on PCM {self.name}", extra={"origin": "pcm.PCMDevice.toggle_channel"})
        current_state = self.get_channel_state(channel)
        logger.info(f"Current state of channel {channel} on PCM {self.name}: requested_on={current_state.requested_on}", extra={"origin": "pcm.PCMDevice.toggle_channel"})
        if current_state.requested_on:
            self.set_channel_off(channel)
        else:
            self.set_channel_on(channel)

        ...

    def set_channel_pwm(self, channel: int, duty_cycle: float) -> None:
        """
        Optionally support dimming/PWM if your hardware/protocol allows.
        duty_cycle: 0.0 - 1.0
        """
        ...

    def get_channel_state(self, channel: int) -> ChannelState:
        """
        Return the last-known state for channel `channel`.
        Does NOT necessarily cause a bus read; relies on prior updates.
        """
        return self.channels[channel]

    # ----- ADC / GPIO API (scaffolding) -----

    def request_adc_snapshot(self) -> None:
        """
        Send a CAN request asking the PCM to report current ADC values.
        """
        ...

    def get_adc_channels(self) -> Iterable[AdcChannel]:
        """
        Return all last-known ADC channel values.
        """
        return self.adc_channels.values()

    def configure_gpio_pin(self, index: int, is_output: bool) -> None:
        """
        Configure a GPIO pin's direction.
        """
        ...

    def write_gpio_pin(self, index: int, level: bool) -> None:
        """
        Set an output GPIO pin high or low.
        """
        ...

    def read_gpio_pin(self, index: int) -> Optional[GpioPinState]:
        """
        Return the last-known state for the given GPIO pin.
        """
        return self.gpio_pins.get(index)

    # ----- Internal: CAN frame handling -----

    def handle_can_message(self, msg: CanMessage) -> None:
        """
        Called by PCMManager when a CAN frame addressed to this PCM arrives.

        Responsibilities (to be implemented later):
        - Decode arbitration_id / payload.
        - Update channel states (health, on/off, current, etc.).
        - Update ADC and GPIO state.
        - Update 'online' / heartbeat status.

        This is the only place that should parse raw frames for this device.
        """
        ...

    # ----- Utility / lifecycle -----

    def refresh_status(self) -> None:
        """
        Optionally send a poll/heartbeat request for all channels.
        Implementation can be protocol-specific.
        """
        ...

    def __repr__(self) -> str:
        return f"<PCMDevice name={self.name!r} node_id={self.node_id}>"


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

    def __init__(self, can: CanInterface):
        self._can = can
        self._pcms: Dict[int, PCMDevice] = {}
        logger.info("PCMManager created", extra={"origin": "pcm.PCMManager.__init__"})

        # Register global RX callback
        # self._can.add_rx_callback(self._on_can_message)

    def add_pcm(self, node_id: int, name: Optional[str] = None) -> PCMDevice:
        """
        Create and register a PCMDevice for the given node_id.
        Returns the created instance.
        """
        logger.info(f"Creating PCMDevice node_id={node_id}, name={name}", extra={"origin": "pcm.PCMManager.add_pcm"})
        device = PCMDevice(node_id=node_id, can=self._can, name=name)
        self._pcms[node_id] = device
        logger.info(f"PCMDevice created: {device}", extra={"origin": "pcm.PCMManager.add_pcm"})
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

        Implementation (later) should:
        - Decode which node_id / PCM this frame belongs to.
        - Find the correct PCMDevice and call device.handle_can_message(msg).
        """
        ...

    # Convenience helpers for app/Qt:

    def set_channel_on(self, node_id: int, channel: int) -> None:
        logger.info(f"Setting channel {channel} ON for PCM node_id={node_id}", extra={"origin": "pcm.PCMManager.set_channel_on"})
        pcm = self._pcms[node_id]
        pcm.set_channel_on(channel)

    def set_channel_off(self, node_id: int, channel: int) -> None:
        logger.info(f"Setting channel {channel} OFF for PCM node_id={node_id}", extra={"origin": "pcm.PCMManager.set_channel_off"})
        pcm = self._pcms[node_id]
        pcm.set_channel_off(channel)

    def get_channel_state(self, node_id: int, channel: int) -> ChannelState:
        pcm = self._pcms[node_id]
        return pcm.get_channel_state(channel)