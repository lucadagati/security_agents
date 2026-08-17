#!/usr/bin/env bash
# Regenerate paper artifacts after LLM campaign completes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
make -C paper figures 2>/dev/null || {
  "$PY" scripts/generate_paper_figures.py
  "$PY" scripts/paper_analysis.py
}
"$PY" scripts/export_paper_data.py
make -C paper pdf
echo "Done. See paper/main.pdf and analysis_out/paper_stats.md"
