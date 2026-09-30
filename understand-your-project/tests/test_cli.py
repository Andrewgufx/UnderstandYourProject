import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_facts.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
        )

    def test_outputs_json_with_all_top_level_keys(self):
        (self.root / "main.py").write_text("print(1)\n", encoding="utf-8")
        proc = self.run_cli(str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(sorted(data), [
            "dependency", "docs", "duplication", "hygiene", "largest_files", "layer_mixing",
            "naming", "project_type", "root", "scale", "tree",
        ])
        self.assertEqual(data["scale"]["source_files"], 1)
        self.assertEqual(sorted(data["duplication"]), ["repeated_function_names", "similar_filenames"])

    def test_compact_flag(self):
        (self.root / "main.py").write_text("", encoding="utf-8")
        proc = self.run_cli("--compact", str(self.root))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.count("\n"), 1)

    def test_secret_value_never_appears_in_output(self):
        proc = self.run_cli(str(FIXTURES / "monolith-py"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("main.py:6", proc.stdout)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", proc.stdout)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", proc.stderr)

    def test_missing_directory_errors(self):
        proc = self.run_cli(str(self.root / "nope"))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.startswith("error:"))
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
