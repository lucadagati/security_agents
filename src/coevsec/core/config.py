"""Experiment configuration schema (proposal section 28).

A single YAML file fully specifies a reproducible experiment: models, number of
agents, topology, capabilities, memory level, communication, seed, episode
count, environment backend and budget. Parsed and validated with pydantic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from coevsec.core.types import AdaptationLevel


class LLMConfig(BaseModel):
    """LLM backend selection. ``mock`` and ``heuristic`` policies ignore this."""

    provider: Literal["ollama", "mock"] = "ollama"
    base_url: str | None = None  # falls back to COEVSEC_OLLAMA_BASE_URL
    model: str | None = None  # falls back to COEVSEC_OLLAMA_MODEL
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout_s: float = 120.0

    def resolved_base_url(self) -> str:
        return self.base_url or os.environ.get("COEVSEC_OLLAMA_BASE_URL", "http://localhost:11434")

    def resolved_model(self) -> str:
        return self.model or os.environ.get("COEVSEC_OLLAMA_MODEL", "llama3.1:8b")


class PolicyConfig(BaseModel):
    """How an agent chooses actions.

    ``kind`` selects the policy implementation:
        rule_based  fixed heuristic (baselines B1/B2, proposal section 22)
        heuristic   parameterised heuristic that can adapt (no LLM required)
        llm         LLM-driven policy via the configured backend
        hybrid      LLM primary with heuristic takeover when stuck (B3–B5 fix)
    """

    kind: Literal["rule_based", "heuristic", "llm", "hybrid"] = "heuristic"
    # Baseline knobs for heuristic policies; interpreted per role.
    stealth: float = 0.5  # initial preference for low-noise actions (0..1)
    aggression: float = 0.5  # initial preference for direct high-value actions
    params: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """A single agent or a homogeneous group of ``count`` agents."""

    id_prefix: str
    role: Literal["attacker", "defender"]
    count: int = 1
    goal: str = ""
    adaptation: AdaptationLevel = AdaptationLevel.EPISODIC
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    # Which behaviours the agent is *explicitly* instructed to use. Used by the
    # emergence detector (section 25) to distinguish encoded vs emergent.
    encoded_behaviours: list[str] = Field(default_factory=list)
    # Per-episode budget: max turns the agent may act.
    max_turns: int = 20
    token_budget: int = 20000


class EnvironmentConfig(BaseModel):
    """Cyber environment selection and parameters (proposal section 10)."""

    backend: Literal["sim", "k8s"] = "sim"
    hosts: int = 3  # number of service hosts between gateway and data store
    vulnerabilities_per_host: int = 2
    detection_base_rate: float = 0.15  # base per-turn detection probability
    params: dict[str, Any] = Field(default_factory=dict)


class InteractionConfig(BaseModel):
    """Interaction graph / communication settings (proposal section 11, 16)."""

    topology: Literal["none", "static", "graph", "dynamic"] = "none"
    communication: Literal["none", "direct", "graph"] = "none"
    communication_cost: float = 0.5
    allow_coalitions: bool = False


class ExperimentConfig(BaseModel):
    """Top-level experiment specification."""

    name: str
    description: str = ""
    seed: int = 0
    episodes: int = 10
    max_turns: int = 20  # global cap on turns per episode

    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    agents: list[AgentConfig] = Field(default_factory=list)

    # ESR (section 19) requires paired isolation runs; when true the controller
    # also runs each population in isolation to estimate P(failure|isolation).
    measure_esr: bool = False

    output_dir: str = "runs"

    @model_validator(mode="after")
    def _check_agents(self) -> "ExperimentConfig":
        if not self.agents:
            raise ValueError("experiment must define at least one agent group")
        roles = {a.role for a in self.agents}
        if "attacker" not in roles or "defender" not in roles:
            raise ValueError("experiment needs at least one attacker and one defender group")
        return self

    def expand_agents(self) -> list[dict[str, Any]]:
        """Expand agent groups into concrete per-agent specs with unique ids."""
        out: list[dict[str, Any]] = []
        for group in self.agents:
            for i in range(group.count):
                agent_id = group.id_prefix if group.count == 1 else f"{group.id_prefix}_{i:02d}"
                out.append({"agent_id": agent_id, "group": group})
        return out

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        data = yaml.safe_load(Path(path).read_text())
        return cls.model_validate(data)

    def config_hash(self) -> str:
        """Stable hash of the config for reproducibility bookkeeping."""
        import hashlib
        import json

        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
