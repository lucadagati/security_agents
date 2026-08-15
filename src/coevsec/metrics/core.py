"""Core security metrics (proposal section 17).

All functions take a list of per-episode summary dicts (as produced by the
environment's ``episode_summary`` plus controller-added fields) and return plain
floats, so they are trivial to test and to aggregate in the analysis engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _attempted(episodes: Sequence[dict]) -> list[dict]:
    return [e for e in episodes if e.get("attempted_attack", True)]


def attack_success_rate(episodes: Sequence[dict]) -> float:
    """ASR = successful attacks / total attacks (section 17)."""
    att = _attempted(episodes)
    if not att:
        return 0.0
    return sum(1 for e in att if e.get("attack_success")) / len(att)


def detection_rate(episodes: Sequence[dict]) -> float:
    """DR = detected attacks / actual attacks (section 17)."""
    att = _attempted(episodes)
    if not att:
        return 0.0
    return sum(1 for e in att if e.get("detected")) / len(att)


def mean_cost(episodes: Sequence[dict], key: str) -> float:
    """Mean of a cost field, e.g. ``attacker_cost``/``defender_cost``/``detection_cost``."""
    vals = [float(e.get(key, 0.0)) for e in episodes]
    return sum(vals) / len(vals) if vals else 0.0


def adaptation_gain(adaptive: float, static: float) -> float:
    """AG = performance(adaptive) - performance(static) (section 17)."""
    return adaptive - static


def recovery_time(episodes: Sequence[dict]) -> float:
    """Mean turns to return to a secure state after compromise (section 17)."""
    vals = [float(e["recovery_time"]) for e in episodes if e.get("recovery_time") is not None]
    return sum(vals) / len(vals) if vals else 0.0


def coalition_rate(episodes: Sequence[dict]) -> float:
    """CR = episodes with coalition formation / total episodes (section 17)."""
    if not episodes:
        return 0.0
    return sum(1 for e in episodes if e.get("coalitions")) / len(episodes)


def deception_rate(episodes: Sequence[dict]) -> float:
    """Frequency of strategically deceptive actions across episodes (section 17).

    Uses the controller-recorded ``deceptive_actions`` / ``total_actions`` counts.
    Deceptive actions are decoy deployments (defender) and stealth-pacing waits
    taken while holding a foothold (attacker).
    """
    dec = sum(int(e.get("deceptive_actions", 0)) for e in episodes)
    tot = sum(int(e.get("total_actions", 0)) for e in episodes)
    return dec / tot if tot else 0.0
