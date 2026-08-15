"""Agent memory implementations realising the three adaptation levels.

Memory feeds *context* into the policy. The distinction between episodic and
persistent memory is the central lever behind the proposal's core hypothesis
(section 13): persistent cross-episode memory should yield stronger strategic
adaptation than episodic memory alone.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    turn: int
    action: str
    result: str
    note: str = ""


class Memory(abc.ABC):
    """Abstract memory store."""

    @abc.abstractmethod
    def record(self, entry: MemoryEntry) -> None: ...

    @abc.abstractmethod
    def context(self) -> str:
        """Return a text block the policy can condition on."""

    @abc.abstractmethod
    def reset_episode(self) -> None: ...

    @abc.abstractmethod
    def end_episode(self, summary: dict[str, Any]) -> None: ...


class NullMemory(Memory):
    """Level 0 - remembers nothing. Used by static agents."""

    def record(self, entry: MemoryEntry) -> None:  # noqa: D401
        return

    def context(self) -> str:
        return ""

    def reset_episode(self) -> None:
        return

    def end_episode(self, summary: dict[str, Any]) -> None:
        return


class EpisodicMemory(Memory):
    """Level 1 - remembers within the current episode only."""

    def __init__(self, window: int = 8) -> None:
        self.window = window
        self._entries: list[MemoryEntry] = []

    def record(self, entry: MemoryEntry) -> None:
        self._entries.append(entry)

    def context(self) -> str:
        recent = self._entries[-self.window :]
        if not recent:
            return ""
        lines = ["Recent actions this episode:"]
        lines += [f"  t{e.turn}: {e.action} -> {e.result}" for e in recent]
        return "\n".join(lines)

    def reset_episode(self) -> None:
        self._entries = []

    def end_episode(self, summary: dict[str, Any]) -> None:
        return


class PersistentMemory(Memory):
    """Level 2 - keeps within-episode detail plus cross-episode reflections.

    At the end of each episode a compact reflection is distilled from the outcome
    and carried into all future episodes, so behaviour can evolve across the run.
    """

    def __init__(self, window: int = 8, max_reflections: int = 12) -> None:
        self.window = window
        self.max_reflections = max_reflections
        self._entries: list[MemoryEntry] = []
        self._reflections: list[str] = []

    def record(self, entry: MemoryEntry) -> None:
        self._entries.append(entry)

    def context(self) -> str:
        parts: list[str] = []
        if self._reflections:
            parts.append("Lessons from previous episodes:")
            parts += [f"  - {r}" for r in self._reflections[-self.max_reflections :]]
        recent = self._entries[-self.window :]
        if recent:
            parts.append("Recent actions this episode:")
            parts += [f"  t{e.turn}: {e.action} -> {e.result}" for e in recent]
        return "\n".join(parts)

    def reset_episode(self) -> None:
        self._entries = []

    def end_episode(self, summary: dict[str, Any]) -> None:
        reflection = self._distill(summary)
        if reflection:
            self._reflections.append(reflection)

    @staticmethod
    def _distill(summary: dict[str, Any]) -> str:
        if summary.get("role") == "attacker":
            if summary.get("attack_success") and not summary.get("detected"):
                return "Stealthy path worked and went undetected; repeat it."
            if summary.get("attack_success") and summary.get("detected"):
                return "Succeeded but was detected; reduce noisy actions next time."
            if summary.get("detected"):
                return "Detected and failed; be stealthier and pace actions."
            return "Failed without reaching the objective; probe more before exploiting."
        # defender
        if summary.get("attack_success"):
            return "Breach occurred; monitor and isolate the deeper layers earlier."
        if summary.get("false_positives", 0) > 0:
            return "Wasted effort on false positives; investigate before isolating."
        return "Held the line; keep monitoring the service and data layers."

    @property
    def reflections(self) -> list[str]:
        return list(self._reflections)


def make_memory(adaptation: str) -> Memory:
    from coevsec.core.types import AdaptationLevel

    if adaptation == AdaptationLevel.STATIC.value:
        return NullMemory()
    if adaptation == AdaptationLevel.EPISODIC.value:
        return EpisodicMemory()
    if adaptation == AdaptationLevel.PERSISTENT.value:
        return PersistentMemory()
    raise ValueError(f"unknown adaptation level: {adaptation}")
