"""Shared value types exchanged between agents, environment and telemetry.

These are deliberately backend-agnostic: the Sim and K8s environments, and the
heuristic and LLM policies, all speak in terms of :class:`Action`,
:class:`Observation` and :class:`StepResult`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Which side of the co-evolutionary game an agent plays on."""

    ATTACKER = "attacker"
    DEFENDER = "defender"


class AdaptationLevel(str, Enum):
    """Three levels of adaptation (proposal section 13).

    STATIC     Level 0 - fixed policy, never changes.
    EPISODIC   Level 1 - adapts within the current episode only.
    PERSISTENT Level 2 - remembers past episodes and changes future behaviour.
    """

    STATIC = "static"
    EPISODIC = "episodic"
    PERSISTENT = "persistent"


class Outcome(str, Enum):
    """Terminal outcome of an episode from the attacker's perspective."""

    ATTACKER_SUCCESS = "attacker_success"
    DEFENDER_SUCCESS = "defender_success"
    TIMEOUT = "timeout"


@dataclass
class Action:
    """A single structured action selected by an agent.

    ``tool`` names a capability the environment exposes; ``params`` are validated
    against that tool's JSON schema. ``rationale`` and ``strategy`` are free-text
    fields captured for post-hoc emergence analysis (they never affect the
    environment, only telemetry).
    """

    agent_id: str
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    target: str | None = None
    rationale: str = ""
    strategy: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "params": self.params,
            "target": self.target,
            "rationale": self.rationale,
            "strategy": self.strategy,
        }


@dataclass
class Event:
    """A log/telemetry event emitted by the environment as a side effect.

    ``noise`` is how detectable the event is (0..1); the defender's monitoring
    accumulates suspicion from noisy events. ``kind`` categorises the event for
    analysis (e.g. ``recon``, ``exploit``, ``detection``).
    """

    kind: str
    source: str
    target: str | None = None
    noise: float = 0.0
    detail: dict[str, Any] = field(default_factory=dict)
    t: float = field(default_factory=time.time)


@dataclass
class Observation:
    """What an agent perceives under partial observability (proposal section 7).

    ``data`` holds structured, machine-usable fields; ``text`` is a rendered
    summary suitable for an LLM prompt. An agent never receives the full
    environment state, only what its role and prior actions have revealed.
    """

    agent_id: str
    turn: int
    data: dict[str, Any] = field(default_factory=dict)
    text: str = ""

    def to_record(self) -> dict[str, Any]:
        return {"turn": self.turn, "data": self.data, "text": self.text}


@dataclass
class StepResult:
    """The result of applying one :class:`Action` to the environment."""

    observation: Observation
    events: list[Event] = field(default_factory=list)
    success: bool = False
    cost: float = 0.0
    detail: dict[str, Any] = field(default_factory=dict)
