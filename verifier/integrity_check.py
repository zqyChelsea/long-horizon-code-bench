#!/usr/bin/env python3
"""Static integrity checks for an extracted candidate workspace."""

from __future__ import annotations

import json
from pathlib import Path


ALLOWED_ROOTS = (Path("src/main"), Path("pom.xml"), Path(".mvn"))
FORBIDDEN_FRAGMENTS = (
    "/opt/verifier",
    "/opt/author_only",
    "hidden_tests",
    "latest_report.json",
    "score_current",
)
FORBIDDEN_SUFFIXES = {".class", ".jar", ".zip", ".tar", ".gz", ".so", ".dylib", ".dll", ".exe"}
BINARY_MAGICS = (b"\x7fELF", b"MZ", b"\xca\xfe\xba\xbe", b"PK\x03\x04")
MAX_ALLOWED_FILES = 5000
MAX_ALLOWED_BYTES = 100 * 1024 * 1024


def is_allowed(relative: Path) -> bool:
    return any(relative == root or root in relative.parents for root in ALLOWED_ROOTS)


def inspect_submission(root: Path) -> list[str]:
    violations: list[str] = []
    root = root.resolve()
    allowed_file_count = 0
    allowed_total_bytes = 0
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink():
            violations.append(f"symbolic_link:{relative.as_posix()}")
            continue
        if path.is_file() and is_allowed(relative):
            stat = path.stat()
            allowed_file_count += 1
            allowed_total_bytes += stat.st_size
            if stat.st_size > 20 * 1024 * 1024:
                violations.append(f"oversized_file:{relative.as_posix()}")
                continue
            if stat.st_mode & 0o111:
                violations.append(f"executable_file:{relative.as_posix()}")
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                violations.append(f"forbidden_binary_type:{relative.as_posix()}")
                continue
            try:
                with path.open("rb") as handle:
                    header = handle.read(4)
            except OSError:
                header = b""
            if any(header.startswith(magic) for magic in BINARY_MAGICS):
                violations.append(f"binary_payload:{relative.as_posix()}")
                continue
            if path.suffix.lower() not in {".java", ".xml", ".config", ".properties", ".md", ""}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for fragment in FORBIDDEN_FRAGMENTS:
                if fragment in text:
                    violations.append(f"forbidden_reference:{relative.as_posix()}:{fragment}")
    if allowed_file_count > MAX_ALLOWED_FILES:
        violations.append(f"too_many_files:{allowed_file_count}")
    if allowed_total_bytes > MAX_ALLOWED_BYTES:
        violations.append(f"submission_too_large:{allowed_total_bytes}")
    return sorted(set(violations))


def inspect_trajectory(path: Path) -> list[str]:
    violations: list[str] = []
    if not path.is_file():
        return ["trajectory_log_missing"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ["trajectory_log_unreadable"]
    for line_number, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            violations.append(f"trajectory_log_malformed:{line_number}")
            continue
        if event.get("allowed") is False and event.get("blocking") is True:
            reason = str(event.get("reason", "unknown"))
            violations.append(f"trajectory_policy_violation:{line_number}:{reason}")
    return sorted(set(violations))
