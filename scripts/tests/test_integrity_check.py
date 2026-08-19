from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "verifier/integrity_check.py"
SPEC = importlib.util.spec_from_file_location("integrity_check", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class IntegrityCheckTests(unittest.TestCase):
    def test_clean_source_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "src/main/java/Example.java"
            source.parent.mkdir(parents=True)
            source.write_text("class Example {}\n", encoding="utf-8")
            self.assertEqual(MODULE.inspect_submission(Path(directory)), [])

    def test_forbidden_judge_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "src/main/java/Example.java"
            source.parent.mkdir(parents=True)
            source.write_text('class Example { String p = "/opt/verifier"; }\n', encoding="utf-8")
            violations = MODULE.inspect_submission(Path(directory))
            self.assertTrue(any(item.startswith("forbidden_reference") for item in violations))

    def test_binary_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = Path(directory) / "src/main/resources/payload.jar"
            payload.parent.mkdir(parents=True)
            payload.write_bytes(b"PK\x03\x04payload")
            violations = MODULE.inspect_submission(Path(directory))
            self.assertTrue(any(item.startswith("forbidden_binary_type") for item in violations))

    def test_blocking_trajectory_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            trajectory = Path(directory) / "commands.jsonl"
            trajectory.write_text(
                json.dumps({"allowed": False, "blocking": True, "reason": "network_target"}) + "\n",
                encoding="utf-8",
            )
            violations = MODULE.inspect_trajectory(trajectory)
            self.assertEqual(violations, ["trajectory_policy_violation:1:network_target"])


if __name__ == "__main__":
    unittest.main()
