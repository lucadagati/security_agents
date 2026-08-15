"""Experiment controller: drives the co-evolutionary loop (proposal section 12).

For each episode: reset -> interact (turn loop) -> outcome -> experience ->
strategy adaptation -> next episode. Fully seeded for reproducibility; every
step is logged to telemetry and per-episode metrics are accumulated.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from coevsec.agents.factory import make_agent
from coevsec.agents.shared.agent import Agent
from coevsec.core.config import ExperimentConfig
from coevsec.core.taxonomy import CATEGORY_TO_BEHAVIOURS
from coevsec.core.types import Action, Role
from coevsec.environment import make_environment
from coevsec.interaction import InteractionGraph, MessageBus, detect_coalitions
from coevsec.metrics import (
    attack_success_rate,
    behavioral_novelty,
    coalition_rate,
    coevolutionary_pressure,
    deception_rate,
    detection_rate,
    emergent_security_risk,
    mean_cost,
    recovery_time,
    strategy_diversity,
)
from coevsec.telemetry import TelemetryWriter, TrajectoryRecord


@dataclass
class RunResult:
    episodes: list[dict] = field(default_factory=list)
    attacker_sigs: list[dict[str, float]] = field(default_factory=list)
    defender_sigs: list[dict[str, float]] = field(default_factory=list)
    per_episode_behaviours: list[set[str]] = field(default_factory=list)
    final_signatures: list[dict[str, float]] = field(default_factory=list)


def _mean_signatures(sigs: list[dict[str, float]]) -> dict[str, float]:
    if not sigs:
        return {}
    keys: set[str] = set()
    for s in sigs:
        keys |= set(s)
    return {k: sum(s.get(k, 0.0) for s in sigs) / len(sigs) for k in keys}


class ExperimentController:
    def __init__(self, cfg: ExperimentConfig) -> None:
        self.cfg = cfg

    # ------------------------------------------------------------------ build
    def _build_agents(self, seed: int) -> list[Agent]:
        agents: list[Agent] = []
        for spec in self.cfg.expand_agents():
            agents.append(make_agent(spec["agent_id"], spec["group"], seed))
        return agents

    def _build(self, seed: int, interaction_override: str | None = None):
        rng = random.Random(seed)
        env = make_environment(self.cfg.environment, rng)
        agents = self._build_agents(seed)
        for a in agents:
            env.register_agent(a.agent_id, a.role)
        comm = interaction_override if interaction_override is not None else self.cfg.interaction.communication
        bus = MessageBus(communication=comm, cost=self.cfg.interaction.communication_cost)
        graph = InteractionGraph(topology=self.cfg.interaction.topology)
        for a in agents:
            graph.add_agent(a.agent_id, a.role.value)
        graph.initialise()
        return env, agents, bus, graph

    # -------------------------------------------------------------- run loop
    def _run_config(
        self, seed: int, writer: TelemetryWriter | None, interaction_override: str | None = None
    ) -> RunResult:
        env, agents, bus, graph = self._build(seed, interaction_override)
        roles = {a.agent_id: a.role.value for a in agents}
        result = RunResult()

        for ep in range(self.cfg.episodes):
            ep_seed = seed + ep
            env.reset(ep_seed)
            for a in agents:
                a.reset_episode()
            bus.reset_episode()

            deceptive_actions = 0
            total_actions = 0
            ep_categories: dict[str, set[str]] = {"attacker": set(), "defender": set()}

            for turn in range(self.cfg.max_turns):
                for agent in agents:
                    if not agent.can_act():
                        continue
                    obs = env.observe(agent.agent_id)
                    peers = [
                        {"id": other.agent_id, "role": other.role.value}
                        for other in agents
                        if other.agent_id != agent.agent_id
                        and graph.can_send(agent.agent_id, other.agent_id, bus.communication)
                    ]
                    obs.data["peers"] = peers
                    if bus.enabled():
                        inbox = bus.inbox_text(agent.agent_id)
                        if inbox:
                            obs.text = obs.text + "\n\n" + inbox
                    action = agent.decide(obs, env.available_tools(agent.role))

                    if action.tool == "communicate":
                        recipient = str(action.params.get("to", ""))
                        if bus.enabled() and graph.can_send(agent.agent_id, recipient, bus.communication):
                            bus.send(agent.agent_id, recipient,
                                     str(action.params.get("content", "")), turn)
                            env.cost[agent.agent_id] = env.cost.get(agent.agent_id, 0.0) + bus.cost
                        else:
                            action = Action(agent_id=agent.agent_id, tool="wait",
                                            rationale="communication not permitted")

                    result_step = env.step(action)
                    agent.learn(action, result_step)

                    total_actions += 1
                    cat = _category(env, action.tool)
                    ep_categories[agent.role.value].add(cat)
                    if _is_deceptive(agent.role, action, obs.data):
                        deceptive_actions += 1

                    if writer is not None:
                        writer.log_step(TrajectoryRecord(
                            episode=ep, turn=turn, agent=agent.agent_id, role=agent.role.value,
                            observation=obs.text[:500], action=action.tool, params=action.params,
                            target=action.target, reason=action.rationale,
                            result=str(result_step.detail)[:200], success=result_step.success,
                            strategy=action.strategy, memory_update="",
                            cost=result_step.cost,
                        ))

                env.end_turn()
                if self.cfg.interaction.topology == "dynamic":
                    graph.set_edges_from_counts(bus.counts)
                graph.snapshot(turn)

                if env.objective_met():
                    break

            summary = env.episode_summary()
            summary["episode"] = ep
            summary["deceptive_actions"] = deceptive_actions
            summary["total_actions"] = total_actions

            coalitions = []
            if self.cfg.interaction.allow_coalitions:
                coalitions = [sorted(c) for c in detect_coalitions(bus.counts, roles)]
            summary["coalitions"] = coalitions
            if graph.snapshots:
                summary["graph_density"] = graph.snapshots[-1]["density"]
                summary["graph_edges"] = graph.snapshots[-1]["edges"]

            for a in agents:
                a.end_episode(summary)

            att_sig = _mean_signatures(
                [a.strategy_signature() for a in agents if a.role == Role.ATTACKER])
            def_sig = _mean_signatures(
                [a.strategy_signature() for a in agents if a.role == Role.DEFENDER])
            result.attacker_sigs.append(att_sig)
            result.defender_sigs.append(def_sig)

            behaviours: set[str] = set()
            for role_cats in ep_categories.values():
                for c in role_cats:
                    behaviours |= CATEGORY_TO_BEHAVIOURS.get(c, set())
            result.per_episode_behaviours.append(behaviours)

            summary["attacker_strategy"] = att_sig
            summary["defender_strategy"] = def_sig
            result.episodes.append(summary)
            if writer is not None:
                writer.log_episode(summary)

        result.final_signatures = [a.strategy_signature() for a in agents]
        env.teardown()
        return result

    # --------------------------------------------------------------- public
    def run(self) -> dict[str, Any]:
        writer = TelemetryWriter(self.cfg.output_dir, self.cfg.name,
                                 self.cfg.config_hash(), self.cfg.seed)
        writer.write_config(self.cfg.model_dump(mode="json"))

        main = self._run_config(self.cfg.seed, writer)
        aggregate = self._aggregate(main)

        # ESR (section 19) requires a paired isolation run with communication off.
        if self.cfg.measure_esr:
            isolation = self._run_config(self.cfg.seed, writer=None, interaction_override="none")
            asr_int = attack_success_rate(main.episodes)
            asr_iso = attack_success_rate(isolation.episodes)
            aggregate["esr"] = emergent_security_risk(asr_int, asr_iso)
            aggregate["asr_isolation"] = asr_iso

        writer.write_summary(aggregate)
        writer.close()
        aggregate["run_dir"] = str(writer.run_dir)
        return aggregate

    def _aggregate(self, r: RunResult) -> dict[str, Any]:
        eps = r.episodes
        return {
            "name": self.cfg.name,
            "episodes": len(eps),
            "attack_success_rate": attack_success_rate(eps),
            "detection_rate": detection_rate(eps),
            "attacker_cost": mean_cost(eps, "attacker_cost"),
            "defender_cost": mean_cost(eps, "defender_cost"),
            "detection_cost": mean_cost(eps, "detection_cost"),
            "recovery_time": recovery_time(eps),
            "coalition_rate": coalition_rate(eps),
            "deception_rate": deception_rate(eps),
            "attacker_strategy_diversity": strategy_diversity(r.attacker_sigs),
            "defender_strategy_diversity": strategy_diversity(r.defender_sigs),
            "behavioral_novelty": behavioral_novelty(r.per_episode_behaviours),
            "coevolutionary_pressure": coevolutionary_pressure(r.attacker_sigs, r.defender_sigs),
            "mean_graph_density": (
                sum(e.get("graph_density", 0.0) for e in eps) / len(eps) if eps else 0.0
            ),
        }


def _category(env, tool_name: str) -> str:
    t = env.tools.get(tool_name)
    return t.category if t else "misc"


def _is_deceptive(role: Role, action: Action, obs_data: dict) -> bool:
    if role == Role.DEFENDER and action.tool == "deploy_decoy":
        return True
    if role == Role.ATTACKER and action.tool == "wait" and obs_data.get("footholds"):
        return True
    return False


def run_experiment(config_path: str) -> dict[str, Any]:
    cfg = ExperimentConfig.from_yaml(config_path)
    return ExperimentController(cfg).run()
