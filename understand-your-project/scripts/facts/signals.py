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
