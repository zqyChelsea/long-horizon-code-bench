#!/usr/bin/env python3
"""Build, test and score an exchange-core long-horizon submission."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET

import yaml

from integrity_check import inspect_submission, inspect_trajectory


TASK_ID = "exchange_core_throughput_long"
AVERAGE_RE = re.compile(r"Average:\s*([0-9]+(?:\.[0-9]+)?)\s*MT/s")
ALLOWED_ARCHIVE_ROOTS = ("src/main/", "pom.xml", ".mvn/")


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def archive_member_allowed(name: str) -> bool:
    normalized = name.lstrip("./")
    return normalized == "pom.xml" or any(normalized.startswith(root) for root in ALLOWED_ARCHIVE_ROOTS if root != "pom.xml")


def overlay_submission(archive_path: Path, workspace: Path) -> None:
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive.getmembers():
            name = member.name.lstrip("./")
            if not name or member.isdir():
                continue
            if member.issym() or member.islnk():
                raise ValueError(f"禁止提交链接：{name}")
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError(f"非法归档路径：{name}")
            if not archive_member_allowed(name):
                raise ValueError(f"提交包含未允许路径：{name}")
            destination = (workspace / name).resolve()
            if workspace.resolve() not in destination.parents:
                raise ValueError(f"归档路径越界：{name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"无法读取归档成员：{name}")
            with destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def install_hidden_tests(workspace: Path, phase: str, author_root: Path) -> None:
    common = author_root / "hidden_tests" / "common"
    phase_dir = author_root / "hidden_tests" / phase
    destination = workspace / "src/test/java/exchange/core2/tests/perf"
    destination.mkdir(parents=True, exist_ok=True)
    for source_dir in (common, phase_dir):
        if not source_dir.exists():
            continue
        for source in source_dir.rglob("*.java"):
            shutil.copy2(source, destination / source.name)


def clear_test_reports(workspace: Path) -> None:
    report_dir = workspace / "target/surefire-reports"
    if report_dir.exists():
        shutil.rmtree(report_dir)


def execute(command: list[str], workspace: Path, timeout_seconds: int) -> dict:
    clear_test_reports(workspace)
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": True,
        }


def junit_counts(workspace: Path, exit_code: int) -> tuple[int, int]:
    reports = workspace / "target/surefire-reports"
    total = passed = 0
    if reports.exists():
        for report in reports.glob("TEST-*.xml"):
            try:
                root = ET.parse(report).getroot()
            except (ET.ParseError, OSError):
                continue
            tests = int(root.attrib.get("tests", 0))
            failures = int(root.attrib.get("failures", 0))
            errors = int(root.attrib.get("errors", 0))
            skipped = int(root.attrib.get("skipped", 0))
            total += tests
            passed += max(0, tests - failures - errors - skipped)
    if total == 0:
        return (1 if exit_code == 0 else 0, 1)
    return passed, total


def clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(upper, max(lower, value))


def normalize_metric(value: float, floor: float | None, target: float | None) -> float | None:
    if floor is None or target is None or not math.isfinite(floor) or not math.isfinite(target) or target <= floor:
        return None
    return clip((value - floor) / (target - floor))


def find_average(output: str) -> float | None:
    matches = AVERAGE_RE.findall(output)
    return float(matches[-1]) if matches else None


def regressions(previous: dict | None, current_groups: dict) -> list[str]:
    if not previous:
        return []
    old_groups = previous.get("test_groups", {})
    result = []
    for group_id, current in current_groups.items():
        old = old_groups.get(group_id)
        if old and current["passed"] < old.get("passed", 0):
            result.append(group_id)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, help="Agent提交的tar.gz")
    parser.add_argument("--phase", choices=("feedback", "final"), default="feedback")
    parser.add_argument("--output", required=True)
    parser.add_argument("--previous-report")
    parser.add_argument("--best-score", type=float, default=0.0)
    parser.add_argument("--remaining-seconds", type=int, default=0)
    parser.add_argument("--baseline-root", default="/opt/baseline")
    parser.add_argument("--author-root", default="/opt/author_only")
    parser.add_argument("--verifier-root", default="/opt/verifier")
    parser.add_argument("--trajectory-log", default="/trajectory/commands.jsonl")
    parser.add_argument("--development-skip-trajectory-check", action="store_true")
    args = parser.parse_args()

    verifier_root = Path(args.verifier_root)
    author_root = Path(args.author_root)
    scoring = load_yaml(verifier_root / "scoring.yaml")
    workload_config = load_yaml(verifier_root / "workloads" / f"{args.phase}.yaml")
    calibration = load_json(author_root / "calibration.json")
    previous = load_json(Path(args.previous_report)) if args.previous_report else None

    with tempfile.TemporaryDirectory(prefix="exchange-core-judge-") as temporary:
        workspace = Path(temporary) / "exchange-core"
        shutil.copytree(Path(args.baseline_root), workspace)
        overlay_submission(Path(args.submission), workspace)
        install_hidden_tests(workspace, args.phase, author_root)

        violations = inspect_submission(workspace)
        if not args.development_skip_trajectory_check:
            violations.extend(inspect_trajectory(Path(args.trajectory_log)))
            violations = sorted(set(violations))
        test_groups: dict[str, dict] = {}
        mandatory_failed = False

        for group in scoring["test_groups"]:
            result = execute(group["command"], workspace, int(group["timeout_seconds"]))
            passed, total = junit_counts(workspace, result["exit_code"])
            ratio = passed / total if total else 0.0
            test_groups[group["id"]] = {
                "title": group["title"],
                "passed": passed,
                "total": total,
                "score": round(ratio, 6),
                "exit_code": result["exit_code"],
                "timed_out": result["timed_out"],
                "duration_seconds": result["duration_seconds"],
            }
            if group.get("mandatory", False) and ratio < 1.0:
                mandatory_failed = True

        test_score = sum(
            float(group["weight"]) * test_groups[group["id"]]["score"]
            for group in scoring["test_groups"]
        )

        metrics: dict[str, dict] = {}
        metric_protocol_failed = False
        active_weight = 0.0
        weighted_metric = 0.0

        if not mandatory_failed and not violations:
            phase_calibration = calibration.get(args.phase, {})
            for workload in workload_config["workloads"]:
                result = execute(workload["command"], workspace, int(workload["timeout_seconds"]))
                combined = result["stdout"] + "\n" + result["stderr"]
                value = find_average(combined) if result["exit_code"] == 0 else None
                values = phase_calibration.get(workload["id"], {})
                normalized = normalize_metric(value, values.get("floor"), values.get("target")) if value is not None else None
                if value is None:
                    metric_protocol_failed = True
                if normalized is not None:
                    weight = float(workload["weight"])
                    active_weight += weight
                    weighted_metric += weight * normalized
                metrics[workload["id"]] = {
                    "title": workload["title"],
                    "value": value,
                    "unit": "MT/s",
                    "direction": workload["direction"],
                    "normalized_score": round(normalized, 6) if normalized is not None else None,
                    "exit_code": result["exit_code"],
                    "timed_out": result["timed_out"],
                    "duration_seconds": result["duration_seconds"],
                }

        calibration_required = any(item.get("normalized_score") is None for item in metrics.values()) if metrics else True
        metric_score = weighted_metric / active_weight if active_weight > 0 else 0.0

        hard_gate_reasons = []
        if test_groups.get("build", {}).get("score", 0.0) < 1.0:
            hard_gate_reasons.append("build_failure")
        if mandatory_failed:
            hard_gate_reasons.append("mandatory_test_failure")
        if violations:
            hard_gate_reasons.append("integrity_violation")
        if metric_protocol_failed:
            hard_gate_reasons.append("metric_protocol_failure")

        if violations or test_groups.get("build", {}).get("score", 0.0) < 1.0:
            score_current = 0.0
        else:
            effective_metric = 0.0 if mandatory_failed else metric_score
            score_current = (
                float(scoring["score"]["test_weight"]) * test_score
                + float(scoring["score"]["metric_weight"]) * effective_metric
            )

        prior_score = float(previous.get("score_current", 0.0)) if previous else 0.0
        score_current = round(clip(score_current), 6)
        previous_best = float(previous.get("score_best", 0.0)) if previous else 0.0
        score_best = round(max(args.best_score, previous_best, score_current), 6)
        reward_delta = round(score_current - prior_score, 6)

        report = {
            "task_id": TASK_ID,
            "phase": args.phase,
            "score_current": score_current,
            "score_best": score_best,
            "reward_delta": reward_delta,
            "score_test": round(test_score, 6),
            "score_metric": round(metric_score, 6),
            "test_groups": test_groups,
            "metrics": metrics,
            "new_regressions": regressions(previous, test_groups),
            "hard_gate": {
                "passed": not hard_gate_reasons,
                "reasons": hard_gate_reasons,
            },
            "integrity_violations": violations,
            "remaining_seconds": max(0, args.remaining_seconds),
            "calibration_required": calibration_required,
        }

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
