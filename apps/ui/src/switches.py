# switches.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Iterable, Optional
import logging

from .pcm import PCMManager, ChannelState, ChannelHealth  # adjust import as needed

logger = logging.getLogger("control_head.switches")


# ---------- Models ----------

@dataclass(frozen=True)
class ChannelBinding:
    """
    Links a logical switch to a specific PCM channel.

    Keeping this small & serializable so it can come from config.
    """
    node_id: int
    channel_index: int
    # Optional fields for future use (pwm, role, etc.)
    label: Optional[str] = None
    pwm_capable: bool = False


class SwitchState(Enum):
    UNKNOWN = auto()
    OFF = auto()
    ON = auto()
    PARTIAL = auto()
    FAULT = auto()


# ---------- Logical Switch ----------

class LogicalSwitch:
    """
    Represents a real-world thing like 'Front Lights' that controls
    one or more PCM channels.

    - Does NOT talk CAN directly.
    - Delegates to PCMManager.
    - Computes its state based on underlying ChannelState values.
    """

    def __init__(
        self,
        name: str,
        bindings: List[ChannelBinding],
        pcm_manager: PCMManager,
    ):
        self.name = name
        self._bindings = bindings
        self._pcm = pcm_manager

        # Switch does not own timers or patterns; it is a thin abstraction.
        logger.info(
            f"LogicalSwitch created: {self.name} with {len(bindings)} bindings",
            extra={"origin": "switches.LogicalSwitch.__init__"},
        )

    # ----- Public API -----

    def on(self) -> None:
        """
        Turn ALL bound channels ON (as a command).
        """
        # Implementation will loop bindings and call PCMManager.set_channel_on(...)
        ...

    def off(self) -> None:
        """
        Turn ALL bound channels OFF (as a command).
        """
        ...

    def toggle(self) -> None:
        """
        Toggle behavior:
        - If all ON -> all OFF.
        - Else (OFF/PARTIAL/UNKNOWN) -> all ON.
        """
        ...

    def get_state(self) -> SwitchState:
        """
        Derive current state from the underlying ChannelState objects.
        Rules (to be implemented):
        - If any channel has fault -> FAULT.
        - Else if all off -> OFF.
        - Else if all on -> ON.
        - Else -> PARTIAL.
        """
        return SwitchState.UNKNOWN

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
    """
    Owns all LogicalSwitch instances.

    - Bridges high-level UI / config to PCMManager.
    - Provides simple methods: set_switch_on/off/toggle, listing, lookup.
    """

    def __init__(self, pcm_manager: PCMManager):
        self._pcm = pcm_manager
        self._switches: Dict[str, LogicalSwitch] = {}
        logger.info("SwitchManager created", extra={"origin": "switches.SwitchManager.__init__"})

    # ----- Registration -----

    def register_switch(
        self,
        name: str,
        bindings: List[ChannelBinding],
    ) -> LogicalSwitch:
        """
        Create & register a LogicalSwitch with the given bindings.
        Typically driven by config at startup.
        """
        # Optionally validate for unknown PCMs/channels.
        switch = LogicalSwitch(name=name, bindings=bindings, pcm_manager=self._pcm)
        self._switches[name] = switch
        return switch

    def get_switch(self, name: str) -> Optional[LogicalSwitch]:
        return self._switches.get(name)

    def all_switches(self) -> List[LogicalSwitch]:
        return list(self._switches.values())

    # ----- Convenience API for UI -----

    def set_switch_on(self, name: str) -> None:
        sw = self._switches.get(name)
        if sw:
            sw.on()

    def set_switch_off(self, name: str) -> None:
        sw = self._switches.get(name)
        if sw:
            sw.off()

    def toggle_switch(self, name: str) -> None:
        sw = self._switches.get(name)
        if sw:
            sw.toggle()

    def get_switch_state(self, name: str) -> Optional[SwitchState]:
        sw = self._switches.get(name)
        if not sw:
            return None
        return sw.get_state()
