#!/usr/bin/env python3
"""Static validation for the task package; requires only the Python stdlib."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import py_compile
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "raw_request.md",
    "qualification.md",
    "source_metadata.yaml",
    "task/task.md",
    "spec/evaluation_contract.md",
    "environment/work/Dockerfile",
    "environment/judge/Dockerfile",
    "environment/resource_limits.yaml",
    "public_tests/run_public_tests.sh",
    "submission/create_submission.py",
    "submission/submit.sh",
    "verifier/run_verifier.py",
    "verifier/integrity_check.py",
    "verifier/scoring.yaml",
    "verifier/report_schema.json",
    "author_only/requirements.yaml",
    "author_only/calibration.json",
    "author_only/source_manifest.json",
    "author_only/hidden_tests/feedback/FeedbackThroughput.java",
    "author_only/hidden_tests/final/FinalThroughput.java",
    "workspace/exchange-core/LICENSE.txt",
    "workspace/exchange-core/pom.xml",
)


def source_digest(root: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return len(files), digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"缺少文件：{relative}")

    source_root = ROOT / "workspace/exchange-core"
    if (source_root / ".git").exists():
        errors.append("冻结源码中不得包含.git目录")

    manifest_path = ROOT / "author_only/source_manifest.json"
    if manifest_path.exists() and source_root.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        file_count, digest = source_digest(source_root)
        if file_count != manifest["file_count"]:
            errors.append(f"冻结源码文件数变化：{file_count} != {manifest['file_count']}")
        if digest != manifest["tree_sha256"]:
            errors.append("冻结源码摘要与source_manifest.json不一致")

    for relative in ("verifier/report_schema.json", "author_only/calibration.json"):
        try:
            json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"JSON无效：{relative}: {exc}")

    for path in sorted(ROOT.rglob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"Python语法错误：{path.relative_to(ROOT)}: {exc.msg}")

    calibration_path = ROOT / "author_only/calibration.json"
    if calibration_path.exists():
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        if calibration.get("status") != "ready":
            warnings.append("性能Metric尚未在冻结硬件上完成floor/target校准")

    if errors:
        print("TASK_PACKAGE_VALID=0")
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("TASK_PACKAGE_VALID=1")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
