"""Co-evolutionary metrics: diversity, novelty, CEP and ESR (sections 17-19)."""

from __future__ import annotations

import math
from collections.abc import Sequence


def strategy_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """Euclidean distance between two strategy signatures over their key union."""
    keys = set(a) | set(b)
    return math.sqrt(sum((a.get(k, 0.0) - b.get(k, 0.0)) ** 2 for k in keys))


def strategy_diversity(signatures: Sequence[dict[str, float]]) -> float:
    """Mean pairwise strategy distance within a set of signatures (section 17)."""
    sigs = list(signatures)
    if len(sigs) < 2:
        return 0.0
    total, n = 0.0, 0
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            total += strategy_distance(sigs[i], sigs[j])
            n += 1
    return total / n if n else 0.0


def behavioral_novelty(per_episode_behaviours: Sequence[set[str]]) -> float:
    """Fraction of episodes that introduce a behaviour not seen before (section 17)."""
    seen: set[str] = set()
    novel_episodes = 0
    for behaviours in per_episode_behaviours:
        if behaviours - seen:
            novel_episodes += 1
        seen |= behaviours
    return novel_episodes / len(per_episode_behaviours) if per_episode_behaviours else 0.0


def coevolutionary_pressure(
    attacker_sigs: Sequence[dict[str, float]],
    defender_sigs: Sequence[dict[str, float]],
) -> float:
    """CEP = mean over episodes of (ΔS_A + ΔS_D)/2 (proposal section 18).

    ΔS is the strategy change between consecutive episodes for each population.
    High CEP indicates an active arms race.
    """
    n = min(len(attacker_sigs), len(defender_sigs))
    if n < 2:
        return 0.0
    total = 0.0
    for t in range(1, n):
        d_a = strategy_distance(attacker_sigs[t], attacker_sigs[t - 1])
        d_d = strategy_distance(defender_sigs[t], defender_sigs[t - 1])
        total += (d_a + d_d) / 2.0
    return total / (n - 1)


def emergent_security_risk(p_fail_interaction: float, p_fail_isolation: float) -> float:
    """ESR = P(failure|interaction) / P(failure|isolation) (proposal section 19).

    A value above 1 means interaction introduces additional security risk.
    Returns +inf if isolation never fails but interaction does.
    """
    if p_fail_isolation <= 0.0:
        return float("inf") if p_fail_interaction > 0.0 else 1.0
    return p_fail_interaction / p_fail_isolation
