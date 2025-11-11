# effects.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Iterable
import logging
import time

from pcm import PCMManager
from switches import SwitchManager, LogicalSwitch, SwitchState
from patterns import Pattern, PatternTarget, PatternTargetType

logger = logging.getLogger("control_head.effects")


# ---------- Ownership Model ----------

@dataclass
class ChannelOwner:
    """
    Tracks who currently 'owns' a given channel and what state they last applied.
    """
    owner_id: str     # e.g. "pattern:EMERGENCY_FRONT" or "switch:FrontLights"
    value: Union[bool, float]


# ---------- Pattern / Effects Engine ----------

class PatternEngine:
    """
    Runs one or more active Patterns and applies their outputs to PCM channels
    (optionally via switches) with clear ownership rules.

    - No internal timers: caller supplies 'now' via tick().
    - Intended to be driven by a QTimer or similar in the UI layer.
    """

    def __init__(
        self,
        pcm_manager: PCMManager,
        switch_manager: Optional[SwitchManager] = None,
    ):
        self._pcm = pcm_manager
        self._switches = switch_manager

        self._patterns: Dict[str, Pattern] = {}         # all known
        self._active: Dict[str, Pattern] = {}           # active pattern_name -> Pattern
        self._channel_owners: Dict[tuple, ChannelOwner] = {}  # (node_id, ch) -> owner

        logger.info("PatternEngine created", extra={"origin": "effects.PatternEngine.__init__"})

    # ----- Registration -----

    def register_pattern(self, pattern: Pattern) -> None:
        """
        Register a pattern by its name.
        Does not activate it.
        """
        self._patterns[pattern.name] = pattern

    # ----- Control API -----

    def start_pattern(self, name: str) -> None:
        """
        Activate a previously registered pattern.
        """
        pattern = self._patterns.get(name)
        if not pattern:
            logger.warning(
                f"Attempted to start unknown pattern '{name}'",
                extra={"origin": "effects.PatternEngine.start_pattern"},
            )
            return
        self._active[name] = pattern

    def stop_pattern(self, name: str) -> None:
        """
        Deactivate a running pattern and release its ownership.
        """
        if name in self._active:
            del self._active[name]
            # Channel ownership cleanup for that pattern will be handled in next tick.
            # (Implementation detail to be filled in.)
        else:
            logger.debug(
                f"Pattern '{name}' not active",
                extra={"origin": "effects.PatternEngine.stop_pattern"},
            )

    def stop_all(self) -> None:
        """
        Stop all active patterns and release all pattern ownerships.
        """
        self._active.clear()
        self._channel_owners.clear()
        # Optionally: restore channels/switches to some default/off state.

    # ----- Main tick (to be called by UI/event loop) -----

    def tick(self, now_s: Optional[float] = None) -> None:
        """
        Evaluate all active patterns at time 'now_s' and apply results.

        Caller (Qt, etc.) should call this periodically via a timer.
        """
        if now_s is None:
            now_s = time.monotonic()

        # 1. Collect desired states from all active patterns.
        # 2. Resolve ownership & priority for each target.
        # 3. Call PCMManager / SwitchManager for actual changes (only if changed).
        ...
