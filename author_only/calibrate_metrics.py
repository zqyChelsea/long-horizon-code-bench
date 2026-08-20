#!/usr/bin/env python3
"""Measure floor or target values on the frozen evaluation machine."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--phase", choices=("feedback", "final"), required=True)
    parser.add_argument("--kind", choices=("floor", "target"), required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--verifier-root", required=True)
    parser.add_argument("--author-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    verifier_root = Path(args.verifier_root).resolve()
    author_root = Path(args.author_root).resolve()
    output_path = Path(args.output).resolve()

    sys.path.insert(0, str(verifier_root))
    module_spec = importlib.util.spec_from_file_location("run_verifier", verifier_root / "run_verifier.py")
    if module_spec is None or module_spec.loader is None:
        raise SystemExit("无法加载run_verifier.py")
    verifier = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(verifier)

    config = yaml.safe_load((verifier_root / "workloads" / f"{args.phase}.yaml").read_text())
    verifier.install_hidden_tests(workspace, args.phase, author_root)
    collected: dict[str, list[float]] = {}

    for workload in config["workloads"]:
        for _ in range(args.repeats):
            with tempfile.TemporaryDirectory(prefix="calibration-junit-") as report_directory:
                report_dir = Path(report_directory)
                command = [*workload["command"], f"-Dsurefire.reportsDirectory={report_dir}"]
                result = verifier.execute(
                    command,
                    workspace,
                    int(workload["timeout_seconds"]),
                    measure_resources=bool(workload.get("measure_resources", False)),
                )
                counts = verifier.junit_counts(
                    report_dir,
                    workload.get("expected_reports", []),
                    result["exit_code"],
                )
                output = result["stdout"] + "\n" + result["stderr"]
                value = (
                    verifier.metric_value(
                        workload["kind"],
                        output,
                        duration_seconds=result["duration_seconds"],
                        transactions_total=workload.get("transactions_total"),
                    )
                    if counts["protocol_ok"]
                    else None
                )
                if value is None:
                    raise SystemExit(f"校准失败：{workload['id']}")
                collected.setdefault(workload["id"], []).append(value)

                for derived in workload.get("derived_metrics", []):
                    if derived["kind"] == "cpu_efficiency" and result.get("cpu_seconds"):
                        derived_value = float(derived["transactions_total"]) / result["cpu_seconds"] / 1_000_000.0
                    elif derived["kind"] == "peak_rss_mb":
                        derived_value = result.get("max_rss_mb")
                    else:
                        derived_value = None
                    if derived_value is None:
                        raise SystemExit(f"校准失败：{derived['id']}")
                    collected.setdefault(derived["id"], []).append(float(derived_value))

    results: dict[str, dict] = {}
    for metric_id, values in collected.items():
        results[metric_id] = {
            "kind": args.kind,
            "values": values,
            "median": statistics.median(values),
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
