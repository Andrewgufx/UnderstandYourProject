# UnderstandYourProject Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `understand-your-project` Claude Code skill: a zero-dependency Python fact-collector plus reference documents that let an agent analyze a JS/TS or Python project's architecture, judge it against the user's needs, and write a plain-language report with concrete fixes.

**Architecture:** `scripts/collect_facts.py` is a thin CLI over a `scripts/facts/` package whose modules each collect one category of facts (walking, project type, structure, imports, signals, hygiene) and return plain dicts; `facts/collect.py` assembles them into one JSON document. The agent-facing logic lives entirely in `SKILL.md` and `references/*.md`: interview template, 16-item checklist with tier adjustment rules, reference architectures, and report template. The script never judges; the docs never count.

**Tech Stack:** Python 3.8+ standard library only (`os`, `re`, `json`, `posixpath`, `dataclasses`, `unittest`). Markdown for skill and references. No third-party packages anywhere.

**Spec:** `docs/superpowers/specs/2026-09-30-understand-your-project-design.md`

## Global Constraints

- Python floor: 3.8. Every module starts with `from __future__ import annotations`. No `match`, no `str.removeprefix`, no `list[str]` at runtime.
- Zero third-party dependencies in `scripts/` and `tests/`. Only the standard library.
- Supported source extensions: `.js .jsx .ts .tsx .mjs .cjs .py`. Only these count toward `source_lines` and dependency analysis.
- Ignored directories (verbatim): `node_modules .git .venv venv env __pycache__ dist build .next out coverage .cache .turbo .pytest_cache .mypy_cache`, plus top-level directory names from the project's `.gitignore`.
- Out-of-scope thresholds: `source_files > 800 or source_lines > 80000`.
- `largest_files` contains every source file over 300 lines, padded to at least 15 entries.
- `suspected_secrets` entries are `path:line` only. Matched text is never written to output.
- JSON output contains paths, counts and positions. Never file contents.
- The script never judges or recommends. All judgment lives in `references/` and `SKILL.md`.
- The report is written to `ARCHITECTURE_REVIEW.md` at the project root, in the user's conversation language. The skill never modifies user code.
- Default interview tiers when the user declines: `scale_tier = small_group`, `evolution_tier = iterating`.
- Test runner from repo root: `python3 -m unittest discover -s understand-your-project/tests -v`.
- Commit after every task. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File Structure

All paths relative to repo root `/Users/andrewgu/Documents/GitHub/UnderstandYourProject`.

```
understand-your-project/
├── SKILL.md                            # Task 15: entry point, trigger, 5-step procedure, agent rules
├── scripts/
│   ├── collect_facts.py                # Task 9: CLI wrapper (argparse, JSON to stdout, errors to stderr)
│   └── facts/
│       ├── __init__.py                 # Task 1: empty
│       ├── walk.py                     # Task 1: SourceFile, walk_project, ignore rules, is_test_path
│       ├── project_type.py             # Task 2: languages, frameworks, package managers, monorepo
│       ├── structure.py                # Task 3: scale, tree, largest_files
│       ├── imports.py                  # Tasks 4-5: import extraction, resolution, graph, cycles, orphans
│       ├── signals.py                  # Tasks 6-7: layer_mixing, similar_filenames, repeated functions, naming
│       ├── hygiene.py                  # Task 8: tests/env/lint/format/secrets/config_files/docs
│       └── collect.py                  # Task 9: assembles the final dict
├── references/
│   ├── interview.md                    # Task 11
│   ├── checklist.md                    # Task 12
│   ├── reference-architectures.md      # Task 13
│   └── report-template.md              # Task 14
├── tests/
│   ├── fixtures/
│   │   ├── clean-next/                 # Task 10
│   │   ├── monolith-py/                # Task 10
│   │   └── cyclic-node/                # Task 10
│   ├── test_walk.py                    # Task 1
│   ├── test_project_type.py            # Task 2
│   ├── test_structure.py               # Task 3
│   ├── test_imports.py                 # Tasks 4-5
│   ├── test_signals.py                 # Tasks 6-7
│   ├── test_hygiene.py                 # Task 8
│   ├── test_cli.py                     # Task 9
│   └── test_integration.py             # Task 10
└── EVALS.md                            # Task 16
README.md                               # Task 16: install and usage
```

Every test file begins with the same two lines so `facts` is importable without packaging:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
```

---

### Task 1: Scaffold and file walker

**Files:**
- Create: `understand-your-project/scripts/facts/__init__.py`
- Create: `understand-your-project/scripts/facts/walk.py`
- Create: `understand-your-project/tests/test_walk.py`

**Interfaces:**
- Produces:
  - `SourceFile` dataclass: `path: str` (posix, relative to root), `abs_path: Path`, `language: str` (`"javascript" | "typescript" | "python"`), `lines: int`, method `read_text() -> str` (cached, utf-8 with replacement).
  - `walk_project(root: Path) -> tuple[list[SourceFile], int]` returning source files sorted by walk order and total file count (all files, not only source).
  - `load_gitignore_dirs(root: Path) -> set[str]`.
  - `is_test_path(rel_path: str) -> bool`.
  - Constants `IGNORED_DIRS`, `SOURCE_EXTENSIONS`.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_walk.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ImportError / ModuleNotFoundError for `facts.walk`.

- [ ] **Step 3: Write the walker**

`understand-your-project/scripts/facts/__init__.py`: empty file.

`understand-your-project/scripts/facts/walk.py`:

```python
"""Walk a project directory and collect source files."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

IGNORED_DIRS = {
    "node_modules", ".git", ".venv", "venv", "env", "__pycache__", "dist",
    "build", ".next", "out", "coverage", ".cache", ".turbo", ".pytest_cache",
    ".mypy_cache",
}

SOURCE_EXTENSIONS = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".py": "python",
}

TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs"}
_TEST_FILE_RE = re.compile(
    r"(^test_[^/]*\.py$)|(_test\.py$)|(\.(test|spec)\.[cm]?[jt]sx?$)"
)


@dataclass
class SourceFile:
    path: str
    abs_path: Path
    language: str
    lines: int
    _text: Optional[str] = field(default=None, repr=False, compare=False)

    def read_text(self) -> str:
        if self._text is None:
            try:
                self._text = self.abs_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self._text = ""
        return self._text


def is_test_path(rel_path: str) -> bool:
    parts = rel_path.split("/")
    if any(part in TEST_DIR_NAMES for part in parts[:-1]):
        return True
    return bool(_TEST_FILE_RE.search(parts[-1]))


def load_gitignore_dirs(root: Path) -> Set[str]:
    """Top-level directory names listed in .gitignore without wildcards or slashes."""
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return set()
    names: Set[str] = set()
    for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.strip("/")
        if "/" in line or any(ch in line for ch in "*?["):
            continue
        names.add(line)
    return names


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def walk_project(root: Path) -> Tuple[List[SourceFile], int]:
    """Return (source_files, total_file_count), pruning ignored directories."""
    ignored = IGNORED_DIRS | load_gitignore_dirs(root)
    source_files: List[SourceFile] = []
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignored)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            total += 1
            language = SOURCE_EXTENSIONS.get(path.suffix)
            if language is None:
                continue
            rel = path.relative_to(root).as_posix()
            source_files.append(SourceFile(rel, path, language, count_lines(path)))
    return source_files, total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: 7 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts understand-your-project/tests/test_walk.py
git commit -m "feat(facts): add project walker with ignore rules

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Project type detection

**Files:**
- Create: `understand-your-project/scripts/facts/project_type.py`
- Create: `understand-your-project/tests/test_project_type.py`

**Interfaces:**
- Consumes: `SourceFile` from `facts.walk`.
- Produces: `detect_project_type(root: Path, source_files: list[SourceFile]) -> dict` with keys `languages: list[str]` (sorted by line count desc), `frameworks: list[str]` (sorted), `package_managers: list[str]` (sorted), `monorepo: bool`, `detected_from: list[str]`.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_project_type.py`:

```python
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

    def test_no_manifests(self):
        self.write("script.py", "x\n")
        result = self.detect()
        self.assertEqual(result["frameworks"], [])
        self.assertEqual(result["package_managers"], [])
        self.assertEqual(result["detected_from"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest understand-your-project/tests/test_project_type.py -v` (or discover)
Expected: ModuleNotFoundError for `facts.project_type`.

- [ ] **Step 3: Write the detector**

`understand-your-project/scripts/facts/project_type.py`:

```python
"""Detect languages, frameworks, package managers and monorepo layout."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

from .walk import SourceFile

JS_PACKAGE_TO_FRAMEWORK = {
    "next": "next", "react": "react", "vue": "vue", "nuxt": "nuxt",
    "svelte": "svelte", "@angular/core": "angular", "express": "express",
    "fastify": "fastify", "@nestjs/core": "nest", "koa": "koa", "hono": "hono",
    "electron": "electron", "@remix-run/react": "remix", "astro": "astro",
}
PY_FRAMEWORKS = ["fastapi", "django", "flask", "streamlit", "typer", "click"]
PY_MANIFESTS = ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _js_frameworks(root: Path, detected_from: List[str]) -> Set[str]:
    manifest = root / "package.json"
    if not manifest.is_file():
        return set()
    detected_from.append("package.json")
    try:
        data = json.loads(_read(manifest))
    except ValueError:
        return set()
    deps: Set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key) or {}
        if isinstance(section, dict):
            deps |= set(section)
    return {fw for pkg, fw in JS_PACKAGE_TO_FRAMEWORK.items() if pkg in deps}


def _py_frameworks(root: Path, detected_from: List[str]) -> Set[str]:
    found: Set[str] = set()
    for name in PY_MANIFESTS:
        path = root / name
        if not path.is_file():
            continue
        detected_from.append(name)
        text = _read(path).lower()
        for fw in PY_FRAMEWORKS:
            if re.search(r"(?<![\w-])" + re.escape(fw) + r"(?![\w-])", text):
                found.add(fw)
    return found


def _package_managers(root: Path) -> List[str]:
    managers: Set[str] = set()
    if (root / "package.json").is_file():
        if (root / "pnpm-lock.yaml").is_file():
            managers.add("pnpm")
        elif (root / "yarn.lock").is_file():
            managers.add("yarn")
        elif (root / "bun.lockb").is_file() or (root / "bun.lock").is_file():
            managers.add("bun")
        else:
            managers.add("npm")
    if (root / "requirements.txt").is_file():
        managers.add("pip")
    pyproject = _read(root / "pyproject.toml") if (root / "pyproject.toml").is_file() else ""
    if (root / "poetry.lock").is_file() or "[tool.poetry]" in pyproject:
        managers.add("poetry")
    if (root / "uv.lock").is_file():
        managers.add("uv")
    if (root / "Pipfile").is_file():
        managers.add("pipenv")
    return sorted(managers)


def _is_monorepo(root: Path) -> bool:
    for name in ("pnpm-workspace.yaml", "lerna.json", "turbo.json"):
        if (root / name).is_file():
            return True
    manifest = root / "package.json"
    if manifest.is_file():
        try:
            return "workspaces" in json.loads(_read(manifest))
        except ValueError:
            return False
    return False


def detect_project_type(root: Path, source_files: List[SourceFile]) -> Dict:
    lines_by_language: Counter = Counter()
    for f in source_files:
        lines_by_language[f.language] += f.lines
    languages = [lang for lang, _ in sorted(
        lines_by_language.items(), key=lambda kv: (-kv[1], kv[0]))]
    detected_from: List[str] = []
    frameworks = _js_frameworks(root, detected_from) | _py_frameworks(root, detected_from)
    return {
        "languages": languages,
        "frameworks": sorted(frameworks),
        "package_managers": _package_managers(root),
        "monorepo": _is_monorepo(root),
        "detected_from": sorted(detected_from),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK (11 tests).

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/project_type.py understand-your-project/tests/test_project_type.py
git commit -m "feat(facts): detect languages, frameworks and package managers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Scale, tree and largest files

**Files:**
- Create: `understand-your-project/scripts/facts/structure.py`
- Create: `understand-your-project/tests/test_structure.py`

**Interfaces:**
- Consumes: `SourceFile`.
- Produces:
  - `scale(source_files, total_files: int) -> dict` with `total_files, source_files, source_lines, lines_by_language, out_of_scope`.
  - `build_tree(source_files, max_depth: int = 4) -> list[dict]` entries `{"path", "depth", "files", "lines"}` sorted by path.
  - `largest_files(source_files) -> list[dict]` entries `{"path", "lines", "language"}`.
  - Constants `OUT_OF_SCOPE_FILES = 800`, `OUT_OF_SCOPE_LINES = 80000`, `LARGE_FILE_LINES = 300`, `MIN_LARGEST = 15`.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_structure.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.structure import build_tree, largest_files, scale
from facts.walk import SourceFile


def sf(path, lines, language="typescript"):
    return SourceFile(path, Path("/nonexistent") / path, language, lines)


class ScaleTests(unittest.TestCase):
    def test_counts_and_in_scope(self):
        files = [sf("a.ts", 10), sf("b.py", 5, "python")]
        result = scale(files, total_files=4)
        self.assertEqual(result, {
            "total_files": 4, "source_files": 2, "source_lines": 15,
            "lines_by_language": {"python": 5, "typescript": 10},
            "out_of_scope": False,
        })

    def test_out_of_scope_by_lines(self):
        files = [sf("a.ts", 80001)]
        self.assertTrue(scale(files, 1)["out_of_scope"])

    def test_out_of_scope_by_file_count(self):
        files = [sf("f%d.ts" % i, 1) for i in range(801)]
        self.assertTrue(scale(files, 801)["out_of_scope"])


class TreeTests(unittest.TestCase):
    def test_aggregates_per_directory_up_to_max_depth(self):
        files = [
            sf("src/app/page.tsx", 10),
            sf("src/app/api/x/route.ts", 5),
            sf("src/lib/a.ts", 3),
            sf("root.ts", 1),
        ]
        tree = build_tree(files, max_depth=3)
        self.assertEqual(tree, [
            {"path": "src", "depth": 1, "files": 3, "lines": 18},
            {"path": "src/app", "depth": 2, "files": 2, "lines": 15},
            {"path": "src/app/api", "depth": 3, "files": 1, "lines": 5},
            {"path": "src/lib", "depth": 2, "files": 1, "lines": 3},
        ])


class LargestFilesTests(unittest.TestCase):
    def test_includes_all_over_threshold_and_pads_to_minimum(self):
        files = [sf("f%02d.ts" % i, i) for i in range(20)]
        files.append(sf("big.ts", 301))
        files.append(sf("huge.py", 900, "python"))
        result = largest_files(files)
        self.assertEqual(len(result), 15)
        self.assertEqual(result[0], {"path": "huge.py", "lines": 900, "language": "python"})
        self.assertEqual(result[1]["path"], "big.ts")

    def test_more_than_minimum_when_many_large(self):
        files = [sf("f%02d.ts" % i, 400 + i) for i in range(20)]
        self.assertEqual(len(largest_files(files)), 20)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ModuleNotFoundError for `facts.structure`.

- [ ] **Step 3: Write the module**

`understand-your-project/scripts/facts/structure.py`:

```python
"""Scale, directory tree and largest files."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from .walk import SourceFile

OUT_OF_SCOPE_FILES = 800
OUT_OF_SCOPE_LINES = 80000
LARGE_FILE_LINES = 300
MIN_LARGEST = 15


def scale(source_files: List[SourceFile], total_files: int) -> Dict:
    by_language: Counter = Counter()
    for f in source_files:
        by_language[f.language] += f.lines
    source_lines = sum(by_language.values())
    return {
        "total_files": total_files,
        "source_files": len(source_files),
        "source_lines": source_lines,
        "lines_by_language": dict(sorted(by_language.items())),
        "out_of_scope": len(source_files) > OUT_OF_SCOPE_FILES or source_lines > OUT_OF_SCOPE_LINES,
    }


def build_tree(source_files: List[SourceFile], max_depth: int = 4) -> List[Dict]:
    files: Dict[str, int] = defaultdict(int)
    lines: Dict[str, int] = defaultdict(int)
    for f in source_files:
        parts = f.path.split("/")[:-1]
        for depth in range(1, min(len(parts), max_depth) + 1):
            directory = "/".join(parts[:depth])
            files[directory] += 1
            lines[directory] += f.lines
    return [
        {"path": d, "depth": d.count("/") + 1, "files": files[d], "lines": lines[d]}
        for d in sorted(files)
    ]


def largest_files(source_files: List[SourceFile]) -> List[Dict]:
    ordered = sorted(source_files, key=lambda f: (-f.lines, f.path))
    selected = [f for f in ordered if f.lines > LARGE_FILE_LINES]
    if len(selected) < MIN_LARGEST:
        selected = ordered[:MIN_LARGEST]
    return [{"path": f.path, "lines": f.lines, "language": f.language} for f in selected]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/structure.py understand-your-project/tests/test_structure.py
git commit -m "feat(facts): add scale, tree and largest_files

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Import extraction and path aliases

**Files:**
- Create: `understand-your-project/scripts/facts/imports.py` (first half)
- Create: `understand-your-project/tests/test_imports.py` (first half)

**Interfaces:**
- Produces:
  - `extract_import_specs(text: str, language: str) -> list[str]`. JS/TS: raw module specifiers in source order, duplicates kept. Python: dotted specs; every `from M import a, b` expands to `M.a`, `M.b` (so `from . import a` gives `.a`, `from pkg.mod import f` gives `pkg.mod.f`); parenthesized multi-line or `*` imports yield just `M`; `import a.b, c as d` yields `a.b`, `c`.
  - `load_path_aliases(root: Path) -> dict[str, str]` mapping alias prefix (e.g. `@/`) to posix directory prefix (e.g. `src/`) from `tsconfig.json` or `jsconfig.json` `compilerOptions.paths` + `baseUrl`. Tolerates comments and trailing commas.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_imports.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.imports import extract_import_specs, load_path_aliases


class ExtractJsTests(unittest.TestCase):
    def test_all_import_forms(self):
        text = """
import React from 'react';
import { a } from "./a";
import * as ns from './ns.js';
import './side-effect';
export { b } from './b';
export * from "./all";
const c = require('./c');
const d = await import('./d');
"""
        self.assertEqual(
            extract_import_specs(text, "typescript"),
            ["react", "./a", "./ns.js", "./side-effect", "./b", "./all", "./c", "./d"],
        )

    def test_type_only_import(self):
        text = "import type { T } from './types';\n"
        self.assertEqual(extract_import_specs(text, "typescript"), ["./types"])


class ExtractPyTests(unittest.TestCase):
    def test_all_import_forms(self):
        text = """
import os
import a.b, c as d
from . import x, y
from .. import z
from .sub.mod import thing
from pkg.mod import thing as other
    from indented import q
"""
        self.assertEqual(
            extract_import_specs(text, "python"),
            ["os", "a.b", "c", ".x", ".y", "..z", ".sub.mod.thing", "pkg.mod.thing", "indented.q"],
        )

    def test_parenthesized_and_star_imports_keep_the_module(self):
        text = "from pkg.mod import (\n    a,\n    b,\n)\nfrom other import *\n"
        self.assertEqual(extract_import_specs(text, "python"), ["pkg.mod", "other"])

    def test_ignores_strings_that_look_like_imports(self):
        text = 'msg = "from x import y"\n'
        self.assertEqual(extract_import_specs(text, "python"), [])


class AliasTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_tsconfig_paths_with_comments_and_trailing_commas(self):
        (self.root / "tsconfig.json").write_text("""{
  // comment
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["src/components/*"],
    },
  },
}""")
        self.assertEqual(load_path_aliases(self.root), {"@/": "src/", "@components/": "src/components/"})

    def test_base_url_is_prepended(self):
        (self.root / "jsconfig.json").write_text(
            '{"compilerOptions": {"baseUrl": "src", "paths": {"~/*": ["lib/*"]}}}')
        self.assertEqual(load_path_aliases(self.root), {"~/": "src/lib/"})

    def test_missing_or_invalid_config(self):
        self.assertEqual(load_path_aliases(self.root), {})
        (self.root / "tsconfig.json").write_text("not json at all {{{")
        self.assertEqual(load_path_aliases(self.root), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ModuleNotFoundError for `facts.imports`.

- [ ] **Step 3: Write extraction and alias loading**

`understand-your-project/scripts/facts/imports.py`:

```python
"""Import extraction, resolution and dependency graph."""
from __future__ import annotations

import json
import posixpath
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from .walk import SourceFile, is_test_path

_JS_PATTERNS = [
    re.compile(r"""\bimport\s+(?:type\s+)?(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]"""),
    re.compile(r"""\bexport\s+(?:type\s+)?(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]"""),
    re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
]
_PY_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+([^\n#]+)", re.MULTILINE)
_PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)", re.MULTILINE)
_PY_ANY = re.compile(r"^\s*(from|import)\s", re.MULTILINE)


def _js_specs(text: str) -> List[str]:
    hits = []
    for pattern in _JS_PATTERNS:
        for match in pattern.finditer(text):
            hits.append((match.start(), match.group(1)))
    return [spec for _, spec in sorted(hits)]


def _py_specs(text: str) -> List[str]:
    """`from M import a, b` yields `M.a`, `M.b` so submodule imports resolve; the
    resolver falls back to `M` when `M.a` is not a file. Parenthesized multi-line
    imports and `import *` keep just `M`."""
    hits = []
    for match in _PY_FROM.finditer(text):
        module, names = match.group(1), match.group(2)
        sep = "" if module.endswith(".") else "."
        parsed = []
        for name in names.replace("(", " ").replace(")", " ").split(","):
            name = name.strip().split(" as ")[0].strip()
            if name and name.isidentifier():
                parsed.append(name)
        if parsed:
            for name in parsed:
                hits.append((match.start(), module + sep + name))
        else:
            hits.append((match.start(), module))
    for match in _PY_IMPORT.finditer(text):
        for item in match.group(1).split(","):
            hits.append((match.start(), item.strip().split(" as ")[0].strip()))
    return [spec for _, spec in sorted(hits)]


def extract_import_specs(text: str, language: str) -> List[str]:
    if language == "python":
        return _py_specs(text)
    return _js_specs(text)


def _lenient_json(text: str) -> Optional[dict]:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(^|[^:\\])//[^\n]*", r"\1", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def load_path_aliases(root: Path) -> Dict[str, str]:
    for name in ("tsconfig.json", "jsconfig.json"):
        path = root / name
        if not path.is_file():
            continue
        data = _lenient_json(path.read_text(encoding="utf-8", errors="replace"))
        if not data:
            return {}
        options = data.get("compilerOptions") or {}
        base_url = options.get("baseUrl") or "."
        paths = options.get("paths") or {}
        aliases: Dict[str, str] = {}
        for alias, targets in paths.items():
            if not alias.endswith("*") or not targets:
                continue
            target = str(targets[0])
            if not target.endswith("*"):
                continue
            joined = posixpath.normpath(posixpath.join(base_url, target[:-1]))
            if joined == ".":
                joined = ""
            aliases[alias[:-1]] = (joined + "/") if joined and not joined.endswith("/") else joined
        return aliases
    return {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/imports.py understand-your-project/tests/test_imports.py
git commit -m "feat(facts): extract import specifiers and tsconfig path aliases

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Import resolution, dependency graph, cycles and orphans

**Files:**
- Modify: `understand-your-project/scripts/facts/imports.py` (append)
- Modify: `understand-your-project/tests/test_imports.py` (append)

**Interfaces:**
- Produces:
  - `resolve_import(spec: str, from_path: str, language: str, known: set[str], aliases: dict, py_roots: list[str]) -> str | None`.
  - `find_cycles(graph: dict[str, set[str]]) -> list[list[str]]` one closed path per SCC of size > 1.
  - `is_entry_file(rel_path: str) -> bool`.
  - `build_dependency(source_files, root: Path) -> dict` with `edges: list[{"from","to"}]`, `most_imported: list[{"path","imported_by"}]` (top 10), `cycles`, `orphans: list[str]`, `unresolved_imports: int`.

- [ ] **Step 1: Append the failing tests**

Append to `understand-your-project/tests/test_imports.py` (before the `if __name__` block; also extend the import line to `from facts.imports import build_dependency, extract_import_specs, find_cycles, is_entry_file, load_path_aliases, resolve_import` and add `from facts.walk import walk_project`):

```python
class ResolveJsTests(unittest.TestCase):
    known = {"src/a.ts", "src/b/index.tsx", "src/c.js", "src/lib/x.ts"}

    def test_relative_with_extension_guessing(self):
        self.assertEqual(resolve_import("./a", "src/main.ts", "typescript", self.known, {}, []), "src/a.ts")
        self.assertEqual(resolve_import("./b", "src/main.ts", "typescript", self.known, {}, []), "src/b/index.tsx")
        self.assertEqual(resolve_import("../c.js", "src/lib/x.ts", "typescript", self.known, {}, []), "src/c.js")

    def test_js_extension_mapped_to_ts(self):
        self.assertEqual(resolve_import("./a.js", "src/main.ts", "typescript", self.known, {}, []), "src/a.ts")

    def test_alias(self):
        self.assertEqual(resolve_import("@/lib/x", "src/app/page.tsx", "typescript", self.known, {"@/": "src/"}, []), "src/lib/x.ts")

    def test_third_party_and_missing(self):
        self.assertIsNone(resolve_import("react", "src/main.ts", "typescript", self.known, {}, []))
        self.assertIsNone(resolve_import("./nope", "src/main.ts", "typescript", self.known, {}, []))


class ResolvePyTests(unittest.TestCase):
    known = {"main.py", "utils.py", "app/__init__.py", "app/models.py", "app/api/routes.py", "src/pkg/__init__.py", "src/pkg/core.py"}
    roots = ["", "src"]

    def test_relative(self):
        self.assertEqual(resolve_import(".models", "app/api/routes.py", "python", self.known, {}, self.roots), None)
        self.assertEqual(resolve_import("..models", "app/api/routes.py", "python", self.known, {}, self.roots), "app/models.py")
        self.assertEqual(resolve_import(".", "app/models.py", "python", self.known, {}, self.roots), "app/__init__.py")

    def test_absolute_from_roots_and_script_dir(self):
        self.assertEqual(resolve_import("app.models", "main.py", "python", self.known, {}, self.roots), "app/models.py")
        self.assertEqual(resolve_import("app", "main.py", "python", self.known, {}, self.roots), "app/__init__.py")
        self.assertEqual(resolve_import("pkg.core", "main.py", "python", self.known, {}, self.roots), "src/pkg/core.py")
        self.assertEqual(resolve_import("utils", "main.py", "python", self.known, {}, self.roots), "utils.py")

    def test_from_import_falls_back_to_package_or_module(self):
        self.assertEqual(resolve_import("app.helper_fn", "main.py", "python", self.known, {}, self.roots), "app/__init__.py")
        self.assertEqual(resolve_import("app.models.Thing", "main.py", "python", self.known, {}, self.roots), "app/models.py")
        self.assertEqual(resolve_import(".name_in_init", "app/models.py", "python", self.known, {}, self.roots), "app/__init__.py")
        self.assertIsNone(resolve_import("app.nope.x", "main.py", "python", self.known, {}, self.roots))

    def test_stdlib_is_unresolved(self):
        self.assertIsNone(resolve_import("os.path", "main.py", "python", self.known, {}, self.roots))
        self.assertIsNone(resolve_import("os", "main.py", "python", self.known, {}, self.roots))


class CycleTests(unittest.TestCase):
    def test_two_node_cycle(self):
        graph = {"a": {"b"}, "b": {"a", "c"}, "c": set()}
        self.assertEqual(find_cycles(graph), [["a", "b", "a"]])

    def test_three_node_cycle_and_no_self_loops(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"d"}}
        self.assertEqual(find_cycles(graph), [["a", "b", "c", "a"]])

    def test_acyclic(self):
        self.assertEqual(find_cycles({"a": {"b"}, "b": set()}), [])


class EntryFileTests(unittest.TestCase):
    def test_entries(self):
        for path in ["src/app/page.tsx", "src/index.ts", "main.py", "manage.py",
                     "pkg/__init__.py", "next.config.js", "src/types.d.ts",
                     "tests/test_a.py", "top-level.ts", "src/app/api/x/route.ts"]:
            self.assertTrue(is_entry_file(path), path)

    def test_non_entries(self):
        for path in ["src/lib/utils.ts", "app/models.py", "src/components/Button.tsx"]:
            self.assertFalse(is_entry_file(path), path)


class BuildDependencyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_graph_cycles_orphans_and_unresolved(self):
        self.write("src/server.js", "const r = require('./routes');\nrequire('express');\n")
        self.write("src/routes.js", "const h = require('./handlers');\n")
        self.write("src/handlers.js", "const r = require('./routes');\nrequire('./missing');\n")
        self.write("src/legacy.js", "module.exports = 1;\n")
        files, _ = walk_project(self.root)
        dep = build_dependency(files, self.root)
        self.assertEqual(dep["edges"], [
            {"from": "src/handlers.js", "to": "src/routes.js"},
            {"from": "src/routes.js", "to": "src/handlers.js"},
            {"from": "src/server.js", "to": "src/routes.js"},
        ])
        self.assertEqual(dep["most_imported"][0], {"path": "src/routes.js", "imported_by": 2})
        self.assertEqual(dep["cycles"], [["src/handlers.js", "src/routes.js", "src/handlers.js"]])
        self.assertEqual(dep["orphans"], ["src/legacy.js"])
        self.assertEqual(dep["unresolved_imports"], 1)

    def test_python_absolute_unresolved_only_counted_when_local_looking(self):
        self.write("app/__init__.py", "")
        self.write("app/a.py", "import os\nfrom app.nope import x\nfrom app import b\n")
        self.write("app/b.py", "")
        files, _ = walk_project(self.root)
        dep = build_dependency(files, self.root)
        self.assertEqual(dep["edges"], [{"from": "app/a.py", "to": "app/b.py"}])
        self.assertEqual(dep["unresolved_imports"], 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ImportError for `build_dependency` etc.

- [ ] **Step 3: Append resolution and graph code**

Append to `understand-your-project/scripts/facts/imports.py`:

```python
JS_EXTS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]

ENTRY_STEMS = {
    "main", "index", "app", "page", "layout", "route", "server", "cli", "manage",
    "__main__", "__init__", "setup", "conftest", "middleware", "error", "loading",
    "not-found", "template", "default", "wsgi", "asgi", "instrumentation",
}


def is_entry_file(rel_path: str) -> bool:
    name = posixpath.basename(rel_path)
    stem = name.split(".")[0]
    if stem in ENTRY_STEMS:
        return True
    if ".config." in name or name.endswith(".d.ts"):
        return True
    if is_test_path(rel_path):
        return True
    return "/" not in rel_path


def _js_candidates(base: str) -> List[str]:
    candidates = [base]
    stem, ext = posixpath.splitext(base)
    if ext in JS_EXTS:
        candidates += [stem + e for e in JS_EXTS]
    candidates += [base + e for e in JS_EXTS]
    candidates += [posixpath.join(base, "index" + e) for e in JS_EXTS]
    return candidates


def _resolve_js(spec: str, from_path: str, known: Set[str], aliases: Dict[str, str]) -> Optional[str]:
    if spec.startswith("."):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(from_path), spec))
    else:
        base = None
        for prefix, target in aliases.items():
            if spec.startswith(prefix):
                base = posixpath.normpath(target + spec[len(prefix):])
                break
        if base is None:
            return None
    for candidate in _js_candidates(base):
        if candidate in known:
            return candidate
    return None


def _resolve_py(spec: str, from_path: str, known: Set[str], py_roots: List[str]) -> Optional[str]:
    dots = len(spec) - len(spec.lstrip("."))
    parts = [p for p in spec[dots:].split(".") if p]
    if dots:
        base = posixpath.dirname(from_path)
        for _ in range(dots - 1):
            base = posixpath.dirname(base)
        bases = [base]
    else:
        bases = [posixpath.dirname(from_path)] + list(py_roots)
    # `from M import name` arrives as `M.name`; if that is not a module, fall back to `M`.
    attempts = [parts]
    if parts and (dots or len(parts) > 1):
        attempts.append(parts[:-1])
    for candidate_parts in attempts:
        for base in bases:
            if candidate_parts:
                target = posixpath.normpath(posixpath.join(base, *candidate_parts))
            else:
                target = base or "."
            for candidate in (target + ".py", posixpath.join(target, "__init__.py")):
                candidate = posixpath.normpath(candidate)
                if candidate in known:
                    return candidate
    return None


def resolve_import(spec: str, from_path: str, language: str, known: Set[str],
                   aliases: Dict[str, str], py_roots: List[str]) -> Optional[str]:
    if language == "python":
        return _resolve_py(spec, from_path, known, py_roots)
    return _resolve_js(spec, from_path, known, aliases)


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Tarjan SCC; returns one closed path per component of size > 1."""
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    result: List[List[str]] = []
    counter = [0]

    def strongconnect(node: str) -> None:
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in sorted(graph.get(node, ())):
            if nxt not in index:
                strongconnect(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component = []
            while True:
                top = stack.pop()
                on_stack.discard(top)
                component.append(top)
                if top == node:
                    break
            if len(component) > 1:
                component.reverse()
                result.append(component + [component[0]])

    for node in sorted(graph):
        if node not in index:
            strongconnect(node)
    return sorted(result)


def _python_roots(known: Set[str]) -> List[str]:
    roots = {"", "src"}
    for path in known:
        if path.endswith("/__init__.py"):
            roots.add(posixpath.dirname(posixpath.dirname(path)))
    return sorted(roots)


def _looks_local_py(spec: str, known: Set[str]) -> bool:
    if spec.startswith("."):
        return True
    top_names = {p.split("/")[0].split(".")[0] for p in known}
    return spec.split(".")[0] in top_names


def build_dependency(source_files: List[SourceFile], root: Path) -> Dict:
    known = {f.path for f in source_files}
    aliases = load_path_aliases(root)
    py_roots = _python_roots(known)
    graph: Dict[str, Set[str]] = {f.path: set() for f in source_files}
    unresolved = 0
    for f in source_files:
        for spec in extract_import_specs(f.read_text(), f.language):
            target = resolve_import(spec, f.path, f.language, known, aliases, py_roots)
            if target is None:
                if f.language == "python":
                    unresolved += _looks_local_py(spec, known)
                elif spec.startswith(".") or any(spec.startswith(a) for a in aliases):
                    unresolved += 1
                continue
            if target != f.path:
                graph[f.path].add(target)
    in_degree = {path: 0 for path in graph}
    for targets in graph.values():
        for target in targets:
            in_degree[target] += 1
    edges = [{"from": src, "to": dst} for src in sorted(graph) for dst in sorted(graph[src])]
    most_imported = [
        {"path": path, "imported_by": count}
        for path, count in sorted(in_degree.items(), key=lambda kv: (-kv[1], kv[0]))
        if count > 0
    ][:10]
    orphans = sorted(p for p, count in in_degree.items() if count == 0 and not is_entry_file(p))
    return {
        "edges": edges,
        "most_imported": most_imported,
        "cycles": find_cycles(graph),
        "orphans": orphans,
        "unresolved_imports": unresolved,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK. If `test_relative` fails on `.models` from `app/api/routes.py`: that import correctly resolves to nothing because `app/api/models.py` does not exist; the assertion expects `None`.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/imports.py understand-your-project/tests/test_imports.py
git commit -m "feat(facts): resolve imports and build dependency graph with cycles and orphans

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Layer-mixing signals

**Files:**
- Create: `understand-your-project/scripts/facts/signals.py` (first half)
- Create: `understand-your-project/tests/test_signals.py` (first half)

**Interfaces:**
- Produces:
  - `layer_signals(text: str) -> tuple[list[str], list[str]]` returning `(categories, labels)`; categories subset of `["ui", "network", "data"]` in that order; labels are the matched signal names.
  - `layer_mixing(source_files) -> list[dict]` entries `{"path", "categories", "signals"}` for files hitting 2+ categories, sorted by path. Test files are skipped.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_signals.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from facts.signals import layer_mixing, layer_signals
from facts.walk import SourceFile


def sf(path, text, language="typescript"):
    f = SourceFile(path, Path("/nonexistent") / path, language, text.count("\n"))
    f._text = text
    return f


class LayerSignalTests(unittest.TestCase):
    def test_react_component_with_fetch_and_sql(self):
        text = """
export default function Page() {
  const [rows, setRows] = useState([]);
  useEffect(() => { fetch('/api'); }, []);
  const q = "SELECT * FROM users";
  return <Layout>{rows}</Layout>;
}
"""
        categories, labels = layer_signals(text)
        self.assertEqual(categories, ["ui", "network", "data"])
        self.assertEqual(labels, ["jsx", "useState", "useEffect", "fetch(", "SELECT"])

    def test_python_requests_and_sqlite(self):
        text = "import sqlite3\nimport requests\nr = requests.get(url)\n"
        categories, labels = layer_signals(text)
        self.assertEqual(categories, ["network", "data"])
        self.assertEqual(labels, ["requests.", "sqlite3"])

    def test_pure_logic_has_no_signals(self):
        self.assertEqual(layer_signals("def add(a, b):\n    return a + b\n"), ([], []))

    def test_returned_html_tag_is_ui(self):
        categories, _ = layer_signals("return <div/>;\n")
        self.assertEqual(categories, ["ui"])

    def test_typescript_generics_are_not_ui(self):
        text = "export async function load(): Promise<Array<string>> {\n  const r = await fetch('/x');\n  return r.json();\n}\n"
        self.assertEqual(layer_signals(text), (["network"], ["fetch("]))


class LayerMixingTests(unittest.TestCase):
    def test_reports_only_files_with_two_or_more_categories(self):
        files = [
            sf("src/page.tsx", "useState(); fetch('/x');\n"),
            sf("src/pure.ts", "export const a = 1;\n"),
            sf("src/db.ts", "prisma.user.findMany();\n"),
            sf("src/page.test.tsx", "useState(); fetch('/x');\n"),
        ]
        self.assertEqual(layer_mixing(files), [
            {"path": "src/page.tsx", "categories": ["ui", "network"], "signals": ["useState", "fetch("]},
        ])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ModuleNotFoundError for `facts.signals`.

- [ ] **Step 3: Write the layer signals**

`understand-your-project/scripts/facts/signals.py`:

```python
"""Heuristic signals: layer mixing, duplication, naming styles."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from .walk import SourceFile, is_test_path

_SIGNALS = [  # (category, label, pattern)
    # Returned JSX, a closing tag, or a tag with an attribute. Plain `<T>` generics do not count.
    ("ui", "jsx", re.compile(r"return\s*\(?\s*<[A-Za-z]|</[A-Za-z][\w.]*>|<[A-Za-z][\w.]*\s+[a-zA-Z-]+=")),
    ("ui", "useState", re.compile(r"\buseState\(")),
    ("ui", "useEffect", re.compile(r"\buseEffect\(")),
    ("ui", "document.", re.compile(r"\bdocument\.")),
    ("ui", "window.", re.compile(r"\bwindow\.")),
    ("ui", "streamlit", re.compile(r"\bimport streamlit\b|\bst\.(write|title|button|text_input)\(")),
    ("ui", "tkinter", re.compile(r"\btkinter\b")),
    ("network", "fetch(", re.compile(r"\bfetch\(")),
    ("network", "axios", re.compile(r"\baxios\b")),
    ("network", "requests.", re.compile(r"\brequests\.(get|post|put|delete|patch|request)\(")),
    ("network", "httpx", re.compile(r"\bhttpx\b")),
    ("network", "urllib", re.compile(r"\burllib\b")),
    ("data", "SELECT", re.compile(r"\bSELECT\s+.+?\s+FROM\b")),
    ("data", "INSERT", re.compile(r"\bINSERT\s+INTO\b")),
    ("data", "prisma.", re.compile(r"\bprisma\.")),
    ("data", "sqlite3", re.compile(r"\bsqlite3\b")),
    ("data", "sqlalchemy", re.compile(r"\bsqlalchemy\b")),
    ("data", "mongoose", re.compile(r"\bmongoose\b")),
    ("data", ".query(", re.compile(r"\.query\(")),
]
_CATEGORY_ORDER = ["ui", "network", "data"]


def layer_signals(text: str) -> Tuple[List[str], List[str]]:
    labels: List[str] = []
    categories: List[str] = []
    for category, label, pattern in _SIGNALS:
        if pattern.search(text):
            labels.append(label)
            if category not in categories:
                categories.append(category)
    categories.sort(key=_CATEGORY_ORDER.index)
    return categories, labels


def layer_mixing(source_files: List[SourceFile]) -> List[Dict]:
    results = []
    for f in sorted(source_files, key=lambda x: x.path):
        if is_test_path(f.path):
            continue
        categories, labels = layer_signals(f.read_text())
        if len(categories) >= 2:
            results.append({"path": f.path, "categories": categories, "signals": labels})
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/signals.py understand-your-project/tests/test_signals.py
git commit -m "feat(facts): detect layer-mixing signals

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Duplication and naming signals

**Files:**
- Modify: `understand-your-project/scripts/facts/signals.py` (append)
- Modify: `understand-your-project/tests/test_signals.py` (append)

**Interfaces:**
- Produces:
  - `similar_filenames(source_files) -> list[list[str]]` groups (sorted paths) of 2+ files whose normalized stem matches; generic stems excluded.
  - `repeated_function_names(source_files) -> list[dict]` entries `{"name", "files"}` for names defined in 3+ non-test files, sorted by name.
  - `classify_name(name: str) -> str | None` one of `snake_case`, `kebab-case`, `camelCase`, `PascalCase`, `mixed`, or `None` for flat single tokens.
  - `naming_styles(source_files) -> dict` with `file_case_styles` and `dir_case_styles` counters.

- [ ] **Step 1: Append the failing tests**

Append to `understand-your-project/tests/test_signals.py` (extend import line to `from facts.signals import classify_name, layer_mixing, layer_signals, naming_styles, repeated_function_names, similar_filenames`):

```python
class SimilarFilenameTests(unittest.TestCase):
    def test_groups_utils_synonyms_and_numbered_copies(self):
        files = [
            sf("src/utils.ts", ""), sf("src/utils2.ts", ""), sf("src/lib/helpers.ts", ""),
            sf("src/api/client.ts", ""), sf("src/api/client-v2.ts", ""),
            sf("src/app/page.tsx", ""), sf("src/app/about/page.tsx", ""),
            sf("src/unique.ts", ""),
        ]
        self.assertEqual(similar_filenames(files), [
            ["src/api/client-v2.ts", "src/api/client.ts"],
            ["src/lib/helpers.ts", "src/utils.ts", "src/utils2.ts"],
        ])


class RepeatedFunctionTests(unittest.TestCase):
    def test_names_in_three_or_more_files(self):
        files = [
            sf("a.ts", "export function formatDate(d) {}\nconst x = () => 1;\n"),
            sf("b.ts", "const formatDate = (d) => d;\n"),
            sf("c.py", "def formatDate(d):\n    pass\ndef main():\n    pass\n", "python"),
            sf("d.py", "async def formatDate(d):\n    pass\ndef main():\n    pass\n", "python"),
            sf("e.py", "def main():\n    pass\n", "python"),
            sf("f.test.ts", "function formatDate() {}\n"),
        ]
        self.assertEqual(repeated_function_names(files), [
            {"name": "formatDate", "files": ["a.ts", "b.ts", "c.py", "d.py"]},
        ])


class NamingTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify_name("user_service"), "snake_case")
        self.assertEqual(classify_name("user-service"), "kebab-case")
        self.assertEqual(classify_name("userService"), "camelCase")
        self.assertEqual(classify_name("UserService"), "PascalCase")
        self.assertEqual(classify_name("User_Service"), "mixed")
        self.assertIsNone(classify_name("utils"))
        self.assertIsNone(classify_name("__init__"))

    def test_counts_files_and_dirs(self):
        files = [
            sf("src/components/TodoList.tsx", ""),
            sf("src/components/todo-item.tsx", ""),
            sf("src/lib/date_utils.ts", ""),
            sf("src/my-feature/index.ts", ""),
        ]
        self.assertEqual(naming_styles(files), {
            "file_case_styles": {"PascalCase": 1, "kebab-case": 1, "snake_case": 1},
            "dir_case_styles": {"kebab-case": 1},
        })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ImportError for `similar_filenames` etc.

- [ ] **Step 3: Append the duplication and naming code**

Append to `understand-your-project/scripts/facts/signals.py`:

```python
_SYNONYMS = {
    "util": "utils", "utils": "utils", "utility": "utils", "utilities": "utils",
    "helper": "utils", "helpers": "utils", "common": "utils", "misc": "utils",
}
_GENERIC_STEMS = {
    "", "index", "__init__", "page", "layout", "route", "loading", "error",
    "main", "app", "test", "conftest", "setup", "types", "models", "views",
    "urls", "admin", "apps", "tests", "forms", "serializers", "schema",
    "component", "styles", "store", "hooks", "constants", "config", "settings",
    "notfound", "template", "default", "middleware",
}
_FUNC_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>", re.MULTILINE),
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE),
]
_IGNORED_FUNCS = {
    "main", "default", "setup", "test", "run", "init", "render", "handler",
    "index", "App", "Page", "Layout", "GET", "POST", "PUT", "DELETE", "PATCH",
    "generateMetadata", "loader", "action", "middleware",
}


def _normalize_stem(path: str) -> str:
    stem = path.rsplit("/", 1)[-1].split(".")[0].lower()
    stem = re.sub(r"[-_]?v?\d+$", "", stem)
    stem = stem.replace("-", "").replace("_", "")
    return _SYNONYMS.get(stem, stem)


def similar_filenames(source_files: List[SourceFile]) -> List[List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)
    for f in source_files:
        if is_test_path(f.path):
            continue
        key = _normalize_stem(f.path)
        if key in _GENERIC_STEMS:
            continue
        groups[key].append(f.path)
    return sorted(sorted(paths) for paths in groups.values() if len(paths) >= 2)


def repeated_function_names(source_files: List[SourceFile]) -> List[Dict]:
    where: Dict[str, set] = defaultdict(set)
    for f in source_files:
        if is_test_path(f.path):
            continue
        text = f.read_text()
        for pattern in _FUNC_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1)
                if name in _IGNORED_FUNCS or name.startswith("__"):
                    continue
                where[name].add(f.path)
    return [
        {"name": name, "files": sorted(files)}
        for name, files in sorted(where.items())
        if len(files) >= 3
    ]


def classify_name(name: str) -> "str | None":
    name = name.strip("_")
    if not name:
        return None
    if "-" in name:
        return "kebab-case"
    if "_" in name:
        return "snake_case" if name == name.lower() else "mixed"
    has_upper = any(c.isupper() for c in name)
    has_lower = any(c.islower() for c in name)
    if name[0].isupper() and has_lower:
        return "PascalCase"
    if name[0].islower() and has_upper:
        return "camelCase"
    return None


def naming_styles(source_files: List[SourceFile]) -> Dict:
    file_styles: Counter = Counter()
    dir_styles: Counter = Counter()
    seen_dirs = set()
    for f in source_files:
        parts = f.path.split("/")
        style = classify_name(parts[-1].split(".")[0])
        if style:
            file_styles[style] += 1
        for depth in range(1, len(parts)):
            directory = "/".join(parts[:depth])
            if directory in seen_dirs:
                continue
            seen_dirs.add(directory)
            style = classify_name(parts[depth - 1])
            if style:
                dir_styles[style] += 1
    return {
        "file_case_styles": dict(sorted(file_styles.items())),
        "dir_case_styles": dict(sorted(dir_styles.items())),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/signals.py understand-your-project/tests/test_signals.py
git commit -m "feat(facts): detect duplicated filenames, repeated functions and naming styles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Hygiene, secrets and docs discovery

**Files:**
- Create: `understand-your-project/scripts/facts/hygiene.py`
- Create: `understand-your-project/tests/test_hygiene.py`

**Interfaces:**
- Produces:
  - `suspected_secrets(source_files) -> list[str]` of `path:line`, test files skipped.
  - `find_docs(root: Path) -> list[str]`.
  - `hygiene(root: Path, source_files) -> dict` with `has_tests, test_paths, has_env_example, has_gitignore, has_lint_config, has_format_config, suspected_secrets, config_files`.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_hygiene.py`:

```python
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
        self.assertNotIn("hunter2", " ".join(result))

    def test_known_prefixes(self):
        self.write("a.js", 'const t = "ghp_abcdefghijklmnopqrstuvwxyz";\nconst k = "AKIAABCDEFGHIJKLMNOP";\n')
        files, _ = walk_project(self.root)
        self.assertEqual(suspected_secrets(files), ["a.js:1", "a.js:2"])


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: ModuleNotFoundError for `facts.hygiene`.

- [ ] **Step 3: Write the module**

`understand-your-project/scripts/facts/hygiene.py`:

```python
"""Engineering hygiene facts: tests, env files, lint/format config, secrets, docs."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List

from .walk import IGNORED_DIRS, SourceFile, is_test_path, load_gitignore_dirs

_SECRET_PATTERNS = [
    re.compile(r"""(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]"""),
    re.compile(r"""['"](sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})['"]"""),
]
_CONFIG_STEM = re.compile(r"(^|[_\-.])(config|settings|constants|env)([_\-.]|$)", re.IGNORECASE)
_TOOL_CONFIG = re.compile(r"^[\w\-]+\.config\.[cm]?[jt]s$")
_DOC_KEYWORDS = re.compile(r"(prd|spec|requirements|design)", re.IGNORECASE)
_DOC_EXCLUDE = {"CHANGELOG.md", "LICENSE.md", "ARCHITECTURE_REVIEW.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"}
_LINT_GLOBS = [".eslintrc", ".eslintrc.*", "eslint.config.*", "biome.json", "ruff.toml", ".ruff.toml", ".flake8", ".pylintrc"]
_FORMAT_GLOBS = [".prettierrc", ".prettierrc.*", "prettier.config.*", "biome.json"]


def _any_glob(root: Path, globs: List[str]) -> bool:
    return any(next(root.glob(g), None) is not None for g in globs)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def suspected_secrets(source_files: List[SourceFile]) -> List[str]:
    found: List[str] = []
    for f in sorted(source_files, key=lambda x: x.path):
        if is_test_path(f.path):
            continue
        for number, line in enumerate(f.read_text().splitlines(), start=1):
            if any(p.search(line) for p in _SECRET_PATTERNS):
                found.append("%s:%d" % (f.path, number))
    return found


def find_docs(root: Path) -> List[str]:
    ignored = IGNORED_DIRS | load_gitignore_dirs(root)
    docs: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignored)
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        depth = 0 if rel_dir == "." else rel_dir.count("/") + 1
        for name in sorted(filenames):
            if not name.lower().endswith(".md") or name in _DOC_EXCLUDE:
                continue
            rel = name if rel_dir == "." else rel_dir + "/" + name
            upper = name.upper()
            if depth == 0 and (upper.startswith("README") or name in ("CLAUDE.md", "AGENTS.md")):
                docs.append(rel)
            elif rel.startswith("docs/"):
                docs.append(rel)
            elif depth <= 3 and _DOC_KEYWORDS.search(name):
                docs.append(rel)
    return sorted(docs)


def hygiene(root: Path, source_files: List[SourceFile]) -> Dict:
    pyproject = _read(root / "pyproject.toml") if (root / "pyproject.toml").is_file() else ""
    setup_cfg = _read(root / "setup.cfg") if (root / "setup.cfg").is_file() else ""
    test_paths = sorted(f.path for f in source_files if is_test_path(f.path))
    config_files = sorted(
        f.path for f in source_files
        if not is_test_path(f.path)
        and _CONFIG_STEM.search(f.path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        and not _TOOL_CONFIG.match(f.path.rsplit("/", 1)[-1])
    )
    return {
        "has_tests": bool(test_paths),
        "test_paths": test_paths,
        "has_env_example": any((root / n).is_file() for n in (".env.example", ".env.sample", ".env.template")),
        "has_gitignore": (root / ".gitignore").is_file(),
        "has_lint_config": _any_glob(root, _LINT_GLOBS) or "[tool.ruff]" in pyproject or "[flake8]" in setup_cfg,
        "has_format_config": _any_glob(root, _FORMAT_GLOBS) or "[tool.black]" in pyproject or "[tool.ruff.format]" in pyproject,
        "suspected_secrets": suspected_secrets(source_files),
        "config_files": config_files,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK. Note `next.config.js` is excluded from `config_files` by `_TOOL_CONFIG`, and `app-config.ts` matches because the stem `app-config` contains `-config`.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/scripts/facts/hygiene.py understand-your-project/tests/test_hygiene.py
git commit -m "feat(facts): add hygiene, secret position and docs discovery

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Assembler and CLI

**Files:**
- Create: `understand-your-project/scripts/facts/collect.py`
- Create: `understand-your-project/scripts/collect_facts.py`
- Create: `understand-your-project/tests/test_cli.py`

**Interfaces:**
- Consumes: every module above.
- Produces:
  - `collect(root: Path) -> dict` with the exact top-level keys from the spec: `root, project_type, scale, tree, largest_files, dependency, layer_mixing, duplication, naming, hygiene, docs`.
  - CLI `python3 collect_facts.py <project_path>`: JSON on stdout (indent 2, `ensure_ascii=False`), exit 0; on bad path or exception, one-line `error: ...` on stderr, exit 1. Also supports `--compact` for single-line JSON.

- [ ] **Step 1: Write the failing tests**

`understand-your-project/tests/test_cli.py`:

```python
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_facts.py"


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

    def test_missing_directory_errors(self):
        proc = self.run_cli(str(self.root / "nope"))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.startswith("error:"))
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: FileNotFoundError (script missing) or returncode assertion failures.

- [ ] **Step 3: Write assembler and CLI**

`understand-your-project/scripts/facts/collect.py`:

```python
"""Assemble all fact categories into one JSON-serializable dict."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from .hygiene import find_docs, hygiene
from .imports import build_dependency
from .project_type import detect_project_type
from .signals import layer_mixing, naming_styles, repeated_function_names, similar_filenames
from .structure import build_tree, largest_files, scale
from .walk import walk_project


def collect(root: Path) -> Dict:
    source_files, total_files = walk_project(root)
    return {
        "root": str(root),
        "project_type": detect_project_type(root, source_files),
        "scale": scale(source_files, total_files),
        "tree": build_tree(source_files),
        "largest_files": largest_files(source_files),
        "dependency": build_dependency(source_files, root),
        "layer_mixing": layer_mixing(source_files),
        "duplication": {
            "similar_filenames": similar_filenames(source_files),
            "repeated_function_names": repeated_function_names(source_files),
        },
        "naming": naming_styles(source_files),
        "hygiene": hygiene(root, source_files),
        "docs": find_docs(root),
    }
```

`understand-your-project/scripts/collect_facts.py`:

```python
#!/usr/bin/env python3
"""Collect structural facts about a JS/TS or Python project and print them as JSON.

Usage: python3 collect_facts.py [--compact] <project_path>

Standard library only. Never judges; only counts and locates.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from facts.collect import collect  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_path", help="path to the project root")
    parser.add_argument("--compact", action="store_true", help="single-line JSON")
    args = parser.parse_args(argv)
    root = Path(args.project_path).expanduser().resolve()
    if not root.is_dir():
        print("error: %s is not a directory" % root, file=sys.stderr)
        return 1
    try:
        facts = collect(root)
    except Exception as exc:  # noqa: BLE001 - the agent needs the reason, whatever it is
        print("error: failed to collect facts: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    if args.compact:
        print(json.dumps(facts, ensure_ascii=False))
    else:
        print(json.dumps(facts, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Then: `chmod +x understand-your-project/scripts/collect_facts.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK.

- [ ] **Step 5: Smoke-run on this repo**

Run: `python3 understand-your-project/scripts/collect_facts.py . | head -40`
Expected: JSON starting with `"root"`, `project_type.languages == ["python"]`, no traceback.

- [ ] **Step 6: Commit**

```bash
git add understand-your-project/scripts understand-your-project/tests/test_cli.py
git commit -m "feat(facts): add collect() assembler and collect_facts CLI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Fixture projects and integration tests

**Files:**
- Create: `understand-your-project/tests/fixtures/clean-next/**`
- Create: `understand-your-project/tests/fixtures/monolith-py/**`
- Create: `understand-your-project/tests/fixtures/cyclic-node/**`
- Create: `understand-your-project/tests/test_integration.py`

**Interfaces:**
- Consumes: `collect(root)`.
- Produces: three committed fixture projects used by Task 16's EVALS.

- [ ] **Step 1: Create fixture `clean-next`**

Create these files under `understand-your-project/tests/fixtures/clean-next/`:

`package.json`:
```json
{
  "name": "clean-next",
  "private": true,
  "dependencies": { "next": "14.2.0", "react": "18.3.0", "react-dom": "18.3.0" },
  "devDependencies": { "eslint": "8.57.0", "prettier": "3.3.0", "typescript": "5.4.0", "vitest": "1.6.0" }
}
```
`package-lock.json`: `{}`
`.gitignore`:
```
node_modules/
.next/
.env
```
`.env.example`: `NEXT_PUBLIC_API_URL=http://localhost:3000`
`.eslintrc.json`: `{ "extends": "next/core-web-vitals" }`
`.prettierrc`: `{ "semi": true }`
`tsconfig.json`:
```json
{ "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["./src/*"] }, "jsx": "preserve", "strict": true } }
```
`README.md`:
```markdown
# Clean Next

A small todo list. Personal use. Built with Next.js App Router.
```
`src/app/layout.tsx`:
```tsx
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```
`src/app/page.tsx`:
```tsx
import { TodoList } from "@/components/TodoList";

export default function HomePage() {
  return <TodoList />;
}
```
`src/components/TodoList.tsx`:
```tsx
"use client";
import { useState } from "react";
import { addTodo, type Todo } from "@/lib/todos";

export function TodoList() {
  const [todos, setTodos] = useState<Todo[]>([]);
  return (
    <ul>
      {todos.map((t) => (
        <li key={t.id}>{t.title}</li>
      ))}
      <button onClick={() => setTodos(addTodo(todos, "New"))}>Add</button>
    </ul>
  );
}
```
`src/lib/todos.ts`:
```ts
export type Todo = { id: number; title: string; done: boolean };

export function addTodo(todos: Todo[], title: string): Todo[] {
  return [...todos, { id: todos.length + 1, title, done: false }];
}
```
`src/lib/todos.test.ts`:
```ts
import { addTodo } from "./todos";

test("adds a todo", () => {
  expect(addTodo([], "x")).toHaveLength(1);
});
```

- [ ] **Step 2: Create fixture `monolith-py`**

`understand-your-project/tests/fixtures/monolith-py/requirements.txt`:
```
flask==3.0.0
requests==2.31.0
```
`understand-your-project/tests/fixtures/monolith-py/README.md`:
```markdown
# Monolith

Inventory API for a small shop. Everything lives in main.py.
```
Generate `main.py` (do not hand-write 700 lines) by running this from the repo root:

```bash
python3 - <<'PY'
from pathlib import Path
header = '''import sqlite3
import requests
from flask import Flask, jsonify

app = Flask(__name__)
API_KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"
DB = sqlite3.connect("shop.db", check_same_thread=False)


'''
block = '''@app.route("/items/{i}")
def get_item_{i}():
    row = DB.execute("SELECT * FROM items WHERE id = {i}").fetchone()
    remote = requests.get("https://example.com/items/{i}", headers={{"Authorization": API_KEY}})
    return jsonify({{"row": row, "remote": remote.status_code}})


'''
body = "".join(block.format(i=i) for i in range(100))
Path("understand-your-project/tests/fixtures/monolith-py/main.py").write_text(header + body, encoding="utf-8")
PY
wc -l understand-your-project/tests/fixtures/monolith-py/main.py
```
Expected: about 708 lines.

- [ ] **Step 3: Create fixture `cyclic-node`**

`understand-your-project/tests/fixtures/cyclic-node/package.json`:
```json
{ "name": "cyclic-node", "dependencies": { "express": "4.19.0" } }
```
`understand-your-project/tests/fixtures/cyclic-node/src/server.js`:
```js
const express = require("express");
const routes = require("./routes");

const app = express();
app.use(routes);
app.listen(3000);
```
`understand-your-project/tests/fixtures/cyclic-node/src/routes.js`:
```js
const express = require("express");
const handlers = require("./handlers");

const router = express.Router();
router.get("/", handlers.home);
module.exports = router;
```
`understand-your-project/tests/fixtures/cyclic-node/src/handlers.js`:
```js
const routes = require("./routes");

function home(req, res) {
  res.send("home");
}
module.exports = { home, routes };
```
`understand-your-project/tests/fixtures/cyclic-node/src/legacy.js`:
```js
module.exports = function oldHelper() {
  return "unused";
};
```

- [ ] **Step 4: Write the integration tests**

`understand-your-project/tests/test_integration.py`:

```python
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
```

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all OK. If `suspected_secrets` line number differs from 6, count the header lines in the generator and fix the assertion to match the actual `API_KEY` line.

- [ ] **Step 6: Commit**

```bash
git add understand-your-project/tests
git commit -m "test: add fixture projects and integration tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Interview reference

**Files:**
- Create: `understand-your-project/references/interview.md`

**Interfaces:**
- Produces: the requirements profile format `{purpose, scale_tier, evolution_tier, pain_points}` consumed by `checklist.md` (Task 12) and `report-template.md` (Task 14).

- [ ] **Step 1: Write the file**

`understand-your-project/references/interview.md`:

````markdown
# Requirements interview

Purpose: learn what the project is for and where it is going, so the checklist can
judge "good enough for this project" instead of "good in the abstract". Ask in the
user's conversation language. Ask ONE question per message and wait for the answer.

## Step 1: Draft from existing docs

Read every path listed in `facts.docs` (README, CLAUDE.md, AGENTS.md, docs/, PRD-like
files). Write a 2-4 sentence draft:

> From what I can see, this project is <what it does>, built with <frameworks>, and
> seems intended for <who>. Is that right?

If `facts.docs` is empty, base the draft on directory names, framework and largest
files, and open with "From the code alone, this looks like...".

## Step 2: Four questions, one at a time

**Q1. What is this project for?** Present the draft from Step 1 and ask the user to
confirm or correct it. Open answer.

**Q2. Who uses it?** Offer exactly these options:
- A. Only me
- B. A few people I know (family, friends, teammates)
- C. The public, or anyone who signs up

**Q3. Where is it going in the next six months?** Offer these options; more than one
may apply:
- A. Basically done, just keep it running
- B. I will keep adding features
- C. I plan to launch it properly or charge for it
- D. Other people will work on the code with me

**Q4. What hurts most right now?** Offer these options:
- A. Changing one thing breaks something else
- B. The AI is getting worse at making changes to it
- C. It is slow
- D. Nothing really, I just want to understand it
- E. Something else (tell me)

## Step 3: Build the requirements profile

| Field | Value | Source |
|---|---|---|
| `purpose` | one sentence in the user's words | Q1 |
| `scale_tier` | `personal` (Q2=A), `small_group` (Q2=B), `public` (Q2=C) | Q2 |
| `evolution_tier` | `frozen` (A), `iterating` (B), `launching` (C), `collaborative` (D). If several chosen, take the heaviest: frozen < iterating < launching < collaborative | Q3 |
| `pain_points` | list of chosen labels: `breaks_elsewhere`, `ai_struggles`, `slow`, `none`, or free text | Q4 |

State the profile back to the user in one short paragraph before analysis begins.

## If the user declines or skips questions

Use `scale_tier = small_group` and `evolution_tier = iterating`, `pain_points = []`.
Mark the report header with "Assumptions: judged using default profile (small group,
actively iterating) because the interview was skipped."
````

- [ ] **Step 2: Verify the file reads cleanly**

Run: `sed -n '1,20p' understand-your-project/references/interview.md`
Expected: the heading and Step 1 text appear, no stray code-fence characters.

- [ ] **Step 3: Commit**

```bash
git add understand-your-project/references/interview.md
git commit -m "docs(skill): add requirements interview reference

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Checklist reference

**Files:**
- Create: `understand-your-project/references/checklist.md`

**Interfaces:**
- Consumes: JSON field names from Tasks 1-9 and the profile from Task 11.
- Produces: item IDs `A1..A4, B1..B3, C1..C3, D1..D4, E1..E2` and severities `must_fix / should_fix / note` used by the report template.

- [ ] **Step 1: Write the file**

`understand-your-project/references/checklist.md`:

````markdown
# Architecture checklist

Sixteen items in five dimensions. For each item: read the evidence field in the facts
JSON, apply the threshold, assign the base severity, then apply the tier adjustments at
the end of this file. Every finding in the report must cite the concrete paths and
numbers from the JSON. Never report an item without evidence.

Severity levels:
- **must_fix**: will cause an incident or block development soon.
- **should_fix**: not painful today, will be within six months on the user's stated path.
- **note**: worth knowing; no action required.

Format of each item below: what it is (plain words) / evidence / threshold / base
severity / what happens if ignored / usual fix.

## A. Layers and responsibilities

### A1. Giant file
- **Plain words:** One file does far too many things. Nobody, human or AI, can hold it in their head.
- **Evidence:** `largest_files[].lines`
- **Threshold:** over 500 lines is a candidate; over 1000 lines always reported.
- **Base severity:** should_fix; must_fix when over 1000 lines.
- **If ignored:** Every change touches the same file, merge conflicts and regressions pile up, AI edits get sloppy.
- **Usual fix:** Split by responsibility (routes, data access, business rules, UI) into separate files under a folder named after the feature.

### A2. UI code talks directly to data or network
- **Plain words:** A screen or component also fetches from the internet or runs database queries itself.
- **Evidence:** `layer_mixing[]` where `categories` includes `ui` together with `network` or `data`.
- **Threshold:** any such file.
- **Base severity:** should_fix.
- **If ignored:** You cannot change where data comes from without rewriting screens; testing the screen requires a live database.
- **Usual fix:** Move fetching and queries into a `lib/`, `services/` or `api/` module and call it from the component.

### A3. Business logic lives in routes or pages
- **Plain words:** The rules of your app are written inside the request handlers or page files instead of a place of their own.
- **Evidence:** `largest_files[]` entries whose path contains `page`, `route`, `views`, `api` or `handlers` and whose `lines` exceed 300.
- **Threshold:** any such file.
- **Base severity:** should_fix.
- **If ignored:** The same rule gets copied into the next route; fixing it once no longer fixes it everywhere.
- **Usual fix:** Extract the rules into plain functions in a `services/` or `domain/` folder; routes only parse input and call them.

### A4. One "god utils" file
- **Plain words:** A single helper file that almost everything depends on and that keeps growing.
- **Evidence:** `dependency.most_imported[]` and `largest_files[]`.
- **Threshold:** a file imported by more than 30% of `scale.source_files` and longer than 300 lines.
- **Base severity:** should_fix.
- **If ignored:** Any edit to it can break the whole app; it becomes the file nobody dares touch.
- **Usual fix:** Split it by topic (`date.ts`, `format.ts`, `validation.ts`) and update imports.

## B. Dependencies and coupling

### B1. Circular dependency
- **Plain words:** File A needs B and B needs A. Loading order becomes fragile and neither can be understood alone.
- **Evidence:** `dependency.cycles[]`.
- **Threshold:** non-empty.
- **Base severity:** must_fix.
- **If ignored:** Mysterious "undefined" errors, imports that work in one place and fail in another, impossible to extract either file.
- **Usual fix:** Move the shared piece both files need into a third file that neither imports from.

### B2. Orphan files and dead code
- **Plain words:** Files nothing uses any more.
- **Evidence:** `dependency.orphans[]`.
- **Threshold:** non-empty; more than 10 raises severity.
- **Base severity:** note; should_fix when over 10.
- **If ignored:** Readers and AI waste time on code that does nothing; old bugs get "fixed" in files that never run.
- **Usual fix:** Confirm each is unused, then delete it (git keeps history).

### B3. Dependency direction is inverted
- **Plain words:** Low-level helper code reaches up and imports from screens or routes.
- **Evidence:** `dependency.edges[]` compared with the layer order of the matching template in `reference-architectures.md`. Generic order, low to high: `utils`/`lib`/`shared` < `services`/`db`/`models`/`data` < `components`/`hooks` < `pages`/`app`/`routes`/`api`/`views`. An edge whose `from` directory is lower than its `to` directory is inverted.
- **Threshold:** any inverted edge.
- **Base severity:** should_fix.
- **If ignored:** Nothing is reusable; the helper cannot be tested without the whole app.
- **Usual fix:** Pass the needed value in as a parameter instead of importing it from above.

## C. Duplication and consistency

### C1. Near-duplicate files
- **Plain words:** `utils.ts`, `utils2.ts` and `helpers.ts` all exist; nobody knows which is current.
- **Evidence:** `duplication.similar_filenames[]`.
- **Threshold:** non-empty.
- **Base severity:** should_fix.
- **If ignored:** Fixes land in one copy; the other copy keeps the bug.
- **Usual fix:** Merge into one file, delete the rest.

### C2. Same logic copied in several places
- **Plain words:** A function with the same name is defined in several files.
- **Evidence:** `duplication.repeated_function_names[]`.
- **Threshold:** non-empty; a name in more than 5 files raises severity.
- **Base severity:** note; should_fix when any name appears in over 5 files.
- **If ignored:** Behavior drifts between copies.
- **Usual fix:** Keep one definition in a shared module and import it.

### C3. Inconsistent naming
- **Plain words:** Some files are `userService.ts`, others `user_service.ts`, others `user-service.ts`.
- **Evidence:** `naming.file_case_styles`, `naming.dir_case_styles`.
- **Threshold:** within either map, the second most common style is over 20% of the total count.
- **Base severity:** note.
- **If ignored:** Harder to find files; AI guesses wrong paths.
- **Usual fix:** Pick one convention per language (kebab-case for JS/TS files, snake_case for Python) and rename gradually.

## D. Engineering hygiene

### D1. No tests
- **Plain words:** Nothing automatically checks that the app still works after a change.
- **Evidence:** `hygiene.has_tests`.
- **Threshold:** `false`.
- **Base severity:** should_fix.
- **If ignored:** Every change is a gamble; AI cannot verify its own edits.
- **Usual fix:** Add one test file for the most important function, then grow from there.

### D2. Secrets hard-coded
- **Plain words:** A password, API key or token is written directly in the code.
- **Evidence:** `hygiene.suspected_secrets[]` (positions only).
- **Threshold:** non-empty.
- **Base severity:** must_fix. Never lowered by any tier rule.
- **If ignored:** Anyone with the code, including public repos and AI logs, has your key.
- **Usual fix:** Move to environment variables, add `.env` to `.gitignore`, rotate the exposed key.

### D3. Missing `.env.example` or `.gitignore`
- **Plain words:** No template showing which settings the app needs, or no list of files git should ignore.
- **Evidence:** `hygiene.has_env_example`, `hygiene.has_gitignore`, `hygiene.config_files`.
- **Threshold:** either is `false` and `config_files` is non-empty.
- **Base severity:** should_fix.
- **If ignored:** New machines cannot run the app; secrets and build junk get committed.
- **Usual fix:** Add both files; list every required variable in `.env.example` with placeholder values.

### D4. No lint or format configuration
- **Plain words:** No tool enforces consistent style or catches obvious mistakes.
- **Evidence:** `hygiene.has_lint_config`, `hygiene.has_format_config`.
- **Threshold:** either is `false`.
- **Base severity:** note.
- **If ignored:** Style drifts, trivial bugs slip through.
- **Usual fix:** Add ESLint + Prettier (JS/TS) or Ruff (Python) with default config.

## E. Ability to evolve

### E1. Folders grouped by file type instead of feature
- **Plain words:** Everything is in `components/`, `utils/`, `hooks/`, `types/`; a single feature is scattered across all of them.
- **Evidence:** `tree[]` entries at depth 1 or 2 whose last path segment is one of `components utils hooks types helpers services models` and whose `files` exceed 20.
- **Threshold:** any such directory, and no feature-named directories at the same depth.
- **Base severity:** note; should_fix when `evolution_tier == collaborative`.
- **If ignored:** Adding a feature means touching six folders; deleting one means hunting through all of them.
- **Usual fix:** Group by feature (`features/todos/`, `features/auth/`) with shared code in `shared/`.

### E2. Configuration and constants scattered
- **Plain words:** Settings live in several files in several places.
- **Evidence:** `hygiene.config_files[]`.
- **Threshold:** more than 3 files across more than one directory.
- **Base severity:** note.
- **If ignored:** Changing a setting requires finding every copy.
- **Usual fix:** One `config/` module that reads environment variables and exports typed values.

## Tier adjustment rules

Apply in this order. Each step moves severity by at most one level. Floor is `note`,
ceiling is `must_fix`. D2 is never lowered.

1. `scale_tier == personal`: lower every D and E item by one level, except D2.
2. `evolution_tier == frozen`: set every E item to `note`.
3. `evolution_tier == collaborative`: raise C3, D1, E1 by one level.
4. `evolution_tier in (launching, collaborative)`: raise D1, D3 by one level.
5. `pain_points` contains `breaks_elsewhere`: raise every A and B item by one level.
6. `pain_points` contains `ai_struggles`: raise A1, A4, E1 by one level.
7. Items touched by rules 5 or 6 are listed first in the report's findings section.

## Out-of-scope projects

When `scale.out_of_scope` is true, evaluate only D1-D4 and E1 (top-level structure).
State in the report that per-file analysis was not performed.

## Unreliable dependency data

When `dependency.unresolved_imports` exceeds 30% of the total number of edges plus
unresolved imports, mark every B item "needs confirmation" and say why.
````

- [ ] **Step 2: Cross-check field names against the JSON**

Run: `python3 understand-your-project/scripts/collect_facts.py understand-your-project/tests/fixtures/monolith-py | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d)); print(sorted(d['hygiene'])); print(sorted(d['dependency']))"`
Expected: every field referenced in checklist.md (`largest_files`, `layer_mixing`, `dependency.most_imported`, `dependency.cycles`, `dependency.orphans`, `dependency.edges`, `dependency.unresolved_imports`, `duplication.similar_filenames`, `duplication.repeated_function_names`, `naming.file_case_styles`, `naming.dir_case_styles`, `hygiene.has_tests`, `hygiene.suspected_secrets`, `hygiene.has_env_example`, `hygiene.has_gitignore`, `hygiene.config_files`, `hygiene.has_lint_config`, `hygiene.has_format_config`, `tree`, `scale.out_of_scope`, `scale.source_files`) appears in the printed keys.

- [ ] **Step 3: Commit**

```bash
git add understand-your-project/references/checklist.md
git commit -m "docs(skill): add 16-item architecture checklist with tier rules

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Reference architectures

**Files:**
- Create: `understand-your-project/references/reference-architectures.md`

**Interfaces:**
- Consumes: `project_type.frameworks`, `project_type.languages`, `project_type.monorepo`.
- Produces: five templates each with a directory skeleton, per-directory purpose, "skip when small" notes and a layer order used by checklist B3.

- [ ] **Step 1: Write the file**

`understand-your-project/references/reference-architectures.md`:

````markdown
# Reference architectures

Use these to draw the "suggested target structure" in the report. Rules:

1. Pick the template by the rule in each heading. If none matches, skip the target
   structure entirely and say so in the report.
2. Only include directories that relate to a finding in the report. Do not ask the
   user to rearrange parts that are already fine.
3. Every added or moved directory in the target structure must be annotated with the
   checklist item ID that motivates it.
4. Layer order is listed low to high; checklist B3 treats an import from a lower
   layer to a higher one as inverted.

## T1. Next.js / React front-end app
Matches when `frameworks` contains `next` or `react` and no back-end framework
(`express`, `fastify`, `nest`, `koa`, `hono`, `fastapi`, `django`, `flask`).

```
src/
  app/            routes and pages only; each file wires a screen together
  features/       one folder per user-facing feature: its components, hooks, logic
    <feature>/
      components/
      hooks/
      api.ts      calls to the backend for this feature
  shared/         reused by several features
    components/   generic UI (Button, Modal)
    hooks/
    lib/          pure helpers, no React
  config/         environment reading, constants
```
Skip when small: `features/` is unnecessary under about 15 components; keep
`components/` and `lib/` flat until then.
Layer order: `shared/lib` < `config` < `shared/components`, `shared/hooks` < `features` < `app`.

## T2. Node back-end API
Matches when `frameworks` contains any of `express fastify nest koa hono`.

```
src/
  routes/         HTTP wiring: parse request, call a service, send response
  services/       business rules; no HTTP objects in here
  db/             database access: queries, models, migrations
  lib/            pure helpers
  config/         environment reading
  server.ts       creates the app and starts listening
```
Skip when small: under about 5 routes, `services/` may be one file.
Layer order: `lib` < `config` < `db` < `services` < `routes` < `server`.

## T3. Python back-end API
Matches when `frameworks` contains any of `fastapi django flask`.

```
app/
  api/            route handlers (FastAPI routers, Flask blueprints, Django views)
  services/       business rules
  models/         database models and schemas
  db/             session, connection, migrations
  core/           settings, logging, shared helpers
  main.py         builds the app
tests/
```
Django note: keep Django's per-app layout (`<app>/models.py`, `views.py`, `urls.py`);
map `services/` to a `services.py` inside each app.
Skip when small: under about 5 endpoints, `services/` and `api/` may each be one file.
Layer order: `core` < `db` < `models` < `services` < `api` < `main`.

## T4. Python scripts or data tool
Matches when `languages` is only `python` and no web framework is present.

```
<package_name>/
  __init__.py
  cli.py          argument parsing and entry point
  core.py         the actual work, importable and testable
  io.py           reading and writing files, APIs
  config.py
scripts/          one-off scripts that import the package
tests/
```
Skip when small: a single-purpose script under about 200 lines can stay one file.
Layer order: `config` < `io` < `core` < `cli` < `scripts`.

## T5. Full-stack single repo
Matches when both a front-end template (T1) and a back-end template (T2 or T3) match,
or `monorepo` is true.

```
apps/
  web/            front-end, laid out per T1
  api/            back-end, laid out per T2 or T3
packages/         code shared by both (types, validation)
```
Skip when small: without a build tool that understands workspaces, `frontend/` and
`backend/` as two top-level folders is enough.
Layer order: `packages` < `apps/api` < `apps/web`.
````

- [ ] **Step 2: Verify headings**

Run: `grep -n '^## T' understand-your-project/references/reference-architectures.md`
Expected: five lines, T1 through T5.

- [ ] **Step 3: Commit**

```bash
git add understand-your-project/references/reference-architectures.md
git commit -m "docs(skill): add reference architectures for JS/TS and Python projects

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 14: Report template

**Files:**
- Create: `understand-your-project/references/report-template.md`

**Interfaces:**
- Consumes: checklist IDs and severities, profile fields, facts JSON.
- Produces: the five-section layout of `ARCHITECTURE_REVIEW.md` and the verdict rule.

- [ ] **Step 1: Write the file**

`understand-your-project/references/report-template.md`:

````markdown
# Report template

File: `ARCHITECTURE_REVIEW.md` at the project root. Overwrite if present. Write in the
user's conversation language. Translate every heading below; keep the order and the
item IDs (A1, B2...) untouched.

Writing rules:
- No jargon. If a technical word is unavoidable, explain it in parentheses the first time.
- Every finding cites paths and numbers from the facts JSON. No "it feels messy".
- Never invent a path. Every path must appear in the JSON.
- Section 2 is for a reader who has never opened the code. Write it like you are
  showing someone around a house.
- After writing the file, summarize in chat in at most five sentences and give the path.

## Header

```
# Architecture review: <project name from package.json / pyproject / directory name>
Generated: <YYYY-MM-DD>
<If interview skipped: "Assumptions: judged using default profile (small group, actively iterating) because the interview was skipped.">
<If out_of_scope: "Scope: this project exceeds the per-file analysis limit; only top-level structure was reviewed.">
```

## Section 1: One-line verdict

Pick exactly one:
- **Healthy** when there are zero `must_fix` and at most 2 `should_fix`.
- **A few things to fix** otherwise, unless:
- **Needs a proper tidy-up** when there is at least one `must_fix` or more than 5 `should_fix`.

Follow with one sentence saying why, naming the biggest item.

## Section 2: What your project looks like today

- Two to four sentences: what kind of project (template name in plain words), how many
  files and lines, what the main folders are for.
- An ASCII tree from `facts.tree` limited to depth 3, one short comment per directory:

```
src/                 118 files   everything the app is made of
  app/                30 files   the screens users see
  components/         41 files   reusable pieces of screens
  lib/                12 files   helpers with no UI
```

## Section 3: What we assumed about your needs

Restate the requirements profile: purpose, who uses it, where it is going, what hurts.
Ask the reader to correct anything wrong, because every judgment below depends on it.

## Section 4: What we found

Group by severity in this order: must_fix, should_fix, note. Within a group, items
raised by the user's pain points come first, then by ID. Each finding uses exactly this
shape:

```
### <ID>. <Name in plain words>
- **What it is:** one or two sentences.
- **Evidence:** `path` (N lines), `path:line`, counts. Copied from the JSON.
- **Why it matters for you:** tie to the profile (e.g. "since other people will edit this code...").
- **If ignored:** one sentence.
```

If a dimension has no findings, say so in one line ("No dependency problems found.").
If B items are marked "needs confirmation" because of unresolved imports, say so once
at the top of the section.

## Section 5: What to do about it

One entry per finding, ordered by benefit high and risk low first. Shape:

```
### Fix for <ID>: <short title>
- **Scope:** which files or folders change.
- **Risk:** low / medium / high, with one reason.
- **Effort:** small (under an hour) / medium (an afternoon) / large (a day or more).
- **Task for your agent:** a self-contained paragraph the user can paste into a new
  session. Names the files, the target layout, and what must keep working.
```

If a template matched, end with "Suggested target structure": an ASCII tree containing
only the parts that change, each annotated with the ID that motivates it.

Close with one line: this report does not change any code; pick a fix and hand its task
to your agent when ready.
````

- [ ] **Step 2: Verify section count**

Run: `grep -c '^## Section' understand-your-project/references/report-template.md`
Expected: `5`.

- [ ] **Step 3: Commit**

```bash
git add understand-your-project/references/report-template.md
git commit -m "docs(skill): add report template

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 15: SKILL.md

**Files:**
- Create: `understand-your-project/SKILL.md`

**Interfaces:**
- Consumes: all references and the CLI.
- Produces: the skill entry point with frontmatter `name` and `description`.

- [ ] **Step 1: Write the file**

`understand-your-project/SKILL.md`:

````markdown
---
name: understand-your-project
description: Analyze a project's code architecture, judge it against what the project actually needs, and write a plain-language report with concrete fixes. Use when the user asks whether their project structure or architecture is good, wants to understand how their code is organized, asks if their code is a mess (屎山), or says things like "analyze my project structure", "review my architecture", "understand my project", "is my code structure ok".
---

# Understand Your Project

You are helping someone who may have never read code judge whether the project an AI
built for them is well organized, and what to do if it is not. You collect facts with a
script, learn the project's needs from the user, judge with a fixed checklist, and write
a report. You do not change code.

Announce at the start: "I'll use the understand-your-project skill: collect facts, ask
you a few questions about the project, then write a report."

## Step 1: Collect facts

Run from the project root the user wants analyzed:

```bash
python3 <this skill's directory>/scripts/collect_facts.py <project_root>
```

Save the JSON output; every later step reads from it.

- If the script exits non-zero, show the user the `error:` line from stderr and stop.
  Do not count files by hand instead. Without reliable facts there is no report.
- If `scale.out_of_scope` is true, tell the user now that the project exceeds this
  version's per-file limit and that you will review top-level structure only.
- If `project_type.languages` contains neither `javascript`, `typescript` nor `python`,
  tell the user this version covers JS/TS and Python and proceed with the generic
  checklist only.

## Step 2: Understand the needs

Follow `references/interview.md` exactly: read the docs listed in `facts.docs`, present
a draft understanding, then ask the four questions one at a time. Build the
requirements profile and state it back. If the user declines, use the default profile
and remember to mark the report.

## Step 3: Judge

Open `references/checklist.md`. Go through all 16 items in order. For each, look up the
evidence field in the JSON, apply the threshold, assign the base severity, then apply
the tier adjustment rules with the profile. Keep a list of findings with ID, severity,
and the exact evidence values.

Then open `references/reference-architectures.md`, pick the template by its matching
rule, and note which template (or none) applies.

## Step 4: Write the report

Follow `references/report-template.md`. Write `ARCHITECTURE_REVIEW.md` at the project
root in the user's conversation language. Then reply in chat with at most five
sentences: the verdict, the single most important finding, and the report path.

## Step 5: Stop

Do not modify, move, or delete any project file other than writing the report. Every
fix in Section 5 is a task the user may hand to an agent later; that is their decision.

## Rules that always apply

- Evidence or nothing. A finding without a path or number from the JSON is deleted.
- No invented paths. If you cannot find it in the JSON, it does not exist.
- Plain words. Explain a technical term in parentheses the first time it appears.
- One interview question per message.
- The script counts; you judge. Never re-derive counts by reading files yourself.
- Report language follows the user; item IDs (A1, B2...) stay as they are.
- Secrets: the JSON gives positions only. Never open those lines and never quote them.
````

- [ ] **Step 2: Validate frontmatter and paths**

Run:
```bash
head -4 understand-your-project/SKILL.md
ls understand-your-project/references understand-your-project/scripts
```
Expected: frontmatter with `name: understand-your-project`; the four reference files and `collect_facts.py` exist, matching every path SKILL.md mentions.

- [ ] **Step 3: Commit**

```bash
git add understand-your-project/SKILL.md
git commit -m "feat(skill): add SKILL.md entry point

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 16: EVALS.md, README and a manual end-to-end run

**Files:**
- Create: `understand-your-project/EVALS.md`
- Create: `README.md` (repo root)

**Interfaces:**
- Consumes: the three fixtures and checklist IDs.
- Produces: expected findings per fixture for future regression checks; install instructions.

- [ ] **Step 1: Write EVALS.md**

`understand-your-project/EVALS.md`:

````markdown
# Manual evaluation

Run the skill on each fixture with the default profile (`small_group`, `iterating`,
no pain points) and compare the findings in `ARCHITECTURE_REVIEW.md` against the table.
Re-run after any change to `SKILL.md`, `references/checklist.md` or the script.

How to run: in a Claude Code session, `cd` into the fixture and say
"analyze my project structure". Answer the interview with: Q2=B, Q3=B, Q4=D.

| Fixture | Must be reported | Must NOT be reported | Expected verdict |
|---|---|---|---|
| `tests/fixtures/clean-next` | (nothing) | A1 A2 B1 B2 C1 D1 D2 D3 D4 | Healthy |
| `tests/fixtures/monolith-py` | A1 (must_fix, 700+ lines), A2 or A3 (main.py mixes network and data), D1, D2 (must_fix, main.py:6), D3, D4 | B1, C1 | Needs a proper tidy-up |
| `tests/fixtures/cyclic-node` | B1 (must_fix, handlers.js <-> routes.js), B2 (legacy.js), D1, D4 | A1, A2, D2 | Needs a proper tidy-up |

Also check for every run:
- Every path in the report exists in the fixture.
- No secret value appears anywhere in the report.
- Section 5 has one entry per finding and each has a paste-ready task.
- The report is in the language you spoke to the agent in.

Record results here with the date:

| Date | Fixture | Pass | Notes |
|---|---|---|---|
````

- [ ] **Step 2: Write the root README**

`README.md`:

````markdown
# UnderstandYourProject

A Claude Code skill that explains your project's code structure in plain language,
judges it against what your project actually needs, and tells you exactly what to fix.
Built for people who let AI write their code and want to know whether it is a solid
foundation or a growing mess.

## Install

Copy the skill into your Claude Code skills directory:

```bash
cp -r understand-your-project ~/.claude/skills/understand-your-project
```

Requires Python 3.8 or newer. No packages to install.

## Use

Open Claude Code in your project and say:

> analyze my project structure

The agent runs the fact collector, asks you four short questions about the project,
and writes `ARCHITECTURE_REVIEW.md` in your project root. It never changes your code.

Supports JavaScript / TypeScript and Python projects up to about 800 source files.

## Develop

```bash
python3 -m unittest discover -s understand-your-project/tests -v
python3 understand-your-project/scripts/collect_facts.py path/to/any/project
```

Design: `docs/superpowers/specs/2026-09-30-understand-your-project-design.md`.
Manual evaluation: `understand-your-project/EVALS.md`.
````

- [ ] **Step 3: Run the full suite one last time**

Run: `python3 -m unittest discover -s understand-your-project/tests -v`
Expected: all tests OK, zero failures.

- [ ] **Step 4: Manual end-to-end run on one fixture**

Install the skill locally (`cp -r understand-your-project ~/.claude/skills/understand-your-project`), open a Claude Code session in `understand-your-project/tests/fixtures/monolith-py`, say "analyze my project structure", answer Q2=B, Q3=B, Q4=D, and compare the produced `ARCHITECTURE_REVIEW.md` with the `monolith-py` row in EVALS.md. Record the result in the EVALS.md table. Delete the generated `ARCHITECTURE_REVIEW.md` from the fixture afterwards so it is not committed.

- [ ] **Step 5: Commit**

```bash
git add understand-your-project/EVALS.md README.md
git commit -m "docs: add manual evals and README

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
