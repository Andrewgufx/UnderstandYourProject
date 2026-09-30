"""Assemble all fact categories into one JSON-serializable dict."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from .hygiene import committed_env_files, find_docs, hygiene
from .imports import build_dependency
from .project_type import detect_project_type
from .signals import layer_mixing, naming_styles, repeated_function_names, similar_filenames
from .structure import build_tree, largest_files, scale
from .walk import walk_project


def collect(root: Path) -> Dict:
    source_files, total_files = walk_project(root)
    scale_facts = scale(source_files, total_files)
    if scale_facts["out_of_scope"]:
        # Too big for per-file analysis: skip the import graph and content scans.
        dependency = {
            "edge_count": 0, "most_imported": [], "cycles": [], "orphans": [],
            "unresolved_imports": 0, "edges": [], "skipped": "out_of_scope",
        }
        mixing = []
        duplication = {"similar_filenames": [], "repeated_function_names": [], "skipped": "out_of_scope"}
    else:
        dependency = build_dependency(source_files, root)
        mixing = layer_mixing(source_files)
        duplication = {
            "similar_filenames": similar_filenames(source_files),
            "repeated_function_names": repeated_function_names(source_files),
        }
    hygiene_facts = hygiene(root, source_files)
    hygiene_facts["committed_env_files"] = committed_env_files(root)
    return {
        "root": str(root),
        "project_type": detect_project_type(root, source_files),
        "scale": scale_facts,
        "tree": build_tree(source_files),
        "largest_files": largest_files(source_files),
        "dependency": dependency,
        "layer_mixing": mixing,
        "duplication": duplication,
        "naming": naming_styles(source_files),
        "hygiene": hygiene_facts,
        "docs": find_docs(root),
    }
