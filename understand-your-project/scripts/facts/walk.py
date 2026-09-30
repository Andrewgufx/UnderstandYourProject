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
