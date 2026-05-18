import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from backend.context_pack import build_workspace_context_pack, find_nested_workspace_candidates, is_container_workspace


class ContextPackTests(unittest.TestCase):
    def test_detects_container_workspace_and_dedupes_nested_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "Frontend" / "lab_3"
            child.mkdir(parents=True)
            (child / "package.json").write_text(
                json.dumps({"scripts": {"build": "vite build", "lint": "eslint ."}}),
                encoding="utf-8",
            )
            (child / "requirements.txt").write_text("pytest\n", encoding="utf-8")

            candidates = find_nested_workspace_candidates(root / "Frontend")
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["relative"], "lab_3")
            self.assertIn("Node.js", candidates[0]["signals"])
            self.assertIn("Python", candidates[0]["signals"])

            pack = build_workspace_context_pack(root, root / "Frontend")
            self.assertTrue(is_container_workspace(pack))

    def test_concrete_workspace_is_not_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "app"
            app.mkdir()
            (app / "package.json").write_text(json.dumps({"scripts": {"build": "vite build"}}), encoding="utf-8")

            pack = build_workspace_context_pack(root, app)
            self.assertFalse(is_container_workspace(pack))
            self.assertEqual(pack["nested_workspace_candidates"], [])


if __name__ == "__main__":
    unittest.main()
