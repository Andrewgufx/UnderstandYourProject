import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.collect import collect

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CleanNextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = collect(FIXTURES / "clean-next")

    def test_project_type(self):
        self.assertEqual(self.facts["project_type"]["frameworks"], ["next", "react"])
        self.assertEqual(self.facts["project_type"]["languages"], ["typescript"])
        self.assertEqual(self.facts["project_type"]["package_managers"], ["npm"])

    def test_no_structural_problems(self):
        dep = self.facts["dependency"]
        self.assertEqual(dep["cycles"], [])
        self.assertEqual(dep["orphans"], [])
        self.assertEqual(dep["unresolved_imports"], 0)
        self.assertEqual(self.facts["layer_mixing"], [])
        self.assertEqual(self.facts["duplication"]["similar_filenames"], [])

    def test_alias_imports_resolved(self):
        edges = {(e["from"], e["to"]) for e in self.facts["dependency"]["edges"]}
        self.assertIn(("src/app/page.tsx", "src/components/TodoList.tsx"), edges)
        self.assertIn(("src/components/TodoList.tsx", "src/lib/todos.ts"), edges)

    def test_hygiene(self):
        h = self.facts["hygiene"]
        self.assertTrue(h["has_tests"])
        self.assertTrue(h["has_env_example"])
        self.assertTrue(h["has_lint_config"])
        self.assertTrue(h["has_format_config"])
        self.assertEqual(h["suspected_secrets"], [])
        self.assertEqual(self.facts["docs"], ["README.md"])


class MonolithPyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = collect(FIXTURES / "monolith-py")

    def test_project_type(self):
        self.assertEqual(self.facts["project_type"]["frameworks"], ["flask"])
        self.assertEqual(self.facts["project_type"]["package_managers"], ["pip"])

    def test_giant_file(self):
        top = self.facts["largest_files"][0]
        self.assertEqual(top["path"], "main.py")
        self.assertGreater(top["lines"], 500)

    def test_layer_mixing_and_secret(self):
        mixing = self.facts["layer_mixing"]
        self.assertEqual(len(mixing), 1)
        self.assertEqual(mixing[0]["path"], "main.py")
        self.assertEqual(mixing[0]["categories"], ["network", "data"])
        self.assertEqual(self.facts["hygiene"]["suspected_secrets"], ["main.py:6"])

    def test_missing_hygiene(self):
        h = self.facts["hygiene"]
        self.assertFalse(h["has_tests"])
        self.assertFalse(h["has_env_example"])
        self.assertFalse(h["has_gitignore"])
        self.assertFalse(h["has_lint_config"])


class CyclicNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = collect(FIXTURES / "cyclic-node")

    def test_cycle_and_orphan(self):
        dep = self.facts["dependency"]
        self.assertEqual(dep["cycles"], [["src/handlers.js", "src/routes.js", "src/handlers.js"]])
        self.assertEqual(dep["orphans"], ["src/legacy.js"])
        self.assertEqual(self.facts["project_type"]["frameworks"], ["express"])


if __name__ == "__main__":
    unittest.main()
