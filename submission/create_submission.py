#!/usr/bin/env python3
"""Create a deterministic, complete source-tree submission archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import time


ALLOWED = ("src/main",)
MANIFEST_NAME = "submission_manifest.json"
BASE_COMMIT = "2f8548749839e9095c8dc597e4b61521d259fa5d"
FORBIDDEN_SUFFIXES = {".class", ".jar", ".zip", ".tar", ".gz", ".so", ".dylib", ".dll", ".exe"}
MAX_FILES = 5000
MAX_TOTAL_BYTES = 100 * 1024 * 1024


def iter_files(workspace: Path):
    seen: set[Path] = set()
    for relative in ALLOWED:
        target = workspace / relative
        if not target.exists():
            continue
        if target.is_symlink():
            raise ValueError(f"禁止提交符号链接：{relative}")
        if target.is_file():
            candidates = [target]
        else:
            candidates = sorted(path for path in target.rglob("*") if path.is_file())
        for path in candidates:
            resolved = path.resolve()
            if workspace.resolve() not in resolved.parents:
                raise ValueError(f"文件越出工作区：{path}")
            if path.is_symlink():
                raise ValueError(f"禁止提交符号链接：{path}")
            if resolved not in seen:
                seen.add(resolved)
                yield path


def digest_files(workspace: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def file_manifest(workspace: Path, files: list[Path]) -> dict:
    entries = []
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "schema_version": 1,
        "base_commit": BASE_COMMIT,
        "replacement_roots": list(ALLOWED),
        "tree_sha256": digest_files(workspace, files),
        "files": entries,
    }


def validate_files(files: list[Path]) -> None:
    if len(files) > MAX_FILES:
        raise ValueError(f"提交文件过多：{len(files)}")
    total_bytes = 0
    for path in files:
        stat = path.stat()
        total_bytes += stat.st_size
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise ValueError(f"禁止提交二进制或归档文件：{path}")
        if stat.st_mode & 0o111:
            raise ValueError(f"禁止提交可执行文件：{path}")
    if total_bytes > MAX_TOTAL_BYTES:
        raise ValueError(f"提交总大小超限：{total_bytes}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = list(iter_files(workspace))
    if not files:
        raise SystemExit("没有可提交文件")
    validate_files(files)

    manifest = file_manifest(workspace, files)
    sha256 = manifest["tree_sha256"]
    timestamp = int(time.time())
    archive_name = f"submission-{timestamp}-{sha256[:12]}.tar.gz"
    final_archive = output_dir / archive_name

    with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".tar.gz", delete=False) as tmp:
        temporary = Path(tmp.name)

    try:
        with temporary.open("wb") as raw_archive:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_archive, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
                    manifest_info = tarfile.TarInfo(MANIFEST_NAME)
                    manifest_info.size = len(manifest_bytes)
                    manifest_info.uid = manifest_info.gid = 0
                    manifest_info.uname = manifest_info.gname = "root"
                    manifest_info.mtime = 0
                    archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
                    for path in files:
                        relative = path.relative_to(workspace).as_posix()
                        info = archive.gettarinfo(str(path), arcname=relative)
                        info.uid = info.gid = 0
                        info.uname = info.gname = "root"
                        info.mtime = 0
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
        os.replace(temporary, final_archive)
    finally:
        temporary.unlink(missing_ok=True)

    metadata = {
        "archive": archive_name,
        "tree_sha256": sha256,
        "created_at_unix": timestamp,
        "file_count": len(files),
        "base_commit": BASE_COMMIT,
    }
    metadata_path = final_archive.with_suffix(final_archive.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
