#!/usr/bin/env python3
"""Unattended overnight experiment suite with Telegram progress.

Phases
------
1. Heuristic ladder (configs/ladder) — fast, validates co-evolution.
2. Heuristic E1–E8 matrix — population / topology scaling.
3. Overnight LLM + multi-seed cells (configs/overnight) — L40 via Ollama.
4. Analysis of every completed run + final summary.

Designed to run for hours without interaction. Progress is logged to
``runs/overnight/suite.log`` and pushed to Telegram (@L40unimebot) when a
chat id is available (send ``/start`` once). Already-finished jobs are
skipped on restart (checkpoint file).
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_notify import TelegramNotifier, _load_dotenv  # noqa: E402


@dataclass
class Job:
    job_id: str
    kind: str  # "config" | "ladder"
    path: str
    phase: str
    note: str = ""


@dataclass
class JobResult:
    job_id: str
    status: str  # ok | fail | skip
    started_at: str = ""
    finished_at: str = ""
    elapsed_s: float = 0.0
    run_dir: str | None = None
    summary: dict = field(default_factory=dict)
    error: str | None = None


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_jobs() -> list[Job]:
    jobs: list[Job] = []
    ladder = ROOT / "configs" / "ladder"
    if ladder.is_dir():
        jobs.append(Job("phase1_ladder", "ladder", str(ladder), "1_heuristic_ladder",
                        "Static/Adaptive/Persistent 1v1 factorial"))
    for name in [f"e{i}.yaml" for i in range(1, 9)]:
        p = ROOT / "configs" / name
        if p.exists():
            jobs.append(Job(f"phase2_{p.stem}", "config", str(p), "2_heuristic_matrix",
                            f"Experimental matrix {p.stem}"))
    overnight = sorted(
        p for p in (ROOT / "configs" / "overnight").glob("*.yaml")
        if not p.name.startswith("00_")
    )
    for p in overnight:
        jobs.append(Job(f"phase3_{p.stem}", "config", str(p), "3_llm_overnight",
                        p.stem))
    return jobs


def _models_in_config(path: str) -> list[str]:
    import yaml

    data = yaml.safe_load(Path(path).read_text()) or {}
    models: list[str] = []
    for agent in data.get("agents", []):
        policy = (agent or {}).get("policy") or {}
        llm = (agent or {}).get("llm") or {}
        if policy.get("kind") == "llm" and llm.get("provider", "ollama") == "ollama":
            m = llm.get("model") or os.environ.get("COEVSEC_OLLAMA_MODEL")
            if m:
                models.append(str(m))
    return sorted(set(models))


def _wait_for_ollama_model(model: str, timeout_s: float = 7200.0, log=print) -> None:
    """Block until ``model`` is listed by Ollama (download may still be running)."""
    import requests

    base = os.environ.get("COEVSEC_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base}/api/tags", timeout=15)
            resp.raise_for_status()
            names = {m.get("name") for m in resp.json().get("models", [])}
            if model in names:
                log(f"[ollama] model ready: {model}")
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        log(f"[ollama] waiting for model {model} …")
        time.sleep(20)
    raise TimeoutError(f"model {model} not available on {base} within {timeout_s}s ({last_err})")


class Suite:
    def __init__(self) -> None:
        _load_dotenv(ROOT / ".env")
        self.out = ROOT / "runs" / "overnight"
        self.out.mkdir(parents=True, exist_ok=True)
        self.state_path = self.out / "suite_state.json"
        self.log_path = self.out / "suite.log"
        self.tg = TelegramNotifier()
        self.state = self._load_state()
        self.jobs = _build_jobs()
        self._last_hb = 0.0

    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"results": {}, "started_at": None, "finished_at": None}

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2, default=str))

    def log(self, msg: str) -> None:
        line = f"[{_utc()}] {msg}"
        print(line, flush=True)
        with self.log_path.open("a") as fh:
            fh.write(line + "\n")

    def notify(self, msg: str) -> None:
        self.log(msg)
        # Pick up /start that arrived after suite launch.
        if self.tg.enabled and not self.tg.chat_id:
            self.tg.discover_chat_id(wait_s=0.0)
        self.tg.send(msg)

    def heartbeat(self, current: str, done: int, total: int) -> None:
        now = time.time()
        if now - self._last_hb < 900:  # 15 min
            return
        self._last_hb = now
        self.notify(
            f"⏳ heartbeat\n"
            f"running: {current}\n"
            f"progress: {done}/{total}\n"
            f"host time: {_utc()}"
        )

    def _already_ok(self, job_id: str) -> bool:
        r = self.state.get("results", {}).get(job_id)
        return bool(r and r.get("status") == "ok")

    def run_job(self, job: Job) -> JobResult:
        if self._already_ok(job.job_id):
            prev = self.state["results"][job.job_id]
            self.log(f"SKIP {job.job_id} (already ok → {prev.get('run_dir')})")
            return JobResult(job_id=job.job_id, status="skip",
                             run_dir=prev.get("run_dir"), summary=prev.get("summary", {}))

        from coevsec.analysis.engine import analyze_run
        from coevsec.experiments import run_experiment

        started = time.time()
        result = JobResult(job_id=job.job_id, status="fail", started_at=_utc())
        self.notify(
            f"▶️ START {job.job_id}\n"
            f"phase: {job.phase}\n"
            f"{job.note}\n"
            f"path: {job.path}"
        )
        try:
            if job.kind == "ladder":
                # Run each ladder config individually for cleaner checkpoints.
                summaries = []
                for cfg in sorted(Path(job.path).glob("*.yaml")):
                    sub_id = f"{job.job_id}::{cfg.stem}"
                    if self._already_ok(sub_id):
                        summaries.append(self.state["results"][sub_id].get("summary", {}))
                        continue
                    t0 = time.time()
                    agg = run_experiment(str(cfg))
                    if agg.get("run_dir"):
                        analyze_run(agg["run_dir"])
                    sub = JobResult(
                        job_id=sub_id, status="ok", started_at=_utc(),
                        finished_at=_utc(), elapsed_s=time.time() - t0,
                        run_dir=agg.get("run_dir"), summary=agg,
                    )
                    self.state["results"][sub_id] = asdict(sub)
                    self._save_state()
                    summaries.append(agg)
                    self.notify(
                        f"✅ ladder cell {cfg.stem}\n"
                        f"ASR={agg.get('attack_success_rate', 0):.3f} "
                        f"DR={agg.get('detection_rate', 0):.3f} "
                        f"CEP={agg.get('coevolutionary_pressure', 0):.3f}"
                    )
                result.status = "ok"
                result.summary = {"cells": len(summaries)}
            else:
                for model in _models_in_config(job.path):
                    self.log(f"ensuring Ollama model available: {model}")
                    self.notify(f"📦 ensuring model on L40: {model}")
                    _wait_for_ollama_model(model, log=self.log)
                agg = run_experiment(job.path)
                run_dir = agg.get("run_dir")
                if run_dir:
                    report = analyze_run(run_dir)
                    agg["analysis_classification"] = (
                        report.get("strategy_dynamics", {}) or {}
                    ).get("classification")
                    emergent = (report.get("emergence", {}) or {}).get("candidate_emergent", {})
                    agg["top_emergent"] = list(emergent.keys())[:5]
                result.status = "ok"
                result.run_dir = run_dir
                result.summary = {
                    k: agg.get(k)
                    for k in (
                        "name", "episodes", "attack_success_rate", "detection_rate",
                        "coevolutionary_pressure", "behavioral_novelty", "esr",
                        "coalition_rate", "analysis_classification", "top_emergent",
                        "run_dir",
                    )
                    if k in agg or agg.get(k) is not None
                }
            result.elapsed_s = time.time() - started
            result.finished_at = _utc()
            self.notify(
                f"✅ DONE {job.job_id} ({result.elapsed_s/60:.1f} min)\n"
                + self._fmt_summary(result.summary)
            )
        except Exception as exc:  # noqa: BLE001 — keep suite alive
            result.status = "fail"
            result.error = f"{type(exc).__name__}: {exc}"
            result.elapsed_s = time.time() - started
            result.finished_at = _utc()
            tb = traceback.format_exc()
            self.log(tb)
            self.notify(
                f"❌ FAIL {job.job_id} after {result.elapsed_s/60:.1f} min\n"
                f"{result.error}\n(continuing with next job)"
            )
        self.state["results"][job.job_id] = asdict(result)
        self._save_state()
        return result

    @staticmethod
    def _fmt_summary(s: dict) -> str:
        if not s:
            return "(no summary)"
        parts = []
        if "cells" in s:
            return f"ladder cells completed: {s['cells']}"
        for k in ("attack_success_rate", "detection_rate", "coevolutionary_pressure",
                  "behavioral_novelty", "esr", "coalition_rate", "analysis_classification"):
            if k in s and s[k] is not None:
                v = s[k]
                parts.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
        if s.get("top_emergent"):
            parts.append("emergent=" + ",".join(s["top_emergent"]))
        if s.get("run_dir"):
            parts.append(f"dir={s['run_dir']}")
        return "\n".join(parts) or str(s)[:400]

    def run(self) -> int:
        self.state["started_at"] = self.state.get("started_at") or _utc()
        self._save_state()

        # Brief attempt to attach Telegram; do not block the suite for long.
        # User can send /start any time — subsequent notify() calls re-discover.
        if self.tg.enabled and not self.tg.chat_id:
            self.log("Checking Telegram (30s). Send /start to @L40unimebot anytime.")
            self.tg.discover_chat_id(wait_s=30.0)

        total = len(self.jobs)
        self.notify(
            "🌙 coevsec overnight suite STARTED\n"
            f"jobs: {total}\n"
            f"ollama: {os.environ.get('COEVSEC_OLLAMA_BASE_URL', '?')}\n"
            f"volume model: {os.environ.get('COEVSEC_OLLAMA_MODEL', '?')}\n"
            f"strong model: {os.environ.get('COEVSEC_OLLAMA_MODEL_STRONG', '?')}\n"
            f"log: {self.log_path}"
        )

        ok = fail = skip = 0
        for i, job in enumerate(self.jobs, 1):
            self.heartbeat(job.job_id, i - 1, total)
            r = self.run_job(job)
            if r.status == "ok":
                ok += 1
            elif r.status == "skip":
                skip += 1
            else:
                fail += 1

        self.state["finished_at"] = _utc()
        self._save_state()
        report_path = self._write_final_report()
        self.notify(
            "🏁 coevsec overnight suite FINISHED\n"
            f"ok={ok} skip={skip} fail={fail} / {total}\n"
            f"started: {self.state['started_at']}\n"
            f"finished: {self.state['finished_at']}\n"
            f"report: {report_path}"
        )
        return 0 if fail == 0 else 1

    def _write_final_report(self) -> Path:
        path = self.out / "final_report.json"
        rows = []
        for jid, r in self.state.get("results", {}).items():
            if r.get("status") != "ok":
                continue
            s = r.get("summary") or {}
            if "attack_success_rate" in s:
                rows.append({"job_id": jid, **{k: s.get(k) for k in (
                    "name", "attack_success_rate", "detection_rate",
                    "coevolutionary_pressure", "behavioral_novelty", "esr",
                    "coalition_rate", "analysis_classification", "run_dir",
                )}})
        payload = {
            "started_at": self.state.get("started_at"),
            "finished_at": self.state.get("finished_at"),
            "n_results": len(self.state.get("results", {})),
            "metric_rows": rows,
            "raw": self.state.get("results"),
        }
        path.write_text(json.dumps(payload, indent=2, default=str))
        # Also a compact markdown table for humans / Telegram.
        md = self.out / "final_report.md"
        lines = [
            "# Overnight suite report",
            f"- started: {payload['started_at']}",
            f"- finished: {payload['finished_at']}",
            "",
            "| job | ASR | DR | CEP | novelty | class |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for row in rows:
            lines.append(
                f"| {row.get('job_id') or row.get('name')} | "
                f"{row.get('attack_success_rate', float('nan')):.3f} | "
                f"{row.get('detection_rate', float('nan')):.3f} | "
                f"{row.get('coevolutionary_pressure', float('nan')):.3f} | "
                f"{row.get('behavioral_novelty', float('nan')):.3f} | "
                f"{row.get('analysis_classification', '')} |"
            )
        md.write_text("\n".join(lines) + "\n")
        return path


def main() -> int:
    return Suite().run()


if __name__ == "__main__":
    raise SystemExit(main())
