# patterns.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Protocol, Union, Optional
import logging

from .switches import ChannelBinding  # and/or switch names depending on chosen approach

logger = logging.getLogger("control_head.patterns")


# ---------- Targets ----------

class PatternTargetType(Enum):
    CHANNEL = auto()
    SWITCH = auto()  # optional, if you decide to drive LogicalSwitch instead of raw channels


@dataclass(frozen=True)
class PatternTarget:
    """
    Describes what a pattern can drive.
    """
    type: PatternTargetType
    # For CHANNEL:
    node_id: Optional[int] = None
    channel_index: Optional[int] = None
    # For SWITCH:
    switch_name: Optional[str] = None


# ---------- Pattern Interface ----------

class Pattern(Protocol):
    """
    Stateless-ish interface: given 'now', return desired states.

    Concrete patterns implement their own sequences, periods, etc.
    They do NOT send CAN. They only describe intent.
    """

    name: str

    def get_targets(self) -> List[PatternTarget]:
        """
        Return all targets this pattern controls.
        """
        ...

    def evaluate(self, now_s: float) -> Dict[PatternTarget, Union[bool, float]]:
        """
        At the given time (in seconds), return the desired state per target.

        Values:
            bool  -> ON/OFF
            float -> 0.0 - 1.0 for PWM/brightness (future use)
        """
        ...


# ---------- Example stub patterns (outlines only) ----------

class BlinkPattern:
    """
    Simple on/off blink for one or more targets.
    """

    def __init__(
        self,
        name: str,
        targets: List[PatternTarget],
        period_s: float,
        duty_cycle: float = 0.5,
        phase_offset_s: float = 0.0,
    ):
        self.name = name
        self._targets = targets
        self._period_s = period_s
        self._duty = duty_cycle
        self._phase = phase_offset_s

    def get_targets(self) -> List[PatternTarget]:
        return self._targets

    def evaluate(self, now_s: float) -> Dict[PatternTarget, bool]:
        # Implementation to be added:
        # - Compute phase within period.
        # - Return True/False for each target accordingly.
        ...
        return {}


class WigWagPattern:
    """
    Alternate two groups of targets.
    """

    def __init__(
        self,
        name: str,
        group_a: List[PatternTarget],
        group_b: List[PatternTarget],
        interval_s: float,
    ):
        self.name = name
        self._group_a = group_a
        self._group_b = group_b
        self._interval_s = interval_s

    def get_targets(self) -> List[PatternTarget]:
        return self._group_a + self._group_b

    def evaluate(self, now_s: float) -> Dict[PatternTarget, bool]:
        ...
        return {}
