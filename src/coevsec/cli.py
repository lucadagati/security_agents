"""Command-line interface: run experiments, analyse runs, ingest into Postgres."""

from __future__ import annotations

import argparse
import json
import sys

from coevsec.experiments import run_experiment


def _cmd_run(args: argparse.Namespace) -> int:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        from telegram_notify import _load_dotenv
        _load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except Exception:
        pass
    aggregate = run_experiment(args.config)
    print(json.dumps(aggregate, indent=2))
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    from coevsec.analysis.engine import analyze_run

    report = analyze_run(args.run, out_dir=args.out)
    print(json.dumps(report, indent=2, default=str))
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    from coevsec.telemetry.postgres import available, ingest_run

    if not available():
        print("Postgres not available (install extras + set COEVSEC_PG_DSN)", file=sys.stderr)
        return 1
    rows = ingest_run(args.run)
    print(f"ingested {rows} rows")
    return 0


def _cmd_ladder(args: argparse.Namespace) -> int:
    """Run the 1A-vs-1D adaptation ladder (proposal section 35) and compare metrics."""
    from pathlib import Path

    from coevsec.analysis.engine import analyze_run
    from coevsec.metrics import adaptation_gain

    configs_dir = Path(args.configs_dir)
    files = sorted(configs_dir.glob("*.yaml"))
    if not files:
        print(f"no configs in {configs_dir}", file=sys.stderr)
        return 1

    results = []
    for path in files:
        print(f"running {path} ...", file=sys.stderr)
        aggregate = run_experiment(str(path))
        if args.analyze and aggregate.get("run_dir"):
            analyze_run(aggregate["run_dir"])
        results.append(aggregate)

    baseline_asr = next(
        (r["attack_success_rate"] for r in results if "static_static" in r.get("name", "")),
        results[0]["attack_success_rate"] if results else 0.0,
    )
    table = []
    for r in results:
        row = {
            "name": r.get("name"),
            "asr": r.get("attack_success_rate"),
            "dr": r.get("detection_rate"),
            "cep": r.get("coevolutionary_pressure"),
            "novelty": r.get("behavioral_novelty"),
            "adaptation_gain_vs_static": adaptation_gain(
                r.get("attack_success_rate", 0.0), baseline_asr
            ),
            "run_dir": r.get("run_dir"),
        }
        table.append(row)
    print(json.dumps({"ladder": table}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coevsec", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run an experiment from a YAML config")
    p_run.add_argument("--config", required=True)
    p_run.set_defaults(func=_cmd_run)

    p_an = sub.add_parser("analyze", help="analyse a completed run directory")
    p_an.add_argument("--run", required=True)
    p_an.add_argument("--out", default=None)
    p_an.set_defaults(func=_cmd_analyze)

    p_in = sub.add_parser("ingest", help="ingest a run's trajectories into Postgres")
    p_in.add_argument("--run", required=True)
    p_in.set_defaults(func=_cmd_ingest)

    p_lad = sub.add_parser(
        "ladder",
        help="run the 1-attacker vs 1-defender adaptation ladder (section 35)",
    )
    p_lad.add_argument("--configs-dir", default="configs/ladder")
    p_lad.add_argument("--analyze", action="store_true", default=True)
    p_lad.add_argument("--no-analyze", dest="analyze", action="store_false")
    p_lad.set_defaults(func=_cmd_ladder)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
