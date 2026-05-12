import tempfile
import unittest
from pathlib import Path

from backend.project_intelligence import load_all_project_tasks, load_projects


class ProjectIntelligenceTests(unittest.TestCase):
    def test_project_registry_from_vault_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            wiki = vault / "wiki"
            wiki.mkdir()
            (wiki / "INDEX.md").write_text(
                """
## 📁 Проекты – Активные

| Заметка | Описание | Стек | Статус |
|---------|----------|------|--------|
| [[demo-project]] | Demo | Python, SQLite | 🔄 Активно |
""",
                encoding="utf-8",
            )
            (wiki / "demo-project.md").write_text(
                """
# Demo Project

> Demo summary.

## Путь

```
/Users/justalim/projects/does-not-exist-demo/
```

## Открытые задачи

- [ ] First task
- [ ] Second task
""",
                encoding="utf-8",
            )

            projects = load_projects(vault)
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0]["id"], "demo-project")
            self.assertEqual(projects[0]["task_count"], 2)

            tasks = load_all_project_tasks(vault)
            self.assertEqual([task["task"] for task in tasks], ["First task", "Second task"])


if __name__ == "__main__":
    unittest.main()
