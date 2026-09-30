# UnderstandYourProject

A Claude Code skill that explains your project's code structure in plain language,
judges it against what your project actually needs, and tells you exactly what to fix.
Built for people who let AI write their code and want to know whether it is a solid
foundation or a growing mess.

## Install

Copy the skill into your Claude Code skills directory:

```bash
rm -rf ~/.claude/skills/understand-your-project && cp -R understand-your-project ~/.claude/skills/understand-your-project
```

Requires Python 3.8 or newer. No packages to install.

## Use

Open Claude Code in your project and say:

> analyze my project structure

The agent runs the fact collector, asks you four short questions about the project,
and writes `ARCHITECTURE_REVIEW.md` in your project root. It never changes your code.

Supports JavaScript / TypeScript and Python projects up to about 800 source files.

## Develop

```bash
python3 -m unittest discover -s understand-your-project/tests -v
python3 understand-your-project/scripts/collect_facts.py path/to/any/project
```

Design: `docs/superpowers/specs/2026-09-30-understand-your-project-design.md`.
Manual evaluation: `understand-your-project/EVALS.md`.
