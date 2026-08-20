#!/usr/bin/env python3
"""Build, test and score an exchange-core long-horizon submission."""

from __future__ import annotations

import argparse
import grp
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET

import yaml

from artifact_registry import register_artifact, resolve_best_artifact
from integrity_check import inspect_submission, inspect_trajectory


TASK_ID = "exchange_core_throughput_long"
AVERAGE_RE = re.compile(r"Average:\s*([0-9]+(?:\.[0-9]+)?)\s*MT/s")
LATENCY_P99_RE = re.compile(r"99\.0%=([0-9]+(?:\.[0-9]+)?)(µs|us|ms|s)")
MANIFEST_NAME = "submission_manifest.json"
BASE_COMMIT = "2f8548749839e9095c8dc597e4b61521d259fa5d"
ALLOWED_ARCHIVE_ROOTS = ("src/main/",)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_archive_name(name: str) -> str:
    while name.startswith("./"):
        name = name[2:]
    return name


def archive_member_allowed(name: str) -> bool:
    normalized = normalize_archive_name(name)
    return normalized == MANIFEST_NAME or any(normalized.startswith(root) for root in ALLOWED_ARCHIVE_ROOTS)


def source_tree_digest(workspace: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(workspace).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def replace_submission_tree(archive_path: Path, workspace: Path) -> dict:
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        normalized_names = [normalize_archive_name(member.name) for member in members]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("提交归档包含重复路径")
        try:
            manifest_member = next(member for member in members if normalize_archive_name(member.name) == MANIFEST_NAME)
        except StopIteration as exc:
            raise ValueError("提交缺少submission_manifest.json") from exc
        manifest_source = archive.extractfile(manifest_member)
        if manifest_source is None:
            raise ValueError("无法读取submission_manifest.json")
        manifest = json.load(manifest_source)
        if manifest.get("schema_version") != 1:
            raise ValueError("不支持的提交Manifest版本")
        if manifest.get("base_commit") != BASE_COMMIT:
            raise ValueError("提交基线版本不匹配")
        if manifest.get("replacement_roots") != ["src/main"]:
            raise ValueError("提交替换根目录不符合约定")
        expected = {entry["path"]: entry for entry in manifest.get("files", [])}
        if not expected or len(expected) != len(manifest.get("files", [])):
            raise ValueError("提交Manifest为空或包含重复文件")

        replacement_root = workspace / "src/main"
        if replacement_root.exists():
            shutil.rmtree(replacement_root)

        extracted: set[str] = set()
        for member in members:
            name = normalize_archive_name(member.name)
            if name == MANIFEST_NAME:
                continue
            if not name:
                raise ValueError("提交包含空路径")
            if member.issym() or member.islnk():
                raise ValueError(f"禁止提交链接：{name}")
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError(f"非法归档路径：{name}")
            if not archive_member_allowed(name):
                raise ValueError(f"提交包含未允许路径：{name}")
            if member.isdir():
                continue
            if name not in expected:
                raise ValueError(f"提交文件未在Manifest声明：{name}")
            destination = (workspace / name).resolve()
            if workspace.resolve() not in destination.parents:
                raise ValueError(f"归档路径越界：{name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"无法读取归档成员：{name}")
            with destination.open("wb") as output:
                shutil.copyfileobj(source, output)
            payload = destination.read_bytes()
            entry = expected[name]
            if len(payload) != int(entry["size"]) or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise ValueError(f"提交文件摘要不匹配：{name}")
            extracted.add(name)

        missing = sorted(set(expected) - extracted)
        if missing:
            raise ValueError(f"Manifest声明文件未提交：{missing[0]}")
        files = sorted(path for path in replacement_root.rglob("*") if path.is_file())
        if source_tree_digest(workspace, files) != manifest.get("tree_sha256"):
            raise ValueError("提交源码树摘要不匹配")
        return manifest


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


def execute(
    command: list[str],
    workspace: Path,
    timeout_seconds: int,
    measure_resources: bool = False,
    run_as_user: str | None = None,
) -> dict:
    resource_token = secrets.token_hex(12)
    actual_command = command
    if measure_resources:
        actual_command = [
            "/usr/bin/time",
            "-f",
            f"__JUDGE_RESOURCE_{resource_token}__ user=%U system=%S max_rss_kb=%M",
            *command,
        ]
    started = time.monotonic()
    child_environment = os.environ.copy()
    preexec_fn = None
    if run_as_user:
        user = pwd.getpwnam(run_as_user)
        group = grp.getgrgid(user.pw_gid)
        child_environment["HOME"] = user.pw_dir

        def drop_privileges() -> None:
            os.setgroups([])
            os.setgid(group.gr_gid)
            os.setuid(user.pw_uid)

        preexec_fn = drop_privileges
    try:
        result = subprocess.run(
            actual_command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=child_environment,
            preexec_fn=preexec_fn,
        )
        resource_values = {"cpu_seconds": None, "max_rss_mb": None}
        if measure_resources:
            pattern = re.compile(
                rf"__JUDGE_RESOURCE_{resource_token}__ user=([0-9.]+) system=([0-9.]+) max_rss_kb=([0-9]+)"
            )
            match = pattern.search(result.stderr)
            if match:
                resource_values = {
                    "cpu_seconds": float(match.group(1)) + float(match.group(2)),
                    "max_rss_mb": float(match.group(3)) / 1024.0,
                }
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": False,
            **resource_values,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": True,
            "cpu_seconds": None,
            "max_rss_mb": None,
        }


def junit_counts(reports: Path, expected_reports: list[str], exit_code: int) -> dict:
    total = passed = 0
    missing: list[str] = []
    malformed: list[str] = []
    for class_name in expected_reports:
        report = reports / f"TEST-{class_name}.xml"
        if not report.is_file():
            missing.append(class_name)
            total += 1
            continue
        try:
            root = ET.parse(report).getroot()
            tests = int(root.attrib.get("tests", 0))
            failures = int(root.attrib.get("failures", 0))
            errors = int(root.attrib.get("errors", 0))
            skipped = int(root.attrib.get("skipped", 0))
        except (ET.ParseError, OSError, TypeError, ValueError):
            malformed.append(class_name)
            total += 1
            continue
        if tests <= 0:
            malformed.append(class_name)
            total += 1
            continue
        total += tests
        passed += max(0, tests - failures - errors - skipped)
    return {
        "passed": passed,
        "total": total,
        "missing_reports": missing,
        "malformed_reports": malformed,
        "protocol_ok": exit_code == 0 and not missing and not malformed and total > 0,
    }


def prepare_runner_directory(path: Path, run_as_user: str) -> None:
    user = pwd.getpwnam(run_as_user)
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, user.pw_uid, user.pw_gid)
    path.chmod(0o750)


def freeze_candidate_inputs(workspace: Path) -> None:
    """Make candidate source, trusted build files and tests readable but immutable."""
    for path in workspace.rglob("*"):
        if path.is_symlink():
            continue
        path.chmod(0o555 if path.is_dir() else 0o444)
    workspace.chmod(0o555)


def clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(upper, max(lower, value))


def normalize_metric(value: float, floor: float | None, target: float | None, direction: str) -> float | None:
    if floor is None or target is None or not math.isfinite(floor) or not math.isfinite(target):
        return None
    if direction == "maximize" and target > floor:
        return clip((value - floor) / (target - floor))
    if direction == "minimize" and target < floor:
        return clip((floor - value) / (floor - target))
    return None


def find_average(output: str) -> float | None:
    matches = AVERAGE_RE.findall(output)
    return float(matches[-1]) if matches else None


def find_latency_p99_us(output: str) -> float | None:
    matches = LATENCY_P99_RE.findall(output)
    if not matches:
        return None
    value_text, unit = matches[-1]
    value = float(value_text)
    return value * {"µs": 1.0, "us": 1.0, "ms": 1000.0, "s": 1_000_000.0}[unit]


def metric_value(
    kind: str,
    output: str,
    *,
    duration_seconds: float | None = None,
    transactions_total: int | None = None,
) -> float | None:
    if kind == "throughput":
        if duration_seconds and transactions_total:
            return float(transactions_total) / duration_seconds / 1_000_000.0
        return None
    if kind == "latency_p99_us":
        return find_latency_p99_us(output)
    raise ValueError(f"未知Metric类型：{kind}")


def aggregate_metric(values: list[tuple[float, float | None]]) -> float:
    total_weight = sum(weight for weight, _ in values)
    if total_weight <= 0:
        return 0.0
    return sum(weight * (value if value is not None else 0.0) for weight, value in values) / total_weight


def official_scores(test_score: float, metric_score: float, scoring: dict, hard_gate_reasons: list[str]) -> tuple[float, float]:
    progress = (
        float(scoring["score"]["test_weight"]) * test_score
        + float(scoring["score"]["metric_weight"]) * metric_score
    )
    return clip(progress), 0.0 if hard_gate_reasons else clip(progress)


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
    submission_group = parser.add_mutually_exclusive_group(required=True)
    submission_group.add_argument("--submission", help="Agent提交的tar.gz")
    submission_group.add_argument("--evaluate-best", action="store_true", help="使用可信账本中的最佳产物")
    parser.add_argument("--phase", choices=("feedback", "final"), default="feedback")
    parser.add_argument("--output", required=True)
    parser.add_argument("--previous-report")
    parser.add_argument("--remaining-seconds", type=int, default=0)
    parser.add_argument("--baseline-root", default="/opt/baseline")
    parser.add_argument("--author-root", default="/opt/author_only")
    parser.add_argument("--verifier-root", default="/opt/verifier")
    parser.add_argument("--trajectory-log", default="/trajectory/commands.jsonl")
    parser.add_argument("--runner-user", default="judge-runner")
    parser.add_argument("--artifact-store", default="/reports/artifacts")
    parser.add_argument("--history-file", default="/reports/history.jsonl")
    parser.add_argument("--best-record", default="/reports/best.json")
    parser.add_argument("--development-skip-trajectory-check", action="store_true")
    args = parser.parse_args()

    verifier_root = Path(args.verifier_root)
    author_root = Path(args.author_root)
    scoring = load_yaml(verifier_root / "scoring.yaml")
    workload_config = load_yaml(verifier_root / "workloads" / f"{args.phase}.yaml")
    calibration = load_json(author_root / "calibration.json")
    previous = load_json(Path(args.previous_report)) if args.previous_report else None
    best_record = Path(args.best_record)
    submission_path = resolve_best_artifact(best_record) if args.evaluate_best else Path(args.submission)

    with tempfile.TemporaryDirectory(prefix="exchange-core-judge-") as temporary:
        temporary_root = Path(temporary)
        temporary_root.chmod(0o755)
        workspace = temporary_root / "exchange-core"
        shutil.copytree(Path(args.baseline_root), workspace)
        submission_error = None
        try:
            replace_submission_tree(submission_path, workspace)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, tarfile.TarError) as exc:
            submission_error = f"submission_protocol:{type(exc).__name__}:{exc}"

        violations = [submission_error] if submission_error else inspect_submission(workspace)
        if not args.development_skip_trajectory_check and not args.evaluate_best:
            violations.extend(inspect_trajectory(Path(args.trajectory_log)))
        violations = sorted(set(item for item in violations if item))
        if not submission_error:
            install_hidden_tests(workspace, args.phase, author_root)
            freeze_candidate_inputs(workspace)
            prepare_runner_directory(workspace / "target", args.runner_user)
        reports_root = Path(args.artifact_store).parent
        reports_root.mkdir(parents=True, exist_ok=True)
        reports_root.chmod(0o700)

        test_groups: dict[str, dict] = {}
        mandatory_failed = bool(submission_error)
        test_protocol_failed = False

        for group in scoring["test_groups"]:
            if submission_error:
                result = {"exit_code": 125, "timed_out": False, "duration_seconds": 0.0}
                counts = {
                    "passed": 0,
                    "total": 1,
                    "missing_reports": [],
                    "malformed_reports": [],
                    "protocol_ok": False,
                }
            elif group.get("verifier") == "command_exit":
                result = execute(
                    group["command"], workspace, int(group["timeout_seconds"]), run_as_user=args.runner_user
                )
                counts = {
                    "passed": 1 if result["exit_code"] == 0 else 0,
                    "total": 1,
                    "missing_reports": [],
                    "malformed_reports": [],
                    "protocol_ok": result["exit_code"] == 0,
                }
            else:
                report_dir = temporary_root / "junit" / group["id"]
                prepare_runner_directory(report_dir, args.runner_user)
                command = [*group["command"], f"-Dsurefire.reportsDirectory={report_dir}"]
                result = execute(command, workspace, int(group["timeout_seconds"]), run_as_user=args.runner_user)
                counts = junit_counts(report_dir, group.get("expected_reports", []), result["exit_code"])
                if counts["missing_reports"] or counts["malformed_reports"]:
                    test_protocol_failed = True

            passed, total = counts["passed"], counts["total"]
            ratio = passed / total if total else 0.0
            test_groups[group["id"]] = {
                "title": group["title"],
                "passed": passed,
                "total": total,
                "score": round(ratio, 6),
                "exit_code": result["exit_code"],
                "timed_out": result["timed_out"],
                "duration_seconds": result["duration_seconds"],
                "protocol_ok": counts["protocol_ok"],
                "missing_reports": counts["missing_reports"],
                "malformed_reports": counts["malformed_reports"],
            }
            if group.get("mandatory", False) and (ratio < 1.0 or not counts["protocol_ok"]):
                mandatory_failed = True

        test_score = sum(
            float(group["weight"]) * test_groups[group["id"]]["score"]
            for group in scoring["test_groups"]
        )

        metrics: dict[str, dict] = {}
        metric_protocol_failed = False
        weighted_metric = 0.0
        calibration_ready = calibration.get("status") == "ready"

        if not mandatory_failed and not violations:
            phase_calibration = calibration.get(args.phase, {})
            for workload in workload_config["workloads"]:
                report_dir = temporary_root / "junit" / f"metric-{workload['id']}"
                prepare_runner_directory(report_dir, args.runner_user)
                command = [*workload["command"], f"-Dsurefire.reportsDirectory={report_dir}"]
                result = execute(
                    command,
                    workspace,
                    int(workload["timeout_seconds"]),
                    measure_resources=bool(workload.get("measure_resources", False)),
                    run_as_user=args.runner_user,
                )
                counts = junit_counts(report_dir, workload.get("expected_reports", []), result["exit_code"])
                combined = result["stdout"] + "\n" + result["stderr"]
                value = (
                    metric_value(
                        workload["kind"],
                        combined,
                        duration_seconds=result["duration_seconds"],
                        transactions_total=workload.get("transactions_total"),
                    )
                    if counts["protocol_ok"]
                    else None
                )
                values = phase_calibration.get(workload["id"], {})
                normalized = (
                    normalize_metric(value, values.get("floor"), values.get("target"), workload["direction"])
                    if value is not None and calibration_ready
                    else None
                )
                weight = float(workload["weight"])
                weighted_metric += weight * (normalized if normalized is not None else 0.0)
                if value is None or not counts["protocol_ok"]:
                    metric_protocol_failed = True
                metrics[workload["id"]] = {
                    "title": workload["title"],
                    "value": value,
                    "unit": workload["unit"],
                    "direction": workload["direction"],
                    "weight": weight,
                    "normalized_score": round(normalized, 6) if normalized is not None else None,
                    "exit_code": result["exit_code"],
                    "timed_out": result["timed_out"],
                    "duration_seconds": result["duration_seconds"],
                    "reported_value": find_average(combined) if workload["kind"] == "throughput" else None,
                    "protocol_ok": counts["protocol_ok"],
                    "missing_reports": counts["missing_reports"],
                }

                for derived in workload.get("derived_metrics", []):
                    derived_value = None
                    if derived["kind"] == "cpu_efficiency" and result.get("cpu_seconds"):
                        derived_value = float(derived["transactions_total"]) / result["cpu_seconds"] / 1_000_000.0
                    elif derived["kind"] == "peak_rss_mb":
                        derived_value = result.get("max_rss_mb")
                    derived_values = phase_calibration.get(derived["id"], {})
                    derived_normalized = (
                        normalize_metric(
                            derived_value,
                            derived_values.get("floor"),
                            derived_values.get("target"),
                            derived["direction"],
                        )
                        if derived_value is not None and calibration_ready
                        else None
                    )
                    derived_weight = float(derived["weight"])
                    weighted_metric += derived_weight * (
                        derived_normalized if derived_normalized is not None else 0.0
                    )
                    if derived_value is None:
                        metric_protocol_failed = True
                    metrics[derived["id"]] = {
                        "title": derived["title"],
                        "value": round(derived_value, 6) if derived_value is not None else None,
                        "unit": derived["unit"],
                        "direction": derived["direction"],
                        "weight": derived_weight,
                        "normalized_score": (
                            round(derived_normalized, 6) if derived_normalized is not None else None
                        ),
                        "source_workload": workload["id"],
                        "protocol_ok": derived_value is not None,
                    }

        expected_metric_weight = sum(
            float(workload["weight"])
            + sum(float(item["weight"]) for item in workload.get("derived_metrics", []))
            for workload in workload_config["workloads"]
        )
        if not math.isclose(expected_metric_weight, 1.0, abs_tol=1e-9):
            metric_protocol_failed = True
        calibration_required = not calibration_ready or (
            any(item.get("normalized_score") is None for item in metrics.values()) if metrics else True
        )
        metric_score = weighted_metric / expected_metric_weight if expected_metric_weight > 0 else 0.0

        hard_gate_reasons = []
        if test_groups.get("build", {}).get("score", 0.0) < 1.0:
            hard_gate_reasons.append("build_failure")
        if mandatory_failed:
            hard_gate_reasons.append("mandatory_test_failure")
        if test_protocol_failed:
            hard_gate_reasons.append("test_protocol_failure")
        if violations:
            hard_gate_reasons.append("integrity_violation")
        if metric_protocol_failed:
            hard_gate_reasons.append("metric_protocol_failure")
        if calibration_required:
            hard_gate_reasons.append("calibration_missing")

        score_progress, score_current = official_scores(test_score, metric_score, scoring, hard_gate_reasons)
        artifact_valid = not hard_gate_reasons

        prior_score = float(previous.get("score_current", 0.0)) if previous else 0.0
        score_current = round(clip(score_current), 6)
        reward_delta = round(score_current - prior_score, 6)

        report = {
            "task_id": TASK_ID,
            "phase": args.phase,
            "score_current": score_current,
            "score_progress": round(clip(score_progress), 6),
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

        registry = register_artifact(
            submission=submission_path,
            report_without_registry=report,
            valid=artifact_valid,
            score=score_current,
            phase=args.phase,
            artifact_store=Path(args.artifact_store),
            history_file=Path(args.history_file),
            best_record=best_record,
        )
        report.update(registry)

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
