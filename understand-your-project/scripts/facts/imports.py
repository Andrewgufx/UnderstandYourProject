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
