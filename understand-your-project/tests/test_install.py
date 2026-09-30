import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "install.py"
SKILL = "understand-your-project"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self.project = Path(self._tmp.name) / "project"
        self.home.mkdir()
        self.project.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def run_install(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(self.home), *args],
            capture_output=True, text=True, cwd=str(self.project),
        )

    def test_claude_installs_into_claude_skills(self):
        proc = self.run_install("--agent", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        dest = self.home / ".claude" / "skills" / SKILL
        self.assertTrue((dest / "SKILL.md").is_file())
        self.assertTrue((dest / "scripts" / "collect_facts.py").is_file())
        self.assertTrue((dest / "scripts" / "facts" / "collect.py").is_file())
        self.assertTrue((dest / "references" / "checklist.md").is_file())
        self.assertFalse((self.home / ".agents").exists())
        self.assertIn(str(dest), proc.stdout)

    def test_codex_cursor_and_gemini_share_the_agents_directory(self):
        for agent in ("codex", "cursor", "gemini"):
            proc = self.run_install("--agent", agent)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((self.home / ".agents" / "skills" / SKILL / "SKILL.md").is_file())
        self.assertFalse((self.home / ".claude").exists())

    def test_all_installs_into_both_directories(self):
        proc = self.run_install("--agent", "all")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.home / ".claude" / "skills" / SKILL / "SKILL.md").is_file())
        self.assertTrue((self.home / ".agents" / "skills" / SKILL / "SKILL.md").is_file())

    def test_leaves_out_tests_evals_and_caches(self):
        self.run_install("--agent", "claude")
        dest = self.home / ".claude" / "skills" / SKILL
        self.assertFalse((dest / "tests").exists())
        self.assertFalse((dest / "EVALS.md").exists())
        self.assertEqual(list(dest.rglob("__pycache__")), [])

    def test_replaces_a_previous_install(self):
        dest = self.home / ".claude" / "skills" / SKILL
        dest.mkdir(parents=True)
        (dest / "stale.md").write_text("old", encoding="utf-8")
        proc = self.run_install("--agent", "claude")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((dest / "stale.md").exists())
        self.assertTrue((dest / "SKILL.md").is_file())

    def test_project_flag_installs_into_the_current_directory(self):
        proc = self.run_install("--agent", "codex", "--project")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.project / ".agents" / "skills" / SKILL / "SKILL.md").is_file())
        self.assertFalse((self.home / ".agents").exists())

    def test_installed_collector_runs(self):
        self.run_install("--agent", "codex")
        script = self.home / ".agents" / "skills" / SKILL / "scripts" / "collect_facts.py"
        (self.project / "main.py").write_text("print(1)\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(script), str(self.project)], capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_agent_is_required(self):
        proc = self.run_install()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--agent", proc.stderr)


class SkillFormatTests(unittest.TestCase):
    """The frontmatter rules every supported agent shares (agentskills.io)."""

    def frontmatter(self):
        text = (REPO / SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        block = text[4:text.index("\n---\n", 4)]
        return dict(line.split(": ", 1) for line in block.splitlines())

    def test_name_matches_directory(self):
        self.assertEqual(self.frontmatter()["name"], SKILL)

    def test_description_fits_the_limit(self):
        description = self.frontmatter()["description"]
        self.assertTrue(0 < len(description) <= 1024)


if __name__ == "__main__":
    unittest.main()
