import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from backend.action_manager import PROJECTS_ROOT, _safe_project_path
from backend.security import is_loopback_host, is_valid_token, token_fingerprint


class SecurityTests(unittest.TestCase):
    def test_loopback_detection(self):
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertTrue(is_loopback_host("::1"))
        self.assertFalse(is_loopback_host("192.168.0.10"))

    def test_token_validation(self):
        fingerprint = token_fingerprint()
        self.assertEqual(len(fingerprint), 12)
        self.assertFalse(is_valid_token("definitely-wrong"))

    def test_write_file_stays_inside_selected_workspace(self):
        workspace = PROJECTS_ROOT / "новый проект"
        if not workspace.exists():
            self.skipTest("local workspace fixture is not available")

        resolved = _safe_project_path("README.md", str(workspace))
        self.assertEqual(resolved, workspace / "README.md")

        with self.assertRaises(ValueError):
            _safe_project_path(str(PROJECTS_ROOT / "obsidian-vault" / "README.md"), str(workspace))


if __name__ == "__main__":
    unittest.main()
