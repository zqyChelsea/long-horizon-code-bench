from __future__ import annotations

import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "submission/create_submission.py"
SPEC = importlib.util.spec_from_file_location("create_submission", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SubmissionTests(unittest.TestCase):
    def test_only_allowlisted_files_are_iterated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "src/main/java/Example.java"
            denied = root / "src/test/java/Hidden.java"
            allowed.parent.mkdir(parents=True)
            denied.parent.mkdir(parents=True)
            allowed.write_text("class Example {}\n", encoding="utf-8")
            denied.write_text("class Hidden {}\n", encoding="utf-8")
            files = [path.relative_to(root).as_posix() for path in MODULE.iter_files(root)]
            self.assertEqual(files, ["src/main/java/Example.java"])

    def test_digest_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "pom.xml"
            source.write_text("<project/>\n", encoding="utf-8")
            files = list(MODULE.iter_files(root))
            self.assertEqual(MODULE.digest_files(root, files), MODULE.digest_files(root, files))


if __name__ == "__main__":
    unittest.main()

