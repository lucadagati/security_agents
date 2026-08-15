#!/usr/bin/env python3
"""Multi-seed 1v1 ladder with mean ± 95% CI for ASR, DR, CEP.

Usage:
  python scripts/ladder_ci.py --seeds 100,110,120,130,140,150 --episodes 40
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_notify import _load_dotenv  # noqa: E402

from coevsec.analysis.engine import analyze_run  # noqa: E402
from coevsec.core.config import ExperimentConfig  # noqa: E402
from coevsec.core.types import AdaptationLevel  # noqa: E402
from coevsec.experiments.controller import ExperimentController  # noqa: E402


CELLS = [
    ("static_static", AdaptationLevel.STATIC, "rule_based", AdaptationLevel.STATIC, "rule_based"),
    ("static_adaptive", AdaptationLevel.STATIC, "rule_based", AdaptationLevel.EPISODIC, "heuristic"),
    ("adaptive_static", AdaptationLevel.EPISODIC, "heuristic", AdaptationLevel.STATIC, "rule_based"),
    ("adaptive_adaptive", AdaptationLevel.EPISODIC, "heuristic", AdaptationLevel.EPISODIC, "heuristic"),
    ("persistent_persistent", AdaptationLevel.PERSISTENT, "heuristic", AdaptationLevel.PERSISTENT, "heuristic"),
]


def _cfg(name: str, seed: int, episodes: int, att_ad, att_kind, def_ad, def_kind) -> ExperimentConfig:
    raw = {
        "name": f"ci_{name}_s{seed}",
        "description": f"CI ladder cell {name} seed={seed}",
        "seed": seed,
        "episodes": episodes,
        "max_turns": 20,
        "output_dir": "runs/ci",
        "environment": {
            "backend": "sim",
            "hosts": 3,
            "vulnerabilities_per_host": 2,
            "detection_base_rate": 0.15,
        },
        "interaction": {"topology": "none", "communication": "none"},
        "agents": [
            {
                "id_prefix": "attacker",
                "role": "attacker",
                "adaptation": att_ad.value,
                "policy": {"kind": att_kind, "stealth": 0.3},
                "encoded_behaviours": [
                    "reconnaissance", "privilege_escalation", "resource_targeting",
                ],
            },
            {
                "id_prefix": "defender",
                "role": "defender",
                "adaptation": def_ad.value,
                "policy": {"kind": def_kind, "stealth": 0.4},
                "encoded_behaviours": ["adaptive_monitoring", "dynamic_isolation"],
            },
        ],
    }
    return ExperimentConfig.model_validate(raw)


def _mean_ci(xs: list[float], z: float = 1.96) -> dict:
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"), "ci95": float("nan")}
    mean = sum(xs) / n
    if n == 1:
        return {"n": 1, "mean": mean, "std": 0.0, "ci95": 0.0}
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    std = math.sqrt(var)
    ci = z * std / math.sqrt(n)
    return {"n": n, "mean": mean, "std": std, "ci95": ci, "lo": mean - ci, "hi": mean + ci}


def main() -> int:
    _load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", default="100,110,120,130,140,150")
    p.add_argument("--episodes", type=int, default=40)
    p.add_argument("--out", default="runs/ci/ladder_ci.json")
    args = p.parse_args()
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]

    per_cell: dict[str, list[dict]] = {c[0]: [] for c in CELLS}
    for seed in seeds:
        for name, att_ad, att_kind, def_ad, def_kind in CELLS:
            print(f"running {name} seed={seed} …", flush=True)
            cfg = _cfg(name, seed, args.episodes, att_ad, att_kind, def_ad, def_kind)
            agg = ExperimentController(cfg).run()
            if agg.get("run_dir"):
                analyze_run(agg["run_dir"])
            per_cell[name].append(agg)

    report = {"seeds": seeds, "episodes": args.episodes, "cells": {}}
    lines = [
        "# Ladder multi-seed confidence intervals",
        f"seeds={seeds} episodes={args.episodes}",
        "",
        "| cell | ASR mean±CI95 | DR mean±CI95 | CEP mean±CI95 |",
        "|---|---:|---:|---:|",
    ]
    for name, rows in per_cell.items():
        asr = _mean_ci([r["attack_success_rate"] for r in rows])
        dr = _mean_ci([r["detection_rate"] for r in rows])
        cep = _mean_ci([r["coevolutionary_pressure"] for r in rows])
        report["cells"][name] = {"asr": asr, "dr": dr, "cep": cep, "runs": [
            {"seed": seeds[i], "asr": rows[i]["attack_success_rate"],
             "dr": rows[i]["detection_rate"], "cep": rows[i]["coevolutionary_pressure"],
             "run_dir": rows[i].get("run_dir")}
            for i in range(len(rows))
        ]}
        lines.append(
            f"| {name} | {asr['mean']:.3f}±{asr['ci95']:.3f} | "
            f"{dr['mean']:.3f}±{dr['ci95']:.3f} | {cep['mean']:.3f}±{cep['ci95']:.3f} |"
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    md = out.with_suffix(".md")
    md.write_text("\n".join(lines) + "\n")
    print(md.read_text())
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
