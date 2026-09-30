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
    text = re.sub(
        r'("(?:\\.|[^"\\])*")|/\*.*?\*/|//[^\n]*',
        lambda m: m.group(1) or "",
        text,
        flags=re.DOTALL,
    )
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
