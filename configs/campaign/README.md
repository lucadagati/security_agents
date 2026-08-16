# Two-day L40 campaign — high-tier paper evidence

Target: NVIDIA L40 via Ollama (`COEVSEC_OLLAMA_BASE_URL`), wall time **~36–48 h**.
Checkpointed: safe to restart. Telegram: `@L40unimebot` (send `/start` once).

## Why this (not another overnight)

The heuristic 1v1 ladder + CI already supports H1/H2. Pure-LLM overnight
cells mostly had ASR≈0, so LLM capability claims do not hold. This campaign
is built to produce **credible B3–B5 evidence** and optional scaling results.

## Phases → paper claims

| Phase | What | Claim it unlocks | ~wall |
|---|---|---|---|
| 0 | Smoke hybrid | Fail-fast | 15–30 min |
| 1 | Hybrid B3/B4/B5 × 6 seeds × 30 ep | Main LLM+adapt table + CI | 18–28 h |
| 2 | Pure LLM B5 × 3 seeds (negative control) | Honest ablation vs hybrid | 4–8 h |
| 3 | Model scale (8B / 14B / 30B) hybrid B5 × 3 seeds | Capacity / model sensitivity | 6–12 h |
| 4 | Asymmetric hybrid↔heur × 3 seeds | Interaction of policy classes | 3–6 h |
| 5 | Long-horizon persistent hybrid 80 ep × 3 seeds | Arms-race / CEP trajectories | 4–8 h |
| 6 | Population hybrid E4-lite 3v3 × 2 seeds | Scaling beyond 1v1 | 2–4 h |

Phase 1 alone already elevates the paper. Phases 2–6 are what make it
look like a systems+empirical IEEE Transactions piece rather than a
simulation toy study.

## Launch

```bash
# once: Telegram
# send /start to https://t.me/L40unimebot

./scripts/launch_campaign.sh
# resume after reboot / crash:
./scripts/launch_campaign.sh
```

Artifacts under `runs/campaign/`:
- `suite.log`, `suite_state.json`, `suite.stdout`
- `final_report.{json,md}`
- per-job run dirs + analysis

## Design rules

1. Prefer **hybrid** for positive LLM claims; report pure LLM as ablation.
2. Always multi-seed (≥3; phase 1 uses 6) with mean±CI95 in the paper.
3. Do not inflate episode counts on broken pure-LLM loops — hybrid first.
4. Keep heuristic ladder CI as the backbone; this campaign is the LLM chapter.
