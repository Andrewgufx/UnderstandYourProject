"""Assemble all fact categories into one JSON-serializable dict."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from .hygiene import find_docs, hygiene
from .imports import build_dependency
from .project_type import detect_project_type
from .signals import layer_mixing, naming_styles, repeated_function_names, similar_filenames
from .structure import build_tree, largest_files, scale
from .walk import walk_project


def collect(root: Path) -> Dict:
    source_files, total_files = walk_project(root)
    return {
        "root": str(root),
        "project_type": detect_project_type(root, source_files),
        "scale": scale(source_files, total_files),
        "tree": build_tree(source_files),
        "largest_files": largest_files(source_files),
        "dependency": build_dependency(source_files, root),
        "layer_mixing": layer_mixing(source_files),
        "duplication": {
            "similar_filenames": similar_filenames(source_files),
            "repeated_function_names": repeated_function_names(source_files),
        },
        "naming": naming_styles(source_files),
        "hygiene": hygiene(root, source_files),
        "docs": find_docs(root),
    }
