#!/usr/bin/env python3
"""Export a lightweight manifest of paper-facing run artifacts (no full trajectories).

Usage:
  python scripts/export_paper_data.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _manifest_entry(run_dir: Path) -> dict:
    entry = {"run_dir": str(run_dir.relative_to(ROOT))}
    for name in ("config.json", "aggregate.json", "episodes.jsonl"):
        p = run_dir / name
        if p.exists():
            entry[name] = str(p.relative_to(ROOT))
    analysis = run_dir / "analysis" / "report.json"
    if analysis.exists():
        entry["analysis_report"] = str(analysis.relative_to(ROOT))
    return entry


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="data/paper_runs")
    args = p.parse_args()

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    manifest: dict = {"commit": _git_head(), "ladder_ci": None, "campaign_report": None, "runs": []}

    ladder_json = ROOT / "runs/ci/ladder_ci.json"
    if ladder_json.exists():
        dest = out / "ladder_ci.json"
        shutil.copy2(ladder_json, dest)
        manifest["ladder_ci"] = str(dest.relative_to(ROOT))
        data = json.loads(ladder_json.read_text())
        for cell in data.get("cells", {}).values():
            for run in cell.get("runs", []):
                rd = run.get("run_dir")
                if rd:
                    manifest["runs"].append(_manifest_entry(ROOT / rd))

    campaign = ROOT / "runs/campaign/final_report.json"
    if campaign.exists():
        dest = out / "campaign_final_report.json"
        shutil.copy2(campaign, dest)
        manifest["campaign_report"] = str(dest.relative_to(ROOT))

    stats = ROOT / "analysis_out/paper_stats.json"
    if stats.exists():
        shutil.copy2(stats, out / "paper_stats.json")
        manifest["paper_stats"] = str((out / "paper_stats.json").relative_to(ROOT))

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {out / 'manifest.json'} ({len(manifest['runs'])} ladder runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
