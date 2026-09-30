# UnderstandYourProject

An agent skill that explains your project's code structure in plain language,
judges it against what your project actually needs, and tells you exactly what to fix.
Built for people who let AI write their code and want to know whether it is a solid
foundation or a growing mess.

It follows the open [Agent Skills](https://agentskills.io) format, so the same skill
works in Claude Code, Codex, Cursor and Gemini CLI.

## Install

Clone this repository, then run the installer for the agent you use:

```bash
python3 install.py --agent claude
```

| Agent | `--agent` | Installed to |
|---|---|---|
| Claude Code | `claude` | `~/.claude/skills/understand-your-project` |
| Codex | `codex` | `~/.agents/skills/understand-your-project` |
| Cursor | `cursor` | `~/.agents/skills/understand-your-project` |
| Gemini CLI | `gemini` | `~/.agents/skills/understand-your-project` |
| All of the above | `all` | both directories |

Add `--project` to install into the current project (`.claude/skills` or
`.agents/skills`) instead of your home directory. Running the installer again replaces
the previous copy. Restart the agent afterwards so it picks up the skill.

Cursor also reads `~/.claude/skills`. If you only use Cursor, `--agent cursor` is
enough; `--agent all` may show the skill twice there.

Requires Python 3.8 or newer. No packages to install.

## Use

Open the agent in your project and say:

> analyze my project structure

Every agent picks the skill from that request. To call it by name instead:

| Agent | Explicit call |
|---|---|
| Claude Code | `/understand-your-project` |
| Codex | `$understand-your-project` |
| Cursor | type `/` in Agent chat and pick `understand-your-project` |
| Gemini CLI | ask for it by name; approve the activation prompt |

The agent runs the fact collector, asks you four short questions about the project,
and writes `ARCHITECTURE_REVIEW.md` in your project root. It never changes your code.

Supports JavaScript / TypeScript and Python projects up to about 800 source files.

## Develop

```bash
python3 -m unittest discover -s understand-your-project/tests -v
python3 understand-your-project/scripts/collect_facts.py path/to/any/project
```

Manual evaluation: `understand-your-project/EVALS.md`.
