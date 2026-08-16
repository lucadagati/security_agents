#!/usr/bin/env bash
# Launch the 2-day L40 campaign detached. Safe to re-run (skips completed jobs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
set -a
[ -f .env ] && . ./.env
set +a

mkdir -p runs/campaign
LOG="runs/campaign/suite.log"
PIDFILE="runs/campaign/suite.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Campaign already running with PID $(cat "$PIDFILE")"
  exit 0
fi

PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

nohup "$PYTHON" "$ROOT/scripts/campaign_2day.py" >>"$ROOT/runs/campaign/suite.stdout" 2>&1 &
echo $! >"$PIDFILE"
echo "Started 2-day campaign PID=$(cat "$PIDFILE")"
echo "Log: $LOG  (stdout: runs/campaign/suite.stdout)"
echo "Send /start to @L40unimebot anytime for Telegram progress."
echo "Resume after crash: re-run this script (completed jobs are skipped)."
