#!/usr/bin/env python3
"""Copy the understand-your-project skill to where an agent looks for skills."""
import argparse
import shutil
import sys
from pathlib import Path

SKILL = "understand-your-project"
SOURCE = Path(__file__).resolve().parent / SKILL
# What the skill needs at run time; tests and eval notes stay in the repository.
RUNTIME = ("SKILL.md", "references", "scripts")
# Codex, Cursor and Gemini CLI all read the shared .agents/skills directory.
SKILL_DIRS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "cursor": ".agents/skills",
    "gemini": ".agents/skills",
}


def install(base: Path, skills_dir: str) -> Path:
    dest = base / skills_dir / SKILL
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in RUNTIME:
        src = SOURCE / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dest / name)
    return dest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=sorted(SKILL_DIRS) + ["all"],
                        help="which agent to install for")
    parser.add_argument("--project", action="store_true",
                        help="install into the current directory instead of your home directory")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    base = Path.cwd() if args.project else args.home
    agents = sorted(SKILL_DIRS) if args.agent == "all" else [args.agent]
    for skills_dir in sorted({SKILL_DIRS[agent] for agent in agents}):
        print("installed: %s" % install(base, skills_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
