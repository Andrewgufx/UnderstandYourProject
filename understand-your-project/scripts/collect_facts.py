#!/usr/bin/env python3
"""Collect structural facts about a JS/TS or Python project and print them as JSON.

Usage: python3 collect_facts.py [--compact] <project_path>

Standard library only. Never judges; only counts and locates.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from facts.collect import collect  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_path", help="path to the project root")
    parser.add_argument("--compact", action="store_true", help="single-line JSON")
    args = parser.parse_args(argv)
    root = Path(args.project_path).expanduser().resolve()
    if not root.is_dir():
        print("error: %s is not a directory" % root, file=sys.stderr)
        return 1
    try:
        facts = collect(root)
    except Exception as exc:  # noqa: BLE001 - the agent needs the reason, whatever it is
        print("error: failed to collect facts: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    if args.compact:
        print(json.dumps(facts, ensure_ascii=False))
    else:
        print(json.dumps(facts, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
