"""Scale, directory tree and largest files."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from .walk import SourceFile

OUT_OF_SCOPE_FILES = 800
OUT_OF_SCOPE_LINES = 80000
LARGE_FILE_LINES = 300
MIN_LARGEST = 15


def scale(source_files: List[SourceFile], total_files: int) -> Dict:
    by_language: Counter = Counter()
    for f in source_files:
        by_language[f.language] += f.lines
    source_lines = sum(by_language.values())
    return {
        "total_files": total_files,
        "source_files": len(source_files),
        "source_lines": source_lines,
        "lines_by_language": dict(sorted(by_language.items())),
        "out_of_scope": len(source_files) > OUT_OF_SCOPE_FILES or source_lines > OUT_OF_SCOPE_LINES,
    }


def build_tree(source_files: List[SourceFile], max_depth: int = 4) -> List[Dict]:
    files: Dict[str, int] = defaultdict(int)
    lines: Dict[str, int] = defaultdict(int)
    for f in source_files:
        parts = f.path.split("/")[:-1]
        for depth in range(1, min(len(parts), max_depth) + 1):
            directory = "/".join(parts[:depth])
            files[directory] += 1
            lines[directory] += f.lines
    return [
        {"path": d, "depth": d.count("/") + 1, "files": files[d], "lines": lines[d]}
        for d in sorted(files)
    ]


def largest_files(source_files: List[SourceFile]) -> List[Dict]:
    ordered = sorted(source_files, key=lambda f: (-f.lines, f.path))
    selected = [f for f in ordered if f.lines > LARGE_FILE_LINES]
    if len(selected) < MIN_LARGEST:
        selected = ordered[:MIN_LARGEST]
    return [{"path": f.path, "lines": f.lines, "language": f.language} for f in selected]
