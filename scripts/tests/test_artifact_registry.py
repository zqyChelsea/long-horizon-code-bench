from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "verifier/artifact_registry.py"
SPEC = importlib.util.spec_from_file_location("artifact_registry", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ArtifactRegistryTests(unittest.TestCase):
    def test_best_score_is_bound_to_valid_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            submission = root / "submission.tar.gz"
            submission.write_bytes(b"valid-artifact")
            common = {
                "submission": submission,
                "report_without_registry": {"score_current": 0.7},
                "phase": "feedback",
                "artifact_store": root / "artifacts",
                "history_file": root / "history.jsonl",
                "best_record": root / "best.json",
            }
            first = MODULE.register_artifact(valid=True, score=0.7, **common)
            self.assertEqual(first["artifact_id"], first["best_artifact_id"])
            best = MODULE.load_best(root / "best.json")
            self.assertTrue(Path(best["artifact_path"]).is_file())
            self.assertTrue(Path(best["report_path"]).is_file())

            invalid = root / "invalid.tar.gz"
            invalid.write_bytes(b"invalid-but-high-score")
            second = MODULE.register_artifact(
                submission=invalid,
                report_without_registry={"score_current": 1.0},
                valid=False,
                score=1.0,
                phase="feedback",
                artifact_store=root / "artifacts",
                history_file=root / "history.jsonl",
                best_record=root / "best.json",
            )
            self.assertEqual(second["best_artifact_id"], first["artifact_id"])
            self.assertFalse(second["artifact_valid"])


if __name__ == "__main__":
    unittest.main()
