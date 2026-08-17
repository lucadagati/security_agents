#!/usr/bin/env python3
"""Seed-level statistics for paper tables (paired tests, effect sizes, ANOVA).

Reads runs/ci/ladder_ci.json and runs/campaign/final_report.json.
Writes analysis_out/paper_stats.json, analysis_out/paper_stats.md, and
paper/figures/generated/stats_*.tex tables.

Usage:
  python scripts/paper_analysis.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scipy import stats  # noqa: E402

FIG_GEN = ROOT / "paper" / "figures" / "generated"

LADDER_PRIMARY = [
    "static_static",
    "static_adaptive",
    "adaptive_static",
    "adaptive_adaptive",
    "persistent_persistent",
    "persistent_static",
    "static_persistent",
    "persistent_adaptive",
    "adaptive_persistent",
]

LADDER_COMPARE = [
    ("static_static", "adaptive_static", "H1", "Adaptive vs.\\ static attacker"),
    ("static_static", "static_adaptive", "H2", "Defender adaptation (static att.)"),
    ("static_static", "persistent_persistent", "CEP", "P/P vs.\\ static/static (CEP adj.)"),
    ("adaptive_adaptive", "persistent_persistent", "L2", "P/P vs.\\ A/A (CEP)"),
]

LLM_COMPARE = [
    ("b3_static", "b4_episodic", "B4 vs.\\ B3 (ASR)"),
    ("b5_persistent", "b4_episodic", "B4 vs.\\ B5 (ASR)"),
    ("b3_static", "b4_episodic", "B4 vs.\\ B3 (DR)"),
]

PRETTY = {
    "static_static": "Static / static",
    "static_adaptive": "Static / adaptive",
    "adaptive_static": "Adaptive / static",
    "adaptive_adaptive": "Adaptive / adaptive",
    "persistent_persistent": "Persistent / persistent",
    "persistent_static": "Persistent / static",
    "static_persistent": "Static / persistent",
    "persistent_adaptive": "Persistent / adaptive",
    "adaptive_persistent": "Adaptive / persistent",
}


def _cohen_d(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = stats.tvar(a, ddof=1), stats.tvar(b, ddof=1)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    if pooled == 0:
        return 0.0
    return (stats.tmean(a) - stats.tmean(b)) / pooled


def _paired_test(a: list[float], b: list[float]) -> dict:
    n = len(a)
    if n != len(b) or n < 2:
        return {"n": n, "t": float("nan"), "p": float("nan"), "cohen_d": float("nan")}
    diffs = [x - y for x, y in zip(a, b)]
    mean_diff = sum(diffs) / n
    if all(abs(d) < 1e-12 for d in diffs):
        t, p, d = 0.0, 1.0, 0.0
    else:
        t, p = stats.ttest_rel(a, b)
        d = _cohen_d(a, b)
    se = stats.sem(diffs) if n > 1 else 0.0
    ci = 1.96 * se
    return {
        "n": n,
        "mean_a": sum(a) / n,
        "mean_b": sum(b) / n,
        "mean_diff": mean_diff,
        "diff_ci95": ci,
        "t": float(t),
        "p": float(p),
        "cohen_d": float(d),
    }


def _seed_series(cell: dict, metric: str) -> list[float]:
    return [float(r[metric]) for r in cell.get("runs", []) if metric in r and r[metric] is not None]


def _dynamics_by_cell(data: dict) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for name, cell in data.get("cells", {}).items():
        counts: dict[str, int] = {}
        for run in cell.get("runs", []):
            cls = run.get("dynamics_class") or "unknown"
            counts[cls] = counts.get(cls, 0) + 1
        out[name] = counts
    return out


def _llm_seed_series(report: dict, label: str, metric: str) -> list[float]:
    rows = []
    for row in report.get("metric_rows", []):
        jid = row.get("job_id", "")
        if not jid.startswith("p1_hybrid_"):
            continue
        parts = jid.split("_")
        lab = "_".join(parts[2:4]) if len(parts) >= 5 else ""
        if lab != label:
            continue
        key = {"ASR": "attack_success_rate", "DR": "detection_rate", "CEP": "coevolutionary_pressure"}[metric]
        if key in row:
            rows.append(float(row[key]))
    return rows


def analyze_ladder(path: Path) -> dict:
    data = json.loads(path.read_text())
    cells = data.get("cells", {})
    out: dict = {
        "source": str(path),
        "seeds": data.get("seeds"),
        "comparisons": {},
        "dynamics_by_cell": _dynamics_by_cell(data),
    }

    for left, right, hid, label in LADDER_COMPARE:
        if left not in cells or right not in cells:
            continue
        key = f"{left}_vs_{right}"
        out["comparisons"][key] = {
            "hypothesis": hid,
            "label": label,
            "dr": _paired_test(_seed_series(cells[left], "dr"), _seed_series(cells[right], "dr")),
            "asr": _paired_test(_seed_series(cells[left], "asr"), _seed_series(cells[right], "asr")),
            "cep_adj": _paired_test(
                _seed_series(cells[left], "cep_adj"), _seed_series(cells[right], "cep_adj")
            ),
        }
    return out


def analyze_campaign(path: Path) -> dict:
    if not path.exists():
        return {"missing": True}
    data = json.loads(path.read_text())
    comparisons = {}
    for left, right, label in LLM_COMPARE:
        metric = "ASR" if "ASR" in label else "DR"
        a = _llm_seed_series(data, left, metric)
        b = _llm_seed_series(data, right, metric)
        if len(a) == len(b) and len(a) >= 2:
            comparisons[f"{left}_vs_{right}_{metric.lower()}"] = {
                "label": label,
                **_paired_test(a, b),
            }
    return {
        "phase1_hybrid_ci": data.get("phase1_hybrid_ci"),
        "phase1_gate_frac": data.get("phase1_gate_frac"),
        "comparisons": comparisons,
    }


def _fmt_p(p: float) -> str:
    if math.isnan(p):
        return "---"
    if p < 0.001:
        return "$<0.001$"
    return f"${p:.3f}$"


def _write_stats_tests(ladder: dict, campaign: dict) -> None:
    rows = []
    for _key, comp in ladder.get("comparisons", {}).items():
        hid = comp["hypothesis"]
        for metric in ("dr", "asr", "cep_adj"):
            r = comp.get(metric, {})
            if r.get("n", 0) < 2:
                continue
        rows.append(
            f"{hid} ({metric.replace('_', '-').upper()}) & {comp['label']} & "
                f"${r['mean_diff']:+.3f}$ & ${r['diff_ci95']:.3f}$ & "
                f"{r['t']:.2f} & {_fmt_p(r['p'])} & {r['cohen_d']:.2f} \\\\"
            )
    for _key, r in campaign.get("comparisons", {}).items():
        rows.append(
            f"LLM & {r['label']} & ${r['mean_diff']:+.3f}$ & ${r['diff_ci95']:.3f}$ & "
            f"{r['t']:.2f} & {_fmt_p(r['p'])} & {r['cohen_d']:.2f} \\\\"
        )
    tex = (
        "\\begin{table}[!t]\n\\caption{Seed-paired $t$-tests (six seeds). "
        "Diff.\\ = second minus first cell; positive diff.\\ on DR means higher detection in second cell. "
        "No multiplicity correction (exploratory).}\n\\label{tab:stats-tests}\n\\centering\n"
        "\\setlength{\\tabcolsep}{3pt}\n\\footnotesize\n"
        "\\begin{tabular}{@{}llrrrrr@{}}\n\\toprule\n"
        "\\textbf{ID} & \\textbf{Comparison} & \\textbf{Diff.} & \\textbf{CI$_{95}$} & "
        "$t$ & $p$ & $d$ \\\\\n\\midrule\n"
        + "\n".join(rows)
        + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    FIG_GEN.mkdir(parents=True, exist_ok=True)
    (FIG_GEN / "stats_tests.tex").write_text(tex)


def _write_cep_adj_table(cells: dict) -> None:
    rows = []
    for name in LADDER_PRIMARY:
        if name not in cells:
            continue
        c = cells[name]["cep_adj"]
        rows.append(
            f"{PRETTY[name]:24s} & ${c['mean']:.3f}{{\\pm}}{c['ci95']:.3f}$ \\\\"
        )
    tex = (
        "\\begin{table}[!t]\n\\caption{Baseline-adjusted CEP "
        "($\\mathrm{CEP}_{\\mathrm{adj}}=\\mathrm{CEP}-\\mathrm{CEP}_{\\mathrm{S/S}}$ on the same seed).}\n"
        "\\label{tab:cep-adj}\n\\centering\n\\begin{tabular}{@{}lr@{}}\n\\toprule\n"
        "\\textbf{Matchup} & $\\mathrm{CEP}_{\\mathrm{adj}}$ \\\\\n\\midrule\n"
        + "\n".join(rows)
        + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    (FIG_GEN / "cep_adj_table.tex").write_text(tex)


def _write_dynamics_table(by_cell: dict) -> None:
    rows = []
    for name in LADDER_PRIMARY:
        if name not in by_cell:
            continue
        c = by_cell[name]
        total = sum(c.values())
        stable = c.get("stable_equilibrium", 0)
        conv = c.get("converging", 0)
        nc = c.get("non_convergent", 0)
        rows.append(
            f"{PRETTY[name]:24s} & {stable} & {conv} & {nc} & {total} \\\\"
        )
    tex = (
        "\\begin{table}[!t]\n\\caption{Parameter dynamics class counts per ladder cell "
        "(stealth/vigilance only; six seeds). Full-signature labels are almost always "
        "\\emph{non-convergent} because action-mix features fluctuate stochastically even under L0.}\n"
        "\\label{tab:dynamics}\n\\centering\n\\setlength{\\tabcolsep}{3pt}\n\\footnotesize\n"
        "\\begin{tabular}{@{}lcccc@{}}\n\\toprule\n"
        "\\textbf{Matchup} & \\textbf{Stable} & \\textbf{Conv.} & \\textbf{Non-conv.} & $n$ \\\\\n\\midrule\n"
        + "\n".join(rows)
        + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    (FIG_GEN / "dynamics_table.tex").write_text(tex)


def _md_report(ladder: dict, campaign: dict) -> str:
    lines = ["# Paper statistics", ""]
    for key, comp in ladder.get("comparisons", {}).items():
        lines.append(f"## {comp['label']}")
        for metric in ("dr", "asr", "cep_adj"):
            r = comp.get(metric, {})
            if r.get("n", 0) < 2:
                continue
            lines.append(
                f"- {metric}: diff={r['mean_diff']:+.4f} CI95={r['diff_ci95']:.4f} "
                f"t={r['t']:.3f} p={r['p']:.4g} d={r['cohen_d']:.3f}"
            )
        lines.append("")
    lines.append("## Dynamics by cell")
    for cell, counts in sorted(ladder.get("dynamics_by_cell", {}).items()):
        lines.append(f"- {cell}: {counts}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ladder", default="runs/ci/ladder_ci.json")
    p.add_argument("--campaign", default="runs/campaign/final_report.json")
    p.add_argument("--out-dir", default="analysis_out")
    args = p.parse_args()

    ladder_path = ROOT / args.ladder
    ladder_data = json.loads(ladder_path.read_text())
    ladder_stats = analyze_ladder(ladder_path)
    campaign_stats = analyze_campaign(ROOT / args.campaign)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"ladder": ladder_stats, "campaign": campaign_stats}
    (out_dir / "paper_stats.json").write_text(json.dumps(payload, indent=2))
    (out_dir / "paper_stats.md").write_text(_md_report(ladder_stats, campaign_stats))

    _write_stats_tests(ladder_stats, campaign_stats)
    _write_cep_adj_table(ladder_data.get("cells", {}))
    _write_dynamics_table(ladder_stats.get("dynamics_by_cell", {}))
    print((out_dir / "paper_stats.md").read_text())
    print(f"wrote tables under {FIG_GEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
