"""Detect languages, frameworks, package managers and monorepo layout."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set

from .walk import SourceFile, iter_named_files

JS_PACKAGE_TO_FRAMEWORK = {
    "next": "next", "react": "react", "vue": "vue", "nuxt": "nuxt",
    "svelte": "svelte", "@angular/core": "angular", "express": "express",
    "fastify": "fastify", "@nestjs/core": "nest", "koa": "koa", "hono": "hono",
    "electron": "electron", "@remix-run/react": "remix", "astro": "astro",
}
PY_FRAMEWORKS = ["fastapi", "django", "flask", "streamlit", "typer", "click"]
PY_MANIFESTS = ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"]
MANIFEST_NAMES = ["package.json"] + PY_MANIFESTS
MANIFEST_MAX_DEPTH = 3


def find_manifests(root: Path) -> List[Path]:
    """Every package.json / Python manifest at directory depth <= 3, ignored dirs excluded."""
    found = []
    for path in iter_named_files(root, MANIFEST_NAMES):
        if len(path.relative_to(root).parts) - 1 <= MANIFEST_MAX_DEPTH:
            found.append(path)
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_package_json(root: Path) -> Optional[Dict]:
    """The root package.json as a dict, or None when it is missing, invalid or not an object."""
    manifest = root / "package.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


_PY_TABLE = re.compile(r"^\s*\[\s*([^\[\]]+?)\s*\]\s*(#.*)?$")
_PY_NAME = re.compile(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']")


def _pyproject_name(root: Path) -> Optional[str]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    table = None
    for line in _read(path).splitlines():
        header = _PY_TABLE.match(line)
        if header:
            table = header.group(1)
            continue
        if line.lstrip().startswith("[["):
            table = None
            continue
        if table in ("project", "tool.poetry"):
            match = _PY_NAME.match(line)
            if match:
                return match.group(1)
    return None


def _project_name(root: Path) -> str:
    data = load_package_json(root)
    if data is not None and isinstance(data.get("name"), str) and data["name"]:
        return data["name"]
    return _pyproject_name(root) or root.name


def _js_frameworks(directory: Path, root: Path, detected_from: List[str]) -> Set[str]:
    manifest = directory / "package.json"
    if not manifest.is_file():
        return set()
    data = load_package_json(directory)
    if data is None:
        return set()
    detected_from.append(manifest.relative_to(root).as_posix())
    deps: Set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key) or {}
        if isinstance(section, dict):
            deps |= set(section)
    return {fw for pkg, fw in JS_PACKAGE_TO_FRAMEWORK.items() if pkg in deps}


def _py_frameworks(directory: Path, root: Path, detected_from: List[str]) -> Set[str]:
    found: Set[str] = set()
    for name in PY_MANIFESTS:
        path = directory / name
        if not path.is_file():
            continue
        detected_from.append(path.relative_to(root).as_posix())
        text = _read(path).lower()
        for fw in PY_FRAMEWORKS:
            if re.search(r"(?<![\w-])" + re.escape(fw) + r"(?![\w-])", text):
                found.add(fw)
    return found


def _package_managers(directories: List[Path]) -> List[str]:
    managers: Set[str] = set()
    for d in directories:
        if (d / "package.json").is_file():
            if (d / "pnpm-lock.yaml").is_file():
                managers.add("pnpm")
            elif (d / "yarn.lock").is_file():
                managers.add("yarn")
            elif (d / "bun.lockb").is_file() or (d / "bun.lock").is_file():
                managers.add("bun")
            else:
                managers.add("npm")
        if (d / "requirements.txt").is_file() or (d / "pyproject.toml").is_file():
            managers.add("pip")
        pyproject = _read(d / "pyproject.toml") if (d / "pyproject.toml").is_file() else ""
        if (d / "poetry.lock").is_file() or "[tool.poetry]" in pyproject:
            managers.add("poetry")
        if (d / "uv.lock").is_file():
            managers.add("uv")
        if (d / "Pipfile").is_file():
            managers.add("pipenv")
    return sorted(managers)


def _is_monorepo(root: Path, manifest_dirs: List[Path]) -> bool:
    for name in ("pnpm-workspace.yaml", "lerna.json", "turbo.json"):
        if (root / name).is_file():
            return True
    data = load_package_json(root)
    if data is not None and "workspaces" in data:
        return True
    return len(manifest_dirs) > 1


def detect_project_type(root: Path, source_files: List[SourceFile]) -> Dict:
    lines_by_language: Counter = Counter()
    for f in source_files:
        lines_by_language[f.language] += f.lines
    languages = [lang for lang, _ in sorted(
        lines_by_language.items(), key=lambda kv: (-kv[1], kv[0]))]
    detected_from: List[str] = []
    manifest_dirs = sorted({m.parent for m in find_manifests(root)}, key=str)
    frameworks: Set[str] = set()
    for d in manifest_dirs:
        frameworks |= _js_frameworks(d, root, detected_from) | _py_frameworks(d, root, detected_from)
    return {
        "name": _project_name(root),
        "languages": languages,
        "frameworks": sorted(frameworks),
        "package_managers": _package_managers(manifest_dirs),
        "monorepo": _is_monorepo(root, manifest_dirs),
        "detected_from": sorted(detected_from),
    }
