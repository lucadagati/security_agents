# Co-Evolutionary Security of Autonomous AI Agents

A research framework for studying **cybersecurity as a co-evolutionary process** between autonomous attacker and defender agents.

Agents repeatedly interact in a sandboxed cyber environment, adapt from experience, and may develop strategies that were never hard-coded: stealth, deception, coalitions, arms races.

> Security = f(Capabilities, Goals, Interaction, Adaptation, History)
> rather than Security = f(Agent)

## What this repo contains

| Layer | Location | Role |
| --- | --- | --- |
| Agent loop | `src/coevsec/agents/` | Goal + observation + memory → policy → tool |
| LLM backends | `src/coevsec/llm/` | Ollama (L40) + mock; pluggable |
| Simulator | `src/coevsec/environment/sim/` | Fast seedable in-memory cyber range |
| K8s range | `src/coevsec/environment/k8s/` | Same interface, optional `kind` + Helm |
| Interaction | `src/coevsec/interaction/` | Graph `G_t=(V_t,E_t)`, message bus, coalitions |
| Metrics | `src/coevsec/metrics/` | ASR, DR, CEP, ESR, diversity, novelty, … |
| Telemetry | `src/coevsec/telemetry/` | Trajectory JSONL + optional Postgres |
| Controller | `src/coevsec/experiments/` | Co-evolutionary episode loop |
| Analysis | `src/coevsec/analysis/` | Strategy dynamics, emergence tagging |
| Configs | `configs/` | E1–E8 matrix, 1v1 ladder, LLM baselines |

The environment defines **capabilities**. Agent configs define **objectives**. **Strategy** is discovered, not scripted.

## Setup

Python 3.11+ is required. Package management uses `uv`.

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,analysis,postgres]"
cp .env.example .env   # then set COEVSEC_OLLAMA_BASE_URL
```

Ollama is **not** required for the simulator experiments. Heuristic policies (baselines B1/B2) and `llm.provider: mock` run fully offline. Point `COEVSEC_OLLAMA_BASE_URL` at the L40 host when you are ready to run B3–B5.

Optional telemetry database:

```bash
docker compose -f docker/compose.yaml up -d
export COEVSEC_PG_DSN=postgresql://coevsec:coevsec@localhost:5432/coevsec
```

## Run an experiment

Every experiment is a YAML file. The config hash, seed and git SHA are written next to the trajectories.

```bash
python run_experiment.py --config configs/e1.yaml
# or
coevsec run --config configs/e5.yaml
coevsec analyze --run runs/<name>_<hash>
```

### 1-vs-1 adaptation ladder (start here)

The scientifically meaningful first experiment (proposal section 35):

```text
Static vs Static
Static vs Adaptive
Adaptive vs Static
Adaptive vs Adaptive
Persistent vs Persistent
```

```bash
coevsec ladder --configs-dir configs/ladder
```

Then scale with `configs/e4.yaml` (3v3) → `e5.yaml` (5v5) → `e8.yaml` (10v10).

### LLM agents (Ollama / L40)

```bash
export COEVSEC_OLLAMA_BASE_URL=http://<l40-host>:11434
export COEVSEC_OLLAMA_MODEL=llama3.1:8b
coevsec run --config configs/baselines/b4_llm_adaptive.yaml
```

The LLM never executes code. It selects a structured tool; the environment validates parameters against a JSON schema.

### Kubernetes cyber range

The K8s backend implements the same `CyberEnvironment` interface. Game logic stays in the simulator so metrics remain comparable; isolation can be mirrored onto a `kind` cluster.

```bash
# logic-only (no cluster)
coevsec run --config configs/k8s_validate.yaml

# provision a real range (requires kind, kubectl, helm)
# set environment.params.provision: true in the YAML, then:
#   kind create cluster --config src/coevsec/environment/k8s/kind-cluster.yaml
#   helm upgrade --install range src/coevsec/environment/k8s/chart -n range --create-namespace
```

`kind` is not bundled; install it if you want the provisioned range.

## Metrics

| Metric | Meaning |
| --- | --- |
| ASR | Attack success rate |
| DR | Detection rate |
| Adaptation gain | Adaptive performance − static performance |
| CEP | Co-evolutionary pressure `(ΔS_A + ΔS_D)/2` |
| ESR | `P(fail \| interaction) / P(fail \| isolation)` |
| Strategy diversity / novelty | How strategies spread and appear |
| Coalition / deception rate | Emergent social / deceptive behaviour |

A behaviour is tagged **emergent** only if it is not listed in `encoded_behaviours` yet arises consistently from interaction.

## Layout

```
configs/          E1–E8, ladder, LLM baselines
scenarios/        default cyber-range description
docker/           Postgres compose
src/coevsec/      Python package
tests/            unit + integration tests
paper/            IEEE Transactions LaTeX manuscript
runs/             experiment outputs (gitignored)
datasets/         archival trajectories
```

## Reproducibility

```bash
python run_experiment.py --config configs/e5.yaml
```

Each run directory contains `config.json`, `meta.json` (seed, config hash, git SHA), `trajectories.jsonl`, `episodes.jsonl` and `summary.json`.

## IEEE Transactions paper

The journal manuscript lives in [`paper/`](paper/). Build with:

```bash
cd paper && make
```

See [`paper/README.md`](paper/README.md) for venue notes (TDSC / TIFS / TAI) and how to switch the `compsoc` class option.
