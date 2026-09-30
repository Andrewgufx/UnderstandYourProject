"""Import extraction, resolution and dependency graph."""
from __future__ import annotations

import json
import posixpath
import re
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .project_type import load_package_json
from .walk import SourceFile, is_test_path, iter_named_files

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


_CONFIG_NAMES = ("tsconfig.json", "jsconfig.json")
_MAX_CONFIG_DEPTH = 5

# (dir_prefix, aliases, base_url): dir_prefix is the config's directory relative to root
# ("" for root); alias targets are already joined with dir_prefix and baseUrl.
AliasConfig = Tuple[str, Dict[str, str], Optional[str]]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _config_file(target: Path) -> Optional[Path]:
    """An `extends` or `references` target: a file, a file named without `.json`, or a
    directory holding a tsconfig.json."""
    if target.is_dir():
        candidate = target / "tsconfig.json"
        return candidate if candidate.is_file() else None
    if target.is_file():
        return target
    if not target.name:
        return None
    with_json = target.with_name(target.name + ".json")
    return with_json if with_json.is_file() else None


def _load_options(path: Path, root: Path, depth: int, seen: FrozenSet[Path]):
    """(paths, base_url, referenced config files) for one config, following `extends`.

    The child's `paths` / `baseUrl` override the parent's. Anything of the wrong type is ignored."""
    try:
        key = path.resolve()
    except OSError:
        return None, None, []
    if depth > _MAX_CONFIG_DEPTH or key in seen or not _inside(path, root):
        return None, None, []
    seen = seen | {key}
    try:
        data = _lenient_json(path.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        data = None
    if data is None:
        return None, None, []
    paths: Optional[dict] = None
    base_url: Optional[str] = None
    extends = data.get("extends")
    if isinstance(extends, str) and extends:
        parent = _config_file(path.parent / extends)
        if parent is not None:
            paths, base_url, _ = _load_options(parent, root, depth + 1, seen)
    options = data.get("compilerOptions")
    if isinstance(options, dict):
        if isinstance(options.get("paths"), dict):
            paths = options["paths"]
        if isinstance(options.get("baseUrl"), str):
            base_url = options["baseUrl"]
    references: List[Path] = []
    raw_refs = data.get("references")
    if isinstance(raw_refs, list):
        for ref in raw_refs:
            if isinstance(ref, dict) and isinstance(ref.get("path"), str) and ref["path"]:
                target = _config_file(path.parent / ref["path"])
                if target is not None:
                    references.append(target)
    return paths, base_url, references


def _aliases_from(dir_prefix: str, base_url: Optional[str], paths: Optional[dict]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    if not isinstance(paths, dict):
        return aliases
    for alias, targets in paths.items():
        if not isinstance(alias, str) or not alias.endswith("*") or not alias[:-1]:
            continue
        if not isinstance(targets, list) or not targets or not isinstance(targets[0], str):
            continue
        target = targets[0]
        if not target.endswith("*"):
            continue
        joined = posixpath.normpath(posixpath.join(dir_prefix or ".", base_url or ".", target[:-1]))
        if joined == ".":
            joined = ""
        aliases[alias[:-1]] = (joined + "/") if joined and not joined.endswith("/") else joined
    return aliases


def load_alias_configs(root: Path) -> List[AliasConfig]:
    """Every non-ignored tsconfig.json / jsconfig.json (tsconfig wins in the same directory),
    with `extends` merged and `references` folded into the referencing config's directory."""
    by_dir: Dict[str, Path] = {}
    for path in iter_named_files(root, _CONFIG_NAMES):
        rel_dir = path.parent.relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        if rel_dir not in by_dir or path.name == "tsconfig.json":
            by_dir[rel_dir] = path
    configs: List[AliasConfig] = []
    for dir_prefix in sorted(by_dir):
        path = by_dir[dir_prefix]
        paths, base_url, refs = _load_options(path, root, 0, frozenset())
        aliases = _aliases_from(dir_prefix, base_url, paths)
        visited = {path.resolve()}
        pending = [(ref, 1) for ref in refs]
        while pending:
            ref, depth = pending.pop(0)
            ref_key = ref.resolve()
            if depth > _MAX_CONFIG_DEPTH or ref_key in visited:
                continue
            visited.add(ref_key)
            ref_paths, ref_base, ref_refs = _load_options(ref, root, 0, frozenset())
            for alias, target in _aliases_from(dir_prefix, ref_base, ref_paths).items():
                aliases.setdefault(alias, target)
            if base_url is None and ref_base is not None:
                base_url = ref_base
            pending.extend((nxt, depth + 1) for nxt in ref_refs)
        configs.append((dir_prefix, aliases, base_url))
    return configs


def load_path_aliases(root: Path) -> Dict[str, str]:
    """Aliases of the root config only (kept for callers that need just those)."""
    for dir_prefix, aliases, _ in load_alias_configs(root):
        if dir_prefix == "":
            return aliases
    return {}


def _config_for(path: str, configs: List[AliasConfig]) -> Optional[AliasConfig]:
    """The config whose directory is the longest prefix of `path` (configs sorted longest first)."""
    for config in configs:
        if config[0] == "" or path.startswith(config[0] + "/"):
            return config
    return None


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


def _resolve_js(spec: str, from_path: str, known: Set[str], aliases: Dict[str, str],
                base_dir: Optional[str] = None) -> Optional[str]:
    bases: List[str] = []
    if spec.startswith("."):
        bases.append(posixpath.normpath(posixpath.join(posixpath.dirname(from_path), spec)))
    else:
        for prefix in sorted(aliases, key=len, reverse=True):
            if spec.startswith(prefix):
                bases.append(posixpath.normpath(aliases[prefix] + spec[len(prefix):]))
                break
        if base_dir is not None:
            bases.append(posixpath.normpath(posixpath.join(base_dir, spec)))
    for base in bases:
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
                   aliases: Dict[str, str], py_roots: List[str],
                   base_dir: Optional[str] = None) -> Optional[str]:
    """`base_dir` is the root-relative baseUrl directory tried for bare JS imports after aliases."""
    if language == "python":
        return _resolve_py(spec, from_path, known, py_roots)
    return _resolve_js(spec, from_path, known, aliases, base_dir)


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


def _looks_local_py(spec: str, top_names: Set[str]) -> bool:
    if spec.startswith("."):
        return True
    return spec.split(".")[0] in top_names


# Extensions of non-code files that bundlers import (styles, data, images, fonts, media,
# other component formats). An unresolved import with one of these is not counted.
_ASSET_EXTS = {
    "css", "scss", "sass", "less", "json", "svg", "png", "jpg", "jpeg", "gif", "webp", "ico",
    "avif", "woff", "woff2", "ttf", "otf", "mp3", "mp4", "wav", "webm", "txt", "md", "html",
    "yaml", "yml", "graphql", "gql", "wasm", "vue", "svelte", "astro",
}
_LOCAL_BARE_PREFIXES = ("@/", "~/", "#")
_MAIN_GUARD = re.compile(r"""if\s+__name__\s*==\s*['"]__main__['"]""")


def _is_asset_spec(spec: str) -> bool:
    return posixpath.splitext(posixpath.basename(spec))[1][1:].lower() in _ASSET_EXTS


def _local_dir_names(known: Set[str]) -> Set[str]:
    """Top-level directory names under root and under `src/` that hold source files."""
    names: Set[str] = set()
    for path in known:
        parts = path.split("/")
        if len(parts) > 1:
            names.add(parts[0])
        if parts[0] == "src" and len(parts) > 2:
            names.add(parts[1])
    return names


def _counts_as_unresolved_js(spec: str, local_dirs: Set[str]) -> bool:
    if _is_asset_spec(spec):
        return False
    if spec.startswith(".") or spec.startswith(_LOCAL_BARE_PREFIXES):
        return True
    return spec.split("/")[0] in local_dirs


def _declared_entries(root: Path) -> Set[str]:
    """Paths named by the root package.json `main` or `bin`, normalized."""
    data = load_package_json(root)
    if data is None:
        return set()
    values: List[str] = []
    for key in ("main", "bin"):
        value = data.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            values.extend(v for v in value.values() if isinstance(v, str))
    return {posixpath.normpath(v.replace("\\", "/")) for v in values if v}


def _script_entries(source_files: List[SourceFile]) -> Set[str]:
    """Python files that run as scripts (`if __name__ == "__main__"`)."""
    return {
        f.path for f in source_files
        if f.language == "python" and "__main__" in f.read_text() and _MAIN_GUARD.search(f.read_text())
    }


def build_dependency(source_files: List[SourceFile], root: Path) -> Dict:
    known = {f.path for f in source_files}
    configs = sorted(load_alias_configs(root), key=lambda c: (-len(c[0]), c[0]))
    py_roots = _python_roots(known)
    top_names = {p.split("/")[0].split(".")[0] for p in known}
    local_dirs = _local_dir_names(known)
    graph: Dict[str, Set[str]] = {f.path: set() for f in source_files}
    unresolved = 0
    for f in source_files:
        aliases: Dict[str, str] = {}
        base_dir: Optional[str] = None
        if f.language != "python":
            config = _config_for(f.path, configs)
            if config is not None:
                aliases = config[1]
                if config[2] is not None:
                    base_dir = posixpath.normpath(posixpath.join(config[0] or ".", config[2]))
                    base_dir = "" if base_dir == "." else base_dir
        for spec in extract_import_specs(f.read_text(), f.language):
            target = resolve_import(spec, f.path, f.language, known, aliases, py_roots, base_dir)
            if target is None:
                if f.language == "python":
                    unresolved += _looks_local_py(spec, top_names)
                elif _counts_as_unresolved_js(spec, local_dirs):
                    unresolved += 1
                continue
            if target != f.path:
                graph[f.path].add(target)
    in_degree = {path: 0 for path in graph}
    imported_by = {path: 0 for path in graph}  # importers that are not test files
    for source, targets in graph.items():
        source_is_test = is_test_path(source)
        for target in targets:
            in_degree[target] += 1
            if not source_is_test:
                imported_by[target] += 1
    edges = [{"from": src, "to": dst} for src in sorted(graph) for dst in sorted(graph[src])]
    most_imported = [
        {"path": path, "imported_by": count}
        for path, count in sorted(imported_by.items(), key=lambda kv: (-kv[1], kv[0]))
        if count > 0
    ][:10]
    entries = _declared_entries(root) | _script_entries(source_files)
    orphans = sorted(
        p for p, count in in_degree.items()
        if count == 0 and not is_entry_file(p) and p not in entries
    )
    return {
        "edge_count": len(edges),
        "most_imported": most_imported,
        "cycles": find_cycles(graph),
        "orphans": orphans,
        "unresolved_imports": unresolved,
        "edges": edges,
    }
