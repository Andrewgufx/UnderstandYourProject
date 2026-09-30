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
