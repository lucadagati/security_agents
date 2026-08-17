#!/usr/bin/env python3
"""Regenerate paper figure data and TikZ snippets from experiment outputs.

Usage:
  python scripts/generate_paper_figures.py
  python scripts/generate_paper_figures.py --ladder runs/ci/ladder_ci.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from coevsec.analysis.engine import analyze_run  # noqa: E402

LADDER_ORDER = [
    ("static_static", "S/S"),
    ("static_adaptive", "S/A"),
    ("adaptive_static", "A/S"),
    ("adaptive_adaptive", "A/A"),
    ("persistent_persistent", "P/P"),
    ("persistent_static", "P/S"),
    ("static_persistent", "S/P"),
    ("persistent_adaptive", "P/A"),
    ("adaptive_persistent", "A/P"),
]

LADDER_MAIN = ["static_static", "static_adaptive", "adaptive_static", "adaptive_adaptive", "persistent_persistent"]
LADDER_PRIMARY = [n for n, _ in LADDER_ORDER]

# 3x3 grid: rows = attacker (S,A,P), cols = defender (S,A,P)
LADDER_GRID = [
    ["static_static", "static_adaptive", "static_persistent"],
    ["adaptive_static", "adaptive_adaptive", "adaptive_persistent"],
    ["persistent_static", "persistent_adaptive", "persistent_persistent"],
]


def _fmt_coords(pairs: list[tuple[str, float]]) -> str:
    return " ".join(f"({x},{y:.3f})" for x, y in pairs)


def _err_coords(pairs: list[tuple[str, float, float]]) -> str:
    lines = []
    for x, y, e in pairs:
        lines.append(f"({x},{y:.3f}) +- (0,{e:.3f})")
    return " ".join(lines)


def _write_ladder_heatmap(fig_dir: Path, cells: dict) -> None:
    """3x3 coloured tables for ASR and DR (all nine cells)."""
    gen = fig_dir / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    labels = ["S", "A", "P"]

    def _cell(name: str, metric: str) -> str:
        if name not in cells:
            return "---"
        c = cells[name][metric]
        return f"${c['mean']:.3f}{{\\pm}}{c['ci95']:.3f}$"

    asr_rows, dr_rows = [], []
    for row in LADDER_GRID:
        asr_rows.append(" & ".join(_cell(n, "asr") for n in row) + r" \\")
        dr_rows.append(" & ".join(_cell(n, "dr") for n in row) + r" \\")

    tex = (
        r"""\begin{figure}[!t]
\centering
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lccc@{}}
\toprule
\multicolumn{4}{c}{\textbf{ASR} (attacker $\downarrow$ / defender $\rightarrow$)} \\
\midrule
 & \textbf{S} & \textbf{A} & \textbf{P} \\
\midrule
"""
        + "\n".join(f"\\textbf{{{labels[i]}}} & {asr_rows[i]}" for i in range(3))
        + r"""
\midrule
\multicolumn{4}{c}{\textbf{DR}} \\
\midrule
 & \textbf{S} & \textbf{A} & \textbf{P} \\
\midrule
"""
        + "\n".join(f"\\textbf{{{labels[i]}}} & {dr_rows[i]}" for i in range(3))
        + r"""
\bottomrule
\end{tabular}
\caption{Adaptation ladder: all nine cells ($3{\times}3$; mean$\pm$CI95, six seeds).
ASR stays near zero unless the attacker adapts; DR drops when the attacker is L1/L2.}
\label{fig:ladder}
\end{figure}
"""
    )
    (fig_dir / "ladder_heatmap.tex").write_text(tex)


def _write_ladder_bars(fig_dir: Path, cells: dict, main_only: bool = True) -> None:
    _write_ladder_heatmap(fig_dir, cells)


def _write_hybrid_bars(fig_dir: Path, campaign_path: Path) -> None:
    if not campaign_path.exists():
        return
    data = json.loads(campaign_path.read_text())
    phase1 = data.get("phase1_hybrid_ci", {})
    order = [("b3_static", "B3"), ("b4_episodic", "B4"), ("b5_persistent", "B5")]
    asr = [(lab, phase1[key]["ASR"]["mean"]) for key, lab in order if key in phase1]
    dr = [(lab, phase1[key]["DR"]["mean"]) for key, lab in order if key in phase1]
    tex = f"""\\begin{{figure}}[!t]
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  ybar,
  bar width=10pt,
  width=\\columnwidth,
  height=4.2cm,
  ylabel={{Rate}},
  ymin=0, ymax=1.05,
  symbolic x coords={{B3,B4,B5}},
  xtick=data,
  xticklabel style={{font=\\scriptsize}},
  legend style={{font=\\scriptsize, at={{(0.5,1.02)}}, anchor=south, legend columns=2, draw=none}},
  grid=major,
  major grid style={{dotted,gray!50}},
]
\\addplot coordinates {{{_fmt_coords(asr)}}};
\\addplot coordinates {{{_fmt_coords(dr)}}};
\\legend{{ASR, Detection rate}}
\\end{{axis}}
\\end{{tikzpicture}}
\\caption{{Hybrid LLM baselines B3--B5 (6-seed means; CI95 in Table~\\ref{{tab:llm}}). B4 has the highest mean ASR; B5 remains low ($0.044{{\\pm}}0.028$).}}
\\label{{fig:hybrid-asr}}
\\end{{figure}}
"""
    (fig_dir / "hybrid_memory_bars.tex").write_text(tex)


def _write_llm_table(fig_dir: Path, campaign_path: Path) -> None:
    if not campaign_path.exists():
        return
    data = json.loads(campaign_path.read_text())
    phase1 = data.get("phase1_hybrid_ci", {})
    labels = {
        "b3_static": "B3 hybrid static",
        "b4_episodic": "B4 hybrid episodic",
        "b5_persistent": "B5 hybrid persistent",
    }
    order = ["b3_static", "b4_episodic", "b5_persistent"]
    rows = []
    for key in order:
        if key not in phase1:
            continue
        c = phase1[key]
        rows.append(
            f"{labels[key]:22s} & ${c['ASR']['mean']:.3f}{{\\pm}}{c['ASR']['ci95']:.3f}$ "
            f"& ${c['DR']['mean']:.3f}{{\\pm}}{c['DR']['ci95']:.3f}$ "
            f"& ${c['CEP']['mean']:.3f}{{\\pm}}{c['CEP']['ci95']:.3f}$ \\\\"
        )
    gen = fig_dir / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    tex = """\\begin{table}[!t]
\\caption{Hybrid LLM baselines B3--B5 (mean$\\pm$95\\% CI, six seeds, 30 episodes).}
\\label{tab:llm}
\\centering
\\begin{tabular}{@{}lccc@{}}
\\toprule
\\textbf{Cell} & \\textbf{ASR} & \\textbf{DR} & \\textbf{CEP} \\\\
\\midrule
""" + "\n".join(rows) + """
\\bottomrule
\\end{tabular}
\\end{table}
"""
    (gen / "llm_table.tex").write_text(tex)


def _write_gate_snippet(fig_dir: Path, campaign_path: Path) -> None:
    if not campaign_path.exists():
        return
    data = json.loads(campaign_path.read_text())
    gate = data.get("phase1_gate_frac") or {}
    if not gate:
        return
    pretty = {"b3_static": "B3", "b4_episodic": "B4", "b5_persistent": "B5"}
    parts = []
    for key in ("b3_static", "b4_episodic", "b5_persistent"):
        if key not in gate:
            continue
        g = gate[key]
        mean = g.get("mean", 0.0)
        ci = g.get("ci95", 0.0)
        parts.append(f"{pretty[key]}={mean:.2f}${{\\pm}}{ci:.2f}$")
    if not parts:
        return
    text = (
        "Phase~1 attacker-side gate intervention fractions (heuristic steps / total attacker steps, "
        "6-seed means): " + ", ".join(parts) + "."
    )
    gen = fig_dir / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "gate_stats.tex").write_text(text + "\n")


def _rolling_detection(episodes: list[dict], window: int = 5) -> list[tuple[int, float]]:
    if not episodes:
        return []
    vals = [1.0 if e.get("detected") else 0.0 for e in episodes]
    out: list[tuple[int, float]] = []
    for i in range(len(vals)):
        lo = max(0, i - window + 1)
        out.append((i + 1, sum(vals[lo : i + 1]) / (i - lo + 1)))
    return out


def _write_dynamics(fig_dir: Path, run_dir: Path, ladder_path: Path | None = None) -> None:
    rep = analyze_run(run_dir)
    dyn = rep.get("strategy_dynamics", {})
    param_deltas = dyn.get("param_delta_series", dyn.get("delta_series", []))
    p_early = dyn.get("param_early_delta", dyn.get("early_delta", 0.0))
    p_late = dyn.get("param_late_delta", dyn.get("late_delta", 0.0))
    half = max(1, len(param_deltas) // 2)
    coords = " ".join(f"({i+1},{d:.4f})" for i, d in enumerate(param_deltas))
    cls = dyn.get("classification", "unknown")
    tex = f"""\\begin{{figure}}[!t]
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
  width=\\columnwidth,
  height=3.6cm,
  xlabel={{Episode $t$}},
  ylabel={{$\\Delta$ stealth/vigilance}},
  xmin=1, xmax={max(1, len(param_deltas))},
  ymin=0, ymax={max(0.35, max(param_deltas) * 1.15) if param_deltas else 0.35:.2f},
  xticklabel style={{font=\\scriptsize}},
  yticklabel style={{font=\\scriptsize}},
  label style={{font=\\scriptsize}},
  grid=major,
  major grid style={{dotted,gray!50}},
]
\\addplot+[thick, mark=none] coordinates {{{coords}}};
\\addplot+[thick, dashed, mark=none] coordinates {{(1,{p_early:.4f}) ({half},{p_early:.4f})}};
\\addplot+[thick, dotted, mark=none] coordinates {{({half+1},{p_late:.4f}) ({len(param_deltas)},{p_late:.4f})}};
\\end{{axis}}
\\end{{tikzpicture}}
\\caption{{Per-episode parameter change on a representative P/P run (seed~100). Parameter dynamics class: \\emph{{{cls.replace('_', ' ')}}}. Distribution over all 54 ladder runs in Table~\\ref{{tab:dynamics}}.}}
\\label{{fig:arms}}
\\end{{figure}}
"""
    (fig_dir / "arms_race.tex").write_text(tex)

    ep_path = Path(run_dir) / "episodes.jsonl"
    if ep_path.exists():
        episodes = [json.loads(line) for line in ep_path.read_text().splitlines() if line.strip()]
        gen = fig_dir / "generated"
        gen.mkdir(parents=True, exist_ok=True)
        rolling = _rolling_detection(episodes)
        lines = ["ep det stealth vigilance"]
        for i, e in enumerate(episodes):
            att = e.get("attacker_strategy", {})
            dfn = e.get("defender_strategy", {})
            lines.append(
                f"{i+1} {rolling[i][1]:.4f} {att.get('stealth', 0):.3f} {dfn.get('vigilance', 0):.3f}"
            )
        (gen / "episode_dynamics.dat").write_text("\n".join(lines) + "\n")
        ep_tex = r"""\begin{figure}[!t]
\centering
\begin{tikzpicture}
\begin{axis}[
  width=\columnwidth,
  height=4.0cm,
  xmin=1, xmax=40,
  xlabel={Episode $t$},
  ylabel={Rolling DR},
  ymin=0, ymax=1.05,
  xtick={1,10,20,30,40},
  xticklabel style={font=\scriptsize},
  yticklabel style={font=\scriptsize},
  label style={font=\scriptsize},
  grid=major,
  major grid style={dotted,gray!50},
]
\addplot+[thick, mark=none, color=blue!70!black] table[x=ep, y=det, col sep=space] {figures/generated/episode_dynamics.dat};
\end{axis}
\begin{axis}[
  width=\columnwidth,
  height=4.0cm,
  xmin=1, xmax=40,
  axis y line*=right,
  axis x line=none,
  ylabel={Attacker stealth},
  ymin=0, ymax=1.05,
  yticklabel style={font=\scriptsize},
  legend style={font=\scriptsize, at={(0.02,0.98)}, anchor=north west, draw=none},
]
\addplot+[thick, mark=none, color=red!70!black] table[x=ep, y=stealth, col sep=space] {figures/generated/episode_dynamics.dat};
\end{axis}
\end{tikzpicture}
\caption{Representative P/P run (seed~100): rolling detection rate (left axis) and attacker stealth (right axis). Illustrates programmed pacing, not an unencoded strategy.}
\label{fig:episode-dynamics}
\end{figure}
"""
        (fig_dir / "episode_dynamics.tex").write_text(ep_tex)


def _write_ladder_table(fig_dir: Path, cells: dict) -> None:
    pretty = {
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
    rows = []
    for name in LADDER_PRIMARY:
        if name not in cells:
            continue
        c = cells[name]
        rows.append(
            f"{pretty[name]:24s} & ${c['asr']['mean']:.3f}{{\\pm}}{c['asr']['ci95']:.3f}$ "
            f"& ${c['dr']['mean']:.3f}{{\\pm}}{c['dr']['ci95']:.3f}$ "
            f"& ${c['cep']['mean']:.3f}{{\\pm}}{c['cep']['ci95']:.3f}$ \\\\"
        )
    gen = fig_dir / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    tex = """\\begin{table}[!t]
\\caption{Heuristic adaptation ladder (mean$\\pm$95\\% CI, six seeds, 40 episodes).}
\\label{tab:ladder}
\\centering
\\begin{tabular}{@{}lccc@{}}
\\toprule
\\textbf{Matchup} & \\textbf{ASR} & \\textbf{DR} & \\textbf{CEP} \\\\
\\midrule
""" + "\n".join(rows) + """
\\bottomrule
\\end{tabular}
\\end{table}
"""
    (fig_dir / "generated" / "ladder_table.tex").write_text(tex)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ladder", default="runs/ci/ladder_ci.json")
    p.add_argument("--campaign", default="runs/campaign/final_report.json")
    p.add_argument("--fig-dir", default="paper/figures")
    p.add_argument("--dynamics-run", default="", help="Run dir for Fig. arms/dynamics (default: P/P seed 100)")
    args = p.parse_args()

    ladder_path = ROOT / args.ladder
    fig_dir = ROOT / args.fig_dir
    data = json.loads(ladder_path.read_text())
    cells = data["cells"]

    _write_ladder_bars(fig_dir, cells, main_only=True)
    campaign_path = ROOT / args.campaign
    _write_hybrid_bars(fig_dir, campaign_path)
    _write_llm_table(fig_dir, campaign_path)
    _write_gate_snippet(fig_dir, campaign_path)
    _write_ladder_table(fig_dir, cells)

    run_dir = args.dynamics_run
    if not run_dir:
        pp = cells.get("persistent_persistent", {})
        runs = pp.get("runs", [])
        run_dir = runs[0]["run_dir"] if runs else ""
    if run_dir:
        _write_dynamics(fig_dir, ROOT / run_dir)
        print(f"wrote dynamics from {run_dir}")
    print(f"wrote figures under {fig_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
