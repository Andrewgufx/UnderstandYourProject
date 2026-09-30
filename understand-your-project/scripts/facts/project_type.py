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
