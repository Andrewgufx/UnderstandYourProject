import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.hygiene import find_docs, hygiene, suspected_secrets
from facts.walk import walk_project


class HygieneBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class SecretTests(HygieneBase):
    def test_reports_position_only(self):
        self.write("src/config.ts", 'const a = 1;\nconst API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234";\n')
        self.write("src/auth.py", 'password = "hunter2hunter2hunter2"\n')
        self.write("src/ok.py", 'token = os.environ["TOKEN"]\nshort = "abc"\n')
        self.write("tests/test_x.py", 'API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234"\n')
        files, _ = walk_project(self.root)
        result = suspected_secrets(files)
        self.assertEqual(result, ["src/auth.py:1", "src/config.ts:2"])
        for entry in result:
            self.assertRegex(entry, r"^[^:]+:\d+$")

    def test_known_prefixes(self):
        self.write("a.js", 'const t = "ghp_abcdefghijklmnopqrstuvwxyz";\nconst k = "AKIAABCDEFGHIJKLMNOP";\n')
        files, _ = walk_project(self.root)
        self.assertEqual(suspected_secrets(files), ["a.js:1", "a.js:2"])

    def test_common_real_world_forms_are_flagged(self):
        self.write("a.py", "SECRET_KEY = 'django-insecure-abc123def456ghi789=='\n")
        self.write("b.json.py", 'cfg = {"password": "P@ssw0rd/with+base64=="}\n')
        self.write("c.ts", 'const openaiKey = "sk-proj-abcdefghijklmnopqrstuvwxyz0123";\n')
        self.write("d.py", 'AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n')
        files, _ = walk_project(self.root)
        self.assertEqual(suspected_secrets(files), ["a.py:1", "b.json.py:1", "c.ts:1", "d.py:1"])

    def test_env_lookups_and_templates_are_not_flagged(self):
        self.write("a.ts", 'const token = "${process.env.API_TOKEN_VALUE}";\nconst t2 = process.env.TOKEN;\n')
        self.write("b.py", 'token = os.environ.get("TOKEN")\npassword = f"{settings.PASSWORD_FROM_ENV}"\n')
        files, _ = walk_project(self.root)
        self.assertEqual(suspected_secrets(files), [])


class DocsTests(HygieneBase):
    def test_finds_readme_agent_docs_and_named_specs(self):
        self.write("README.md", "")
        self.write("CLAUDE.md", "")
        self.write("docs/guide.md", "")
        self.write("docs/deep/nested/more.md", "")
        self.write("notes/product-prd.md", "")
        self.write("CHANGELOG.md", "")
        self.write("ARCHITECTURE_REVIEW.md", "")
        self.write("node_modules/x/README.md", "")
        self.assertEqual(find_docs(self.root), [
            "CLAUDE.md", "README.md", "docs/deep/nested/more.md", "docs/guide.md", "notes/product-prd.md",
        ])


class HygieneTests(HygieneBase):
    def test_clean_project(self):
        self.write(".gitignore", "node_modules\n")
        self.write(".env.example", "X=\n")
        self.write(".eslintrc.json", "{}")
        self.write(".prettierrc", "{}")
        self.write("src/lib/todos.test.ts", "")
        self.write("src/lib/todos.ts", "")
        self.write("next.config.js", "")
        self.write("src/config/app-config.ts", "")
        files, _ = walk_project(self.root)
        result = hygiene(self.root, files)
        self.assertEqual(result, {
            "has_tests": True,
            "test_paths": ["src/lib/todos.test.ts"],
            "has_env_example": True,
            "has_gitignore": True,
            "has_lint_config": True,
            "has_format_config": True,
            "suspected_secrets": [],
            "config_files": ["src/config/app-config.ts"],
        })

    def test_python_project_with_pyproject_tools(self):
        self.write("pyproject.toml", "[tool.ruff]\nline-length = 100\n[tool.black]\n")
        self.write("app/settings.py", "")
        self.write("app/constants.py", "")
        files, _ = walk_project(self.root)
        result = hygiene(self.root, files)
        self.assertFalse(result["has_tests"])
        self.assertTrue(result["has_lint_config"])
        self.assertTrue(result["has_format_config"])
        self.assertEqual(result["config_files"], ["app/constants.py", "app/settings.py"])

    def test_bare_project(self):
        self.write("main.py", "")
        files, _ = walk_project(self.root)
        result = hygiene(self.root, files)
        self.assertEqual(
            [result[k] for k in ("has_tests", "has_env_example", "has_gitignore", "has_lint_config", "has_format_config")],
            [False, False, False, False, False],
        )


if __name__ == "__main__":
    unittest.main()
