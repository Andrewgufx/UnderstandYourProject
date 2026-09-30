"""Engineering hygiene facts: tests, env files, lint/format config, secrets, docs."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, List

from .project_type import find_manifests
from .walk import SourceFile, is_test_path, walk_tree

_SECRET_PATTERNS = [
    re.compile(r"""(?i)(api[_-]?key|secret|token|password|passwd)\w*['"]?\s*[:=]\s*['"](?!https?://)[^'"\s${}]{16,}['"]"""),
    re.compile(r"""['"](sk-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})['"]"""),
]
_CONFIG_STEM = re.compile(r"(^|[_\-.])(config|settings|constants|env)([_\-.]|$)", re.IGNORECASE)
_TOOL_CONFIG = re.compile(r"^[\w\-]+\.config\.[cm]?[jt]s$")
_DOC_KEYWORDS = re.compile(r"(prd|spec|requirements|design)", re.IGNORECASE)
_DOC_EXCLUDE = {"CHANGELOG.md", "LICENSE.md", "ARCHITECTURE_REVIEW.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"}
_ENV_TEMPLATES = {".env.example", ".env.sample", ".env.template"}
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
    docs: List[str] = []
    for _, rel_dir, filenames in walk_tree(root):
        depth = 0 if rel_dir == "" else rel_dir.count("/") + 1
        for name in filenames:
            if not name.lower().endswith(".md") or name in _DOC_EXCLUDE:
                continue
            rel = name if rel_dir == "" else rel_dir + "/" + name
            upper = name.upper()
            if depth == 0 and (upper.startswith("README") or name in ("CLAUDE.md", "AGENTS.md")):
                docs.append(rel)
            elif rel.startswith("docs/"):
                docs.append(rel)
            elif depth <= 3 and _DOC_KEYWORDS.search(name):
                docs.append(rel)
    return sorted(docs)


def _gitignore_patterns(root: Path) -> List[str]:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return []
    patterns = []
    for raw in _read(gitignore).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.lstrip("/")
        if line and "/" not in line:
            patterns.append(line)
    return patterns


def committed_env_files(root: Path) -> List[str]:
    """Names of root `.env` / `.env.*` files that are not templates and not matched by a
    root .gitignore line (`.env`, `.env*`, `.env.*`, `*.env`, ...). Names only, never contents."""
    patterns = _gitignore_patterns(root)
    found = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return []
    for path in entries:
        name = path.name
        if not (name == ".env" or name.startswith(".env.")) or name in _ENV_TEMPLATES:
            continue
        if not path.is_file():
            continue
        if any(name == p or fnmatch.fnmatchcase(name, p) for p in patterns):
            continue
        found.append(name)
    return found


def hygiene(root: Path, source_files: List[SourceFile]) -> Dict:
    config_dirs = sorted({root} | {m.parent for m in find_manifests(root)}, key=str)
    pyproject = "\n".join(_read(d / "pyproject.toml") for d in config_dirs if (d / "pyproject.toml").is_file())
    setup_cfg = "\n".join(_read(d / "setup.cfg") for d in config_dirs if (d / "setup.cfg").is_file())
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
        "has_env_example": any((root / n).is_file() for n in sorted(_ENV_TEMPLATES)),
        "has_gitignore": (root / ".gitignore").is_file(),
        "has_lint_config": any(_any_glob(d, _LINT_GLOBS) for d in config_dirs) or "[tool.ruff]" in pyproject or "[flake8]" in setup_cfg,
        "has_format_config": any(_any_glob(d, _FORMAT_GLOBS) for d in config_dirs) or "[tool.black]" in pyproject or "[tool.ruff.format]" in pyproject,
        "suspected_secrets": suspected_secrets(source_files),
        "config_files": config_files,
    }
