# switches.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Iterable, Optional
import logging

from pcm import PCMManager, ChannelState, ChannelHealth  # adjust import as needed

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
    
class SwitchType(Enum):
    TOGGLE = auto()
    MOMENTARY = auto()
    CYCLE = auto()


# ---------- Logical Switch ----------

class LogicalSwitch:
    def __init__(
        self,
        name: str,
        bindings: List[ChannelBinding],
        pcm_manager: PCMManager,
        switch_type: SwitchType = SwitchType.TOGGLE,
        cycles: Optional[List[List[ChannelBinding]]] = None,
    ):
        self.name = name
        self._bindings = bindings
        self._pcm = pcm_manager
        self.switch_type = switch_type

        # For CYCLE behavior
        self._cycles: List[List[ChannelBinding]] = cycles or []
        self._cycle_index: int = 0  # index into self._cycles

        logger.info(
            f"LogicalSwitch created: {self.name} with {len(bindings)} bindings "
            f"(type={self.switch_type}, cycles={len(self._cycles)})",
            extra={"origin": "switches.LogicalSwitch.__init__"},
        )

    # ----- Public API -----

    def on(self) -> None:
        """
        Turn ALL bound channels ON (as a command).
        """
        logger.info(f"Turning ON LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.on"})
        for binding in self._bindings:
            pcm = self._pcm.get_pcm(binding.node_id)
            if pcm is None:
                logger.warning(
                    f"PCM node {binding.node_id} not found for switch {self.name}",
                    extra={"origin": "switches.LogicalSwitch.on"},
                )
                continue
            pcm.set_channel_on(binding.channel_index)
        # Implementation will loop bindings and call PCMManager.set_channel_on(...)
        ...

    def off(self) -> None:
        """
        Turn ALL bound channels OFF (as a command).
        """
        logger.info(f"Turning OFF LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.off"})
        for binding in self._bindings:
            pcm = self._pcm.get_pcm(binding.node_id)
            if pcm is None:
                logger.warning(
                    f"PCM node {binding.node_id} not found for switch {self.name}",
                    extra={"origin": "switches.LogicalSwitch.off"},
                )
                continue
            pcm.set_channel_off(binding.channel_index)
            
    def press(self) -> None:
        """
        Helper function for when a key is pressed on the physical keypad. Varies by switch config.
        """
        logger.info(f"Pressing LogicalSwitch: {self.name}", extra={"origin": "switches.LogicalSwitch.press"})
        # For now, just toggle. Could be extended for momentary, etc.
        
        match self.switch_type:
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
        match self.switch_type:
            case SwitchType.MOMENTARY:
                self.off()
            case _:
                pass  # No action for TOGGLE or CYCLE on release

    def toggle(self) -> None:
        """
        Toggle behavior:
        - If all ON -> all OFF.
        - Else (OFF/PARTIAL/UNKNOWN) -> all ON.
        """
        current_state = self.get_state()
        logger.info(f"Toggling LogicalSwitch: {self.name} from state {current_state}", extra={"origin": "switches.LogicalSwitch.toggle"})
        if current_state == SwitchState.ON:
            self.off()
        else:
            self.on()
        ...
    
    def cycle(self) -> None:
        """
        Cycle behavior (for multi-state switches):

        Example with cycles:
            [
                [],  # all off
                [front_left],
                [front_left, front_right],
                [front_left, front_right, grill_light],
            ]

        Behavior:
        - Each press -> advance to next step.
        - First, all bound channels are turned OFF.
        - Then only the channels in the current cycle step are turned ON.
        """
        if not self._cycles:
            # No explicit cycles configured; fallback to toggle
            logger.debug(
                f"No cycles defined for {self.name}, falling back to toggle()",
                extra={"origin": "switches.LogicalSwitch.cycle"},
            )
            # self.toggle()
            return
        
        # Advance cycle index
        self._cycle_index = (self._cycle_index + 1) % len(self._cycles)
        step_bindings = self._cycles[self._cycle_index]
        
        logger.info(
            f"Cycling LogicalSwitch: {self.name} to cycle index: {self._cycle_index} of {len(self._cycles)}",
            extra={"origin": "switches.LogicalSwitch.cycle"},
        )

        # # Turn everything this switch owns OFF
        # for binding in self._bindings:
        #     pcm = self._pcm.get_pcm(binding.node_id)
        #     if pcm is None:
        #         logger.warning(
        #             f"PCM node {binding.node_id} not found for switch {self.name}",
        #             extra={"origin": "switches.LogicalSwitch.cycle"},
        #         )
        #         continue
        #     pcm.set_channel_off(binding.channel_index)

        # Turn ON the bindings in the current cycle step
        for binding in step_bindings:
            pcm = self._pcm.get_pcm(binding.node_id)
            if pcm is None:
                logger.warning(
                    f"PCM node {binding.node_id} not found for switch {self.name}",
                    extra={"origin": "switches.LogicalSwitch.cycle"},
                )
                continue
            pcm.set_channel_on(binding.channel_index)
        
        # Turn off any bindings not in the current cycle step
        for binding in self._bindings:
            if binding in step_bindings:
                continue
            pcm = self._pcm.get_pcm(binding.node_id)
            if pcm is None:
                logger.warning(
                    f"PCM node {binding.node_id} not found for switch {self.name}",
                    extra={"origin": "switches.LogicalSwitch.cycle"},
                )
                continue
            pcm.set_channel_off(binding.channel_index)
            


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
        type: SwitchType = SwitchType.TOGGLE,
        cycles: Optional[List[List[ChannelBinding]]] = None,
    ) -> LogicalSwitch:
        """
        Create & register a LogicalSwitch with the given bindings.

        `type` controls behavior (TOGGLE / MOMENTARY / CYCLE).
        `cycles` is an optional list-of-lists of ChannelBindings
        describing each cycle step.
        """
        switch = LogicalSwitch(
            name=name,
            bindings=bindings,
            pcm_manager=self._pcm,
            switch_type=type,
            cycles=cycles,
        )
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
