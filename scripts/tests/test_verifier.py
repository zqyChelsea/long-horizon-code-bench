from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verifier"))
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda handle: {}))
MODULE_PATH = ROOT / "verifier/run_verifier.py"
SPEC = importlib.util.spec_from_file_location("run_verifier", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def create_archive(path: Path, files: dict[str, bytes]) -> None:
    entries = []
    import hashlib

    digest = hashlib.sha256()
    for name, payload in sorted(files.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        entries.append({"path": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = {
        "schema_version": 1,
        "base_commit": MODULE.BASE_COMMIT,
        "replacement_roots": ["src/main"],
        "tree_sha256": digest.hexdigest(),
        "files": entries,
    }
    with tarfile.open(path, "w:gz") as archive:
        manifest_payload = (json.dumps(manifest) + "\n").encode()
        info = tarfile.TarInfo(MODULE.MANIFEST_NAME)
        info.size = len(manifest_payload)
        archive.addfile(info, io.BytesIO(manifest_payload))
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


class VerifierTests(unittest.TestCase):
    def test_missing_junit_report_is_failure_even_when_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            counts = MODULE.junit_counts(Path(directory), ["example.ExpectedTest"], 0)
            self.assertEqual(counts["passed"], 0)
            self.assertEqual(counts["total"], 1)
            self.assertFalse(counts["protocol_ok"])

    def test_replacement_tree_preserves_deletions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            old = workspace / "src/main/java/Old.java"
            old.parent.mkdir(parents=True)
            old.write_text("class Old {}\n", encoding="utf-8")
            archive = root / "candidate.tar.gz"
            create_archive(archive, {"src/main/java/New.java": b"class New {}\n"})
            MODULE.replace_submission_tree(archive, workspace)
            self.assertFalse(old.exists())
            self.assertTrue((workspace / "src/main/java/New.java").is_file())

    def test_archive_path_traversal_is_rejected(self):
        self.assertFalse(MODULE.archive_member_allowed("../src/main/java/Escape.java"))

    def test_metric_normalization_supports_both_directions(self):
        self.assertEqual(MODULE.normalize_metric(15.0, 10.0, 20.0, "maximize"), 0.5)
        self.assertEqual(MODULE.normalize_metric(15.0, 20.0, 10.0, "minimize"), 0.5)

    def test_invalid_metric_keeps_its_weight_in_denominator(self):
        self.assertEqual(MODULE.aggregate_metric([(0.5, 1.0), (0.5, None)]), 0.5)

    def test_hard_gate_zeroes_official_score_but_keeps_progress(self):
        scoring = {"score": {"test_weight": 0.3, "metric_weight": 0.7}}
        progress, official = MODULE.official_scores(1.0, 0.8, scoring, ["mandatory_test_failure"])
        self.assertAlmostEqual(progress, 0.86)
        self.assertEqual(official, 0.0)


if __name__ == "__main__":
    unittest.main()
