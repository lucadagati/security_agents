# Overnight experiment suite — unattended plan
#
# Target host: Ollama at http://100.86.223.16:11434 (NVIDIA L40, 46 GB).
# Volume model: qwen2.5-coder:7b
# Strong model: qwen3-coder:30b
# Notify: Telegram @L40unimebot
#
# Estimated wall time (order of magnitude, L40 idle):
#   Phase 1 heuristic ladder .............. < 5 min
#   Phase 2 E1–E8 heuristic ............... 10–40 min (E8 heaviest)
#   Phase 3 volume LLM cells .............. 3–8 h
#   Phase 3 strong 30B cells .............. 2–6 h
#   Analysis ................................ folded into each job
# Total: typically a long evening / overnight.

Launch:
  1. Send /start to https://t.me/L40unimebot (once).
  2. ./scripts/launch_overnight.sh
  3. Leave it; re-running the launcher is safe (skips completed jobs).

Artifacts:
  runs/overnight/suite.log
  runs/overnight/suite_state.json
  runs/overnight/final_report.{json,md}
  runs/overnight/<experiment>_*/
