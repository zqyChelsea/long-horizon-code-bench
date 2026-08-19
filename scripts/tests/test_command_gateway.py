from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "policy/command_gateway.py"
SPEC = importlib.util.spec_from_file_location("command_gateway", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CommandGatewayTests(unittest.TestCase):
    def test_local_search_is_allowed(self):
        self.assertEqual(MODULE.validate_command(["rg", "RiskEngine", "src/main"]), (True, "allowed"))

    def test_maven_must_be_offline(self):
        self.assertEqual(MODULE.validate_command(["mvn", "-B", "test"]), (False, "maven_online_mode"))
        self.assertEqual(MODULE.validate_command(["mvn", "-B", "-o", "test"]), (True, "allowed"))

    def test_network_target_is_blocked(self):
        self.assertEqual(
            MODULE.validate_command(["rg", "needle", "https://github.com/example/repo"]),
            (False, "network_target"),
        )

    def test_remote_git_operation_is_blocked(self):
        self.assertEqual(MODULE.validate_command(["git", "clone", "repo"]), (False, "denied_git_operation"))

    def test_search_preprocessor_is_blocked(self):
        self.assertEqual(
            MODULE.validate_command(["rg", "--pre=sh", "needle", "src/main"]),
            (False, "raw_shell_bypass"),
        )

    def test_option_embedded_path_escape_is_blocked(self):
        self.assertEqual(
            MODULE.validate_command(["mvn", "-o", "-Dsettings=../../author_only/settings.xml", "test"]),
            (False, "forbidden_path"),
        )

    def test_only_published_scripts_are_allowed(self):
        self.assertEqual(
            MODULE.validate_command(["bash", "/home/public_tests/run_public_tests.sh"]),
            (True, "allowed"),
        )
        self.assertEqual(MODULE.validate_command(["bash", "local.sh"]), (False, "unapproved_script"))


if __name__ == "__main__":
    unittest.main()
