import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.walk import is_test_path, load_gitignore_dirs, walk_project


class TempProject(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class WalkProjectTests(TempProject):
    def test_collects_source_files_with_language_and_lines(self):
        self.write("src/app.ts", "a\nb\nc\n")
        self.write("main.py", "x\n")
        self.write("README.md", "hi")
        files, total = walk_project(self.root)
        self.assertEqual(total, 3)
        self.assertEqual(
            [(f.path, f.language, f.lines) for f in files],
            [("main.py", "python", 1), ("src/app.ts", "typescript", 3)],
        )

    def test_skips_builtin_and_gitignored_dirs(self):
        self.write("node_modules/x/index.js", "a")
        self.write("generated/a.js", "a")
        self.write(".gitignore", "generated/\n*.log\n")
        self.write("src/a.js", "a")
        files, total = walk_project(self.root)
        self.assertEqual([f.path for f in files], ["src/a.js"])
        self.assertEqual(total, 2)

    def test_read_text_is_cached_and_tolerant(self):
        path = self.write("a.py", "print('hi')\n")
        files, _ = walk_project(self.root)
        self.assertEqual(files[0].read_text(), "print('hi')\n")
        path.unlink()
        self.assertEqual(files[0].read_text(), "print('hi')\n")


class GitignoreTests(TempProject):
    def test_only_plain_directory_names_are_returned(self):
        self.write(".gitignore", "# comment\ngenerated/\n*.log\nsub/dir\n!keep\ncache\n")
        self.assertEqual(load_gitignore_dirs(self.root), {"generated", "cache"})

    def test_missing_gitignore_returns_empty(self):
        self.assertEqual(load_gitignore_dirs(self.root), set())


class IsTestPathTests(unittest.TestCase):
    def test_detects_test_files_and_dirs(self):
        for path in [
            "tests/test_a.py", "src/__tests__/a.js", "src/a.test.ts",
            "src/a.spec.tsx", "test_a.py", "pkg/a_test.py", "spec/a.js",
        ]:
            self.assertTrue(is_test_path(path), path)

    def test_regular_files_are_not_tests(self):
        for path in ["src/a.py", "src/testing_utils.py", "src/contest.ts", "latest.py"]:
            self.assertFalse(is_test_path(path), path)


if __name__ == "__main__":
    unittest.main()
