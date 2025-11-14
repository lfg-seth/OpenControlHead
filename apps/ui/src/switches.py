# switches.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Iterable, Optional
import logging

from pcm import PCMManager, ChannelState, ChannelHealth, PCMChannel  # adjust import as needed

logger = logging.getLogger("control_head.switches")


# ---------- Models ----------

# @dataclass(frozen=True)
# class ChannelBinding:
#     """
#     Links a logical switch to a specific PCM channel.

#     Keeping this small & serializable so it can come from config.
#     """
#     node_id: int
#     channel_index: int
#     # Optional fields for future use (pwm, role, etc.)
#     label: Optional[str] = None
#     pwm_capable: bool = False


class SwitchState(Enum):
    UNKNOWN = auto()
    OFF = auto()
    ON = auto()
    PARTIAL = auto()
    FAULT = auto()
    
class SwitchType(Enum):
    TOGGLE = auto()
    MOMENTARY = auto()
    CYCLE = auto()


# ---------- Logical Switch ----------

class LogicalSwitch:
    def __init__(
        self,
        name: str,
        channels: List[PCMChannel],
        type: SwitchType = SwitchType.TOGGLE,
        cycles: List[List[PCMChannel]] | None = None,
    ):
        self.name = name
        self.channels = channels
        self.type = type
        # For CYCLE behavior
        self.cycles: List[List[PCMChannel]] = cycles or []
        self._cycle_index: int = 0  # index into self._cycles

        logger.info(
            f"LogicalSwitch created: {self.name} with {len(channels)} channels "
            f"(type={self.type}, cycles={len(self.cycles)})",
            extra={"origin": "switches.LogicalSwitch.__init__"},
        )

    # ----- Public API -----

    def on(self) -> None:
        """
        Turn ALL bound channels ON (as a command).
        """
        logger.info(f"Turning ON LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.on"})
        for ch in self.channels:
            ch.on()

    def off(self) -> None:
        """
        Turn ALL bound channels OFF (as a command).
        """
        logger.info(f"Turning OFF LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.off"})
        for ch in self.channels:
            ch.off()
            
    def press(self) -> None:
        """
        Helper function for when a key is pressed on the physical keypad. Varies by switch config.
        """
        logger.info(f"Pressing LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.press"})
        # For now, just toggle. Could be extended for momentary, etc.
        
        match self.type:
            case SwitchType.TOGGLE:
                self.toggle()
            case SwitchType.MOMENTARY:
                self.on()
            case SwitchType.CYCLE:
                self.cycle()
    def release(self) -> None:
        """
        Helper function for when a key is released on the physical keypad. Varies by switch config.
        """
        logger.info(f"Releasing LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.release"})
        match self.type:
            case SwitchType.MOMENTARY:
                self.off()
            case _:
                pass  # No action for TOGGLE or CYCLE on release

    def toggle(self) -> None:
        # TODO: you can base this on get_state()
        if self.type is SwitchType.CYCLE and self.cycles:
            self.cycle()
        else:
            # simple toggle: if "mostly off" -> on, else -> off
            if self.is_on():
                self.off()
            else:
                self.on()
    
    def cycle(self) -> None:
        """Advance to next step in cycles array."""
        if not self.cycles:
            logger.warning(
                f"LogicalSwitch {self.name} has no cycles defined; cannot cycle",   
                extra={"origin": "switches.LogicalSwitch.cycle"},
            )
            return

        self._cycle_index = (self._cycle_index + 1) % len(self.cycles)
        step = self.cycles[self._cycle_index]
        logger.info(
            f"Cycling LogicalSwitch {self.name} to step {self._cycle_index}",
            extra={"origin": "switches.LogicalSwitch.cycle"},
        )
        # selected on
        for ch in step:
            ch.on()
        # non-selected off
        other_channels = set(self.channels) - set(step)
        for ch in other_channels:
            ch.off()

    def get_state(self) -> SwitchState:
        """
        Derive current state from the underlying ChannelState objects.

        Rules:
        - If any channel has fault -> FAULT.
        - Else if all off -> OFF.
        - Else if all on -> ON.
        - Else -> PARTIAL.
        """
        states = list(self.iter_channel_states())
        if not states:
            return SwitchState.UNKNOWN

        # Fault overrides everything
        for st in states:
            if st.health in (ChannelHealth.SHORT, ChannelHealth.OPEN):
                return SwitchState.FAULT

        ons = [st.actual_on for st in states]
        if all(not v for v in ons):
            return SwitchState.OFF
        if all(ons):
            return SwitchState.ON
        return SwitchState.PARTIAL

    def is_on(self) -> bool:
        states = [ch.state() for ch in self.channels]
        return any(s.actual_on for s in states)

    def iter_channel_states(self) -> Iterable[ChannelState]:
        """
        Convenience for UI / diagnostics: yield ChannelState for each binding.
        """
        for b in self._bindings:
            pcm = self._pcm.get_pcm(b.node_id)
            if pcm is None:
                continue
            yield pcm.get_channel_state(b.channel_index)

    def __repr__(self) -> str:
        return f"<LogicalSwitch name={self.name!r} bindings={len(self._bindings)}>"


# ---------- Switch Manager ----------
class SwitchManager:
    def __init__(self):
        self._switches: dict[str, LogicalSwitch] = {}

    def add(self, switch: LogicalSwitch) -> LogicalSwitch:
        self._switches[switch.name] = switch
        return switch

    def get(self, name: str) -> Optional[LogicalSwitch]:
        return self._switches.get(name)

    # optional helpers
    def __iter__(self):
        return iter(self._switches.values())


class ButtonLEDMode(Enum):
    STATIC = auto()
    FOLLOW_SWITCH_STATE = auto()
    FOLLOW_CYCLE_STEP = auto()
    BLINK = auto()
    # etc.


class Button:
    def __init__(self, id: int, label: str = ""):
        self.id = id
        self.label = label or f"BTN{id}"
        self.bound_switch: LogicalSwitch | None = None
        self.led_mode: ButtonLEDMode = ButtonLEDMode.FOLLOW_SWITCH_STATE
        # some representation of color, flashing pattern, etc.
        self.color = (0, 0, 0)

    def on_press(self):
        """Called when the *hardware* tells us this button was pressed."""
        if self.bound_switch:
            self.bound_switch.toggle()

    def update_led_for_switch_state(self):
        """Update color/flashing based on bound switch state."""
        if not self.bound_switch:
            self.color = (0, 0, 0)
            return

        state = self.bound_switch.is_on()
        # Example simple rule:
        # - off -> dim white
        # - on -> bright green
        # - fault/partial -> red/amber (if you expose those)
        # Here you'd call into the actual hardware driver.
