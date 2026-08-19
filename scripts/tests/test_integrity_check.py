from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()

