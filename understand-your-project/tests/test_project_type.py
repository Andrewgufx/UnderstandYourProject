import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.project_type import detect_project_type
from facts.walk import walk_project


class ProjectTypeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def detect(self):
        files, _ = walk_project(self.root)
        return detect_project_type(self.root, files)

    def test_next_project(self):
        self.write("package.json", json.dumps({
            "dependencies": {"next": "14", "react": "18"},
            "devDependencies": {"typescript": "5"},
        }))
        self.write("pnpm-lock.yaml", "")
        self.write("src/app/page.tsx", "x\n" * 10)
        self.write("src/lib/a.js", "x\n")
        result = self.detect()
        self.assertEqual(result["languages"], ["typescript", "javascript"])
        self.assertEqual(result["frameworks"], ["next", "react"])
        self.assertEqual(result["package_managers"], ["pnpm"])
        self.assertFalse(result["monorepo"])
        self.assertEqual(result["detected_from"], ["package.json"])

    def test_python_project_from_requirements_and_pyproject(self):
        self.write("requirements.txt", "Flask==3.0\nrequests>=2\n")
        self.write("pyproject.toml", '[project]\ndependencies = ["fastapi"]\n[tool.poetry]\n')
        self.write("main.py", "x\n")
        result = self.detect()
        self.assertEqual(result["languages"], ["python"])
        self.assertEqual(result["frameworks"], ["fastapi", "flask"])
        self.assertEqual(result["package_managers"], ["pip", "poetry"])
        self.assertEqual(result["detected_from"], ["pyproject.toml", "requirements.txt"])

    def test_monorepo_from_workspaces(self):
        self.write("package.json", json.dumps({"workspaces": ["packages/*"]}))
        self.write("packages/a/index.js", "x\n")
        result = self.detect()
        self.assertTrue(result["monorepo"])
        self.assertEqual(result["package_managers"], ["npm"])

    def test_nested_manifests_are_found_and_merged(self):
        self.write("apps/web/package.json", json.dumps({"name": "web", "dependencies": {"react": "18"}}))
        self.write("apps/web/src/App.tsx", "x\n")
        self.write("services/api/pyproject.toml", '[project]\nname = "api"\ndependencies = ["fastapi"]\n')
        self.write("services/api/app/main.py", "x\n")
        self.write("node_modules/dep/package.json", json.dumps({"dependencies": {"vue": "3"}}))
        result = self.detect()
        self.assertEqual(result["frameworks"], ["fastapi", "react"])
        self.assertEqual(result["package_managers"], ["npm", "pip"])
        self.assertEqual(result["detected_from"], ["apps/web/package.json", "services/api/pyproject.toml"])
        self.assertTrue(result["monorepo"])
        self.assertEqual(result["name"], self.root.name)

    def test_no_manifests(self):
        self.write("script.py", "x\n")
        result = self.detect()
        self.assertEqual(result["frameworks"], [])
        self.assertEqual(result["package_managers"], [])
        self.assertEqual(result["detected_from"], [])

    def test_name_from_package_json_then_pyproject_then_directory(self):
        self.write("main.py", "x\n")
        self.assertEqual(self.detect()["name"], self.root.name)
        self.write("pyproject.toml",
                   '[build-system]\nname = "not-this"\n[tool.poetry]\nname = "poetry-app"\n')
        self.assertEqual(self.detect()["name"], "poetry-app")
        self.write("pyproject.toml", '[project]\nname = "py-app"\nversion = "1"\n')
        self.assertEqual(self.detect()["name"], "py-app")
        self.write("package.json", json.dumps({"name": "js-app"}))
        self.assertEqual(self.detect()["name"], "js-app")
        self.write("package.json", json.dumps({"name": 42}))
        self.assertEqual(self.detect()["name"], "py-app")

    def test_non_object_package_json_is_treated_as_absent(self):
        self.write("package.json", "[]")
        self.write("src/a.js", "x\n")
        result = self.detect()
        self.assertEqual(result["frameworks"], [])
        self.assertFalse(result["monorepo"])
        self.assertEqual(result["detected_from"], [])
        self.assertEqual(result["name"], self.root.name)

    def test_bom_prefixed_package_json_is_read(self):
        path = self.root / "package.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"dependencies": {"next": "14"}}).encode("utf-8"))
        self.assertEqual(self.detect()["frameworks"], ["next"])


if __name__ == "__main__":
    unittest.main()
