#!/usr/bin/env python3
"""Measure floor or target values on the frozen evaluation machine."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import sys

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
    results: dict[str, dict] = {}

    for workload in config["workloads"]:
        values = []
        for _ in range(args.repeats):
            result = verifier.execute(workload["command"], workspace, int(workload["timeout_seconds"]))
            value = verifier.find_average(result["stdout"] + "\n" + result["stderr"])
            if result["exit_code"] != 0 or value is None:
                raise SystemExit(f"校准失败：{workload['id']}")
            values.append(value)
        results[workload["id"]] = {
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
