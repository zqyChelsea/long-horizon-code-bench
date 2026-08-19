#!/usr/bin/env python3
"""Static integrity checks for an extracted candidate workspace."""

from __future__ import annotations

from pathlib import Path


ALLOWED_ROOTS = (Path("src/main"), Path("pom.xml"), Path(".mvn"))
FORBIDDEN_FRAGMENTS = (
    "/opt/verifier",
    "/opt/author_only",
    "hidden_tests",
    "latest_report.json",
    "score_current",
)


def is_allowed(relative: Path) -> bool:
    return any(relative == root or root in relative.parents for root in ALLOWED_ROOTS)


def inspect_submission(root: Path) -> list[str]:
    violations: list[str] = []
    root = root.resolve()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink():
            violations.append(f"symbolic_link:{relative.as_posix()}")
            continue
        if path.is_file() and is_allowed(relative):
            if path.stat().st_size > 20 * 1024 * 1024:
                violations.append(f"oversized_file:{relative.as_posix()}")
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
    return sorted(set(violations))

