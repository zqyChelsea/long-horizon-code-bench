#!/usr/bin/env python3
"""Fail-closed command gateway for the benchmark harness.

The harness must expose this gateway instead of an unrestricted shell. Network
isolation remains an OS/container responsibility; this module narrows the tool
surface and records every accepted or rejected command.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


READ_ONLY_PROGRAMS = {"rg", "head", "tail", "wc"}
ALLOWED_PROGRAMS = READ_ONLY_PROGRAMS | {"git", "mvn", "bash"}
ALLOWED_GIT_SUBCOMMANDS = {"status", "diff"}
ALLOWED_SCRIPTS = {
    "/home/public_tests/run_public_tests.sh",
    "/home/submit/submit.sh",
}
ALLOWED_ABSOLUTE_ROOTS = tuple(
    path.resolve(strict=False)
    for path in (
        Path("/home/workspace/exchange-core"),
        Path("/home/task"),
        Path("/home/public_tests"),
        Path("/home/submit"),
    )
)
FORBIDDEN_FRAGMENTS = (
    "/opt/verifier",
    "/opt/author_only",
    "/opt/baseline",
    "/home/trajectory",
    "hidden_tests",
    ".git/config",
    ".git/objects",
    ".git/logs",
)
NETWORK_EXECUTABLES = {
    "curl",
    "wget",
    "ssh",
    "scp",
    "nc",
    "ncat",
    "git-remote-http",
    "git-remote-https",
    "pip",
    "pip3",
    "npm",
    "brew",
}
BLOCKING_REASONS = {
    "network_target",
    "forbidden_path",
    "denied_executable",
    "denied_git_operation",
    "unapproved_script",
    "raw_shell_bypass",
}
DANGEROUS_RG_FLAGS = {"--pre", "--pre-glob"}


def _path_is_allowed(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    return any(resolved == root or root in resolved.parents for root in ALLOWED_ABSOLUTE_ROOTS)


def validate_command(argv: list[str]) -> tuple[bool, str]:
    if not argv:
        return False, "empty_command"

    program = Path(argv[0]).name
    if program in NETWORK_EXECUTABLES:
        return False, "denied_executable"
    if program not in ALLOWED_PROGRAMS:
        return False, "raw_shell_bypass"

    for argument in argv[1:]:
        lowered = argument.lower()
        if "://" in lowered or lowered.startswith(("git@", "ssh:")):
            return False, "network_target"
        if any(fragment in argument for fragment in FORBIDDEN_FRAGMENTS):
            return False, "forbidden_path"
        candidate = argument.split("=", 1)[1] if argument.startswith("-") and "=" in argument else argument
        if ".." in Path(candidate).parts:
            return False, "forbidden_path"
        if candidate.startswith("/") and not _path_is_allowed(Path(candidate)):
            return False, "forbidden_path"

    if program == "rg" and any(argument.split("=", 1)[0] in DANGEROUS_RG_FLAGS for argument in argv[1:]):
        return False, "raw_shell_bypass"

    if program == "git":
        if len(argv) < 2 or argv[1] not in ALLOWED_GIT_SUBCOMMANDS:
            return False, "denied_git_operation"

    if program == "mvn":
        if "-o" not in argv and "--offline" not in argv:
            return False, "maven_online_mode"
        forbidden_goals = ("deploy", "release", "dependency:get", "help:evaluate")
        if any(any(goal in argument for goal in forbidden_goals) for argument in argv[1:]):
            return False, "denied_maven_goal"

    if program == "bash":
        if len(argv) != 2 or argv[1] not in ALLOWED_SCRIPTS:
            return False, "unapproved_script"

    return True, "allowed"


def append_event(log_path: Path, event: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    descriptor = os.open(log_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, line.encode("utf-8"))
    finally:
        os.close(descriptor)


def sanitized_environment() -> dict[str, str]:
    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "JAVA_HOME", "MAVEN_OPTS", "TERM")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="/home/workspace/exchange-core")
    parser.add_argument(
        "--trajectory-log",
        default=os.environ.get("AGENT_TRAJECTORY_LOG", "/home/trajectory/commands.jsonl"),
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--run-as-user", default="agent")
    parser.add_argument("--run-as-group", default="agent")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    allowed, reason = validate_command(argv)
    started = time.time()
    base_event = {
        "event": "command_attempt",
        "timestamp_unix": started,
        "argv": argv,
        "cwd": str(Path(args.workspace).resolve(strict=False)),
        "allowed": allowed,
        "reason": reason,
        "blocking": reason in BLOCKING_REASONS,
    }

    try:
        append_event(Path(args.trajectory_log), base_event)
    except OSError as exc:
        print(f"command gateway refused unlogged execution: {exc}", file=sys.stderr)
        return 125

    if not allowed:
        print(f"command rejected by policy: {reason}", file=sys.stderr)
        return 126

    workspace = Path(args.workspace).resolve()
    identity: dict[str, str] = {}
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        identity = {"user": args.run_as_user, "group": args.run_as_group}
    result = subprocess.run(
        argv,
        cwd=workspace,
        env=sanitized_environment(),
        timeout=max(1, args.timeout),
        check=False,
        **identity,
    )
    append_event(
        Path(args.trajectory_log),
        {
            "event": "command_result",
            "timestamp_unix": time.time(),
            "argv": argv,
            "allowed": True,
            "exit_code": result.returncode,
            "duration_seconds": round(time.time() - started, 3),
        },
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
