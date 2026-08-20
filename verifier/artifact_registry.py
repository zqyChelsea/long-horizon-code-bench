#!/usr/bin/env python3
"""Trusted, append-only artifact history and best-artifact management."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_best(best_record: Path) -> dict | None:
    if not best_record.is_file():
        return None
    return json.loads(best_record.read_text(encoding="utf-8"))


def resolve_best_artifact(best_record: Path) -> Path:
    best = load_best(best_record)
    if not best:
        raise FileNotFoundError("尚无有效最佳产物")
    artifact = Path(best["artifact_path"])
    if not artifact.is_file():
        raise FileNotFoundError(f"最佳产物不存在：{artifact}")
    actual = file_sha256(artifact)
    if actual != best["artifact_sha256"]:
        raise ValueError("最佳产物摘要不匹配")
    return artifact


def register_artifact(
    *,
    submission: Path,
    report_without_registry: dict,
    valid: bool,
    score: float,
    phase: str,
    artifact_store: Path,
    history_file: Path,
    best_record: Path,
) -> dict:
    artifact_sha256 = file_sha256(submission)
    report_sha256 = canonical_sha256(report_without_registry)
    artifact_store.mkdir(parents=True, exist_ok=True)
    report_store = artifact_store.parent / "evaluation_reports"
    report_store.mkdir(parents=True, exist_ok=True)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    lock_path = history_file.with_suffix(history_file.suffix + ".lock")

    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current_best = load_best(best_record)
        stored_artifact = artifact_store / f"{artifact_sha256}.tar.gz"
        previous_record = None
        sequence = 1
        if history_file.is_file():
            lines = [line for line in history_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                previous_record = json.loads(lines[-1])
                sequence = int(previous_record.get("sequence", len(lines))) + 1

        if valid and not stored_artifact.exists():
            temporary = artifact_store / f".{artifact_sha256}.{os.getpid()}.tmp"
            shutil.copy2(submission, temporary)
            if file_sha256(temporary) != artifact_sha256:
                temporary.unlink(missing_ok=True)
                raise ValueError("保存产物时摘要发生变化")
            os.replace(temporary, stored_artifact)

        stored_report = report_store / f"{report_sha256}.json"
        if not stored_report.exists():
            atomic_json_write(stored_report, report_without_registry)

        record = {
            "artifact_id": artifact_sha256,
            "artifact_sha256": artifact_sha256,
            "artifact_path": str(stored_artifact) if valid else None,
            "created_at_unix": int(time.time()),
            "phase": phase,
            "previous_artifact_id": previous_record.get("artifact_id") if previous_record else None,
            "report_sha256": report_sha256,
            "report_path": str(stored_report),
            "score": round(float(score), 6),
            "sequence": sequence,
            "task_id": report_without_registry.get("task_id"),
            "valid": bool(valid),
        }
        with history_file.open("a", encoding="utf-8") as history:
            history.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            history.flush()
            os.fsync(history.fileno())

        best_updated = False
        if phase == "feedback" and valid and (
            current_best is None or float(score) > float(current_best.get("score", -1.0))
        ):
            atomic_json_write(best_record, record)
            current_best = record
            best_updated = True

        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    return {
        "artifact_id": artifact_sha256,
        "artifact_sha256": artifact_sha256,
        "artifact_valid": bool(valid),
        "best_artifact_id": current_best.get("artifact_id") if current_best else None,
        "score_best": round(float(current_best.get("score", 0.0)), 6) if current_best else 0.0,
        "best_updated": best_updated,
    }
