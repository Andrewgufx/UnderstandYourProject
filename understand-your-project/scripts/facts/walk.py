"""Walk a project directory and collect source files."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Set, Tuple

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


def _gitignore_lines(root: Path) -> List[str]:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return []
    lines = []
    for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.strip("/")
        if line and not any(ch in line for ch in "*?["):
            lines.append(line)
    return lines


def load_gitignore_paths(root: Path) -> Set[str]:
    """Directory paths (posix, relative to root) listed in .gitignore with slashes and no wildcards."""
    return {line for line in _gitignore_lines(root) if "/" in line}


def load_gitignore_dirs(root: Path) -> Set[str]:
    """Top-level directory names listed in .gitignore without wildcards or slashes."""
    return {line for line in _gitignore_lines(root) if "/" not in line}


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def ignored_dir_names(root: Path) -> Set[str]:
    """Directory names pruned everywhere: the built-in list plus plain .gitignore names."""
    return IGNORED_DIRS | load_gitignore_dirs(root)


def prune_dirs(dirnames: List[str], ignored: Set[str]) -> List[str]:
    """Keep directories that are not ignored and do not start with a dot, sorted."""
    return sorted(d for d in dirnames if d not in ignored and not d.startswith("."))


def walk_tree(root: Path) -> Iterator[Tuple[Path, str, List[str]]]:
    """Yield (dirpath, rel_dir, sorted filenames) for every non-ignored directory.

    Pruning applies the built-in names, plain .gitignore names, dot-directories, and
    slashed .gitignore paths such as `apps/desktop/target/` at exactly that path.
    `rel_dir` is "" for the root."""
    ignored = ignored_dir_names(root)
    ignored_paths = load_gitignore_paths(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        kept = prune_dirs(dirnames, ignored)
        if ignored_paths:
            kept = [d for d in kept if (rel_dir + "/" + d if rel_dir else d) not in ignored_paths]
        dirnames[:] = kept
        yield Path(dirpath), rel_dir, sorted(filenames)


def iter_named_files(root: Path, names: Iterable[str]) -> Iterator[Path]:
    """Yield every non-ignored file under root whose name is in `names`, in walk order."""
    wanted = set(names)
    for dirpath, _, filenames in walk_tree(root):
        for name in filenames:
            if name in wanted:
                yield dirpath / name


def walk_project(root: Path) -> Tuple[List[SourceFile], int]:
    """Return (source_files, total_file_count), pruning ignored directories.

    Minified files (`.min.` in the name) count toward the total but are not source files."""
    source_files: List[SourceFile] = []
    total = 0
    for dirpath, rel_dir, filenames in walk_tree(root):
        for name in filenames:
            path = dirpath / name
            total += 1
            language = SOURCE_EXTENSIONS.get(path.suffix)
            if language is None or ".min." in name:
                continue
            rel = (rel_dir + "/" + name) if rel_dir else name
            source_files.append(SourceFile(rel, path, language, count_lines(path)))
    return source_files, total
