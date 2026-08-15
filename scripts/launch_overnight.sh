#!/usr/bin/env bash
# Launch the overnight suite detached. Safe to re-run (skips completed jobs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
set -a
[ -f .env ] && . ./.env
set +a

mkdir -p runs/overnight
LOG="runs/overnight/suite.log"
PIDFILE="runs/overnight/suite.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Suite already running with PID $(cat "$PIDFILE")"
  exit 0
fi

# Prefer the project venv if present.
PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

nohup "$PYTHON" "$ROOT/scripts/overnight_suite.py" >>"$ROOT/runs/overnight/suite.stdout" 2>&1 &
echo $! >"$PIDFILE"
echo "Started overnight suite PID=$(cat "$PIDFILE")"
echo "Log: $LOG  (stdout: runs/overnight/suite.stdout)"
echo "Send /start to @L40unimebot anytime for Telegram progress."
