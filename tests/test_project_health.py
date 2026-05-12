import json
import tempfile
import unittest
from pathlib import Path

from backend.project_health import detect_verification_commands, is_safe_verification_command


class ProjectHealthTests(unittest.TestCase):
    def test_detects_node_build_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "vite build", "test": "vitest"}}),
                encoding="utf-8",
            )
            commands = detect_verification_commands(root)
            self.assertIn("npm run build", [item["command"] for item in commands])
            self.assertIn("npm test", [item["command"] for item in commands])

    def test_rejects_shell_chaining(self):
        self.assertTrue(is_safe_verification_command("npm run build"))
        self.assertFalse(is_safe_verification_command("npm run build && rm -rf dist"))


if __name__ == "__main__":
    unittest.main()
