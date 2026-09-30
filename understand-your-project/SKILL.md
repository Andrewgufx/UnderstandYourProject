---
name: understand-your-project
description: Analyze a project's code architecture, judge it against what the project actually needs, and write a plain-language report with concrete fixes. Use when the user asks whether their project structure or architecture is good, wants to understand how their code is organized, asks if their code is a mess (屎山), or says things like "analyze my project structure", "review my architecture", "understand my project", "is my code structure ok".
---

# Understand Your Project

You are helping someone who may have never read code judge whether the project an AI
built for them is well organized, and what to do if it is not. You collect facts with a
script, learn the project's needs from the user, judge with a fixed checklist, and write
a report. You do not change code.

Announce at the start: "I'll use the understand-your-project skill: collect facts, ask
you a few questions about the project, then write a report."

## Step 1: Collect facts

Run from the project root the user wants analyzed:

```bash
python3 <this skill's directory>/scripts/collect_facts.py <project_root>
```

Keep the JSON in your context or in a scratch directory outside the project; never
write it into the project. Every later step reads from it.

- If the script exits non-zero, show the user the `error:` line from stderr and stop.
  Do not count files by hand instead. Without reliable facts there is no report.
- If `scale.out_of_scope` is true, tell the user now that the project exceeds this
  version's per-file limit and that you will review top-level structure only.
- If `project_type.languages` contains none of `javascript`, `typescript`, `python`,
  tell the user this version covers JS/TS and Python, evaluate only D1 to D4 and E1
  (see the last section of `references/checklist.md`), and skip the reference
  architecture.

## Step 2: Understand the needs

Follow `references/interview.md` exactly: read the docs listed in `facts.docs`, present
a draft understanding, then ask the four questions one at a time. Build the
requirements profile and state it back. If the user declines, use the default profile
and remember to mark the report.

## Step 3: Judge

Open `references/checklist.md`. Go through all 16 items in order. For each, look up the
evidence field in the JSON, apply the threshold, assign the base severity, then apply
the tier adjustment rules with the profile. Keep a list of findings with ID, severity,
and the exact evidence values.

Then open `references/reference-architectures.md`, pick the template by its matching
rule, and note which template (or none) applies.

## Step 4: Write the report

Follow `references/report-template.md`. Write `ARCHITECTURE_REVIEW.md` at the project
root in the user's conversation language. Then reply in chat with at most five
sentences: the verdict, the single most important finding, and the report path.

## Step 5: Stop

Do not modify, move, or delete any project file other than writing the report. Every
fix in Section 5 is a task the user may hand to an agent later; that is their decision.

## Rules that always apply

- Evidence or nothing. A finding without a path or number from the JSON is deleted.
- Evidence paths come from the JSON only. Any path you propose that does not exist
  yet carries the suffix ` (proposed)`.
- Plain words. Explain a technical term in parentheses the first time it appears.
- One interview question per message.
- The script counts; you judge. Never re-derive counts by reading files yourself.
- Report language follows the user; item IDs (A1, B2...) stay as they are.
- Secrets: the JSON gives positions only. Never open those lines and never quote them.
