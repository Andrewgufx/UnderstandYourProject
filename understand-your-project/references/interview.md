# Requirements interview

Purpose: learn what the project is for and where it is going, so the checklist can
judge "good enough for this project" instead of "good in the abstract". Ask in the
user's conversation language. Ask ONE question per message and wait for the answer.

## Step 1: Draft from existing docs

Read every path listed in `facts.docs` (README, CLAUDE.md, AGENTS.md, docs/, PRD-like
files). Write a 2-4 sentence draft:

> From what I can see, this project is <what it does>, built with <frameworks>, and
> seems intended for <who>. Is that right?

If `facts.docs` is empty, base the draft on directory names, framework and largest
files, and open with "From the code alone, this looks like...".

## Step 2: Four questions, one at a time

**Q1. What is this project for?** Present the draft from Step 1 and ask the user to
confirm or correct it. Open answer.

**Q2. Who uses it?** Offer exactly these options:
- A. Only me
- B. A few people I know (family, friends, teammates)
- C. The public, or anyone who signs up

**Q3. Where is it going in the next six months?** Offer these options; more than one
may apply:
- A. Basically done, just keep it running
- B. I will keep adding features
- C. I plan to launch it properly or charge for it
- D. Other people will work on the code with me

**Q4. What hurts most right now?** Offer these options; more than one may apply:
- A. Changing one thing breaks something else
- B. The AI is getting worse at making changes to it
- C. It is slow
- D. Nothing really, I just want to understand it
- E. Something else (tell me)

## Step 3: Build the requirements profile

| Field | Value | Source |
|---|---|---|
| `purpose` | one sentence in the user's words | Q1 |
| `scale_tier` | `personal` (Q2=A), `small_group` (Q2=B), `public` (Q2=C) | Q2 |
| `evolution_tier` | `frozen` (A), `iterating` (B), `launching` (C), `collaborative` (D). If several chosen, take the heaviest: frozen < iterating < launching < collaborative | Q3 |
| `pain_points` | list of chosen labels: `breaks_elsewhere`, `ai_struggles`, `slow`, `none`, or free text | Q4 |

State the profile back to the user in one short paragraph before analysis begins.

## If the user declines or skips questions

If the whole interview is skipped, use `scale_tier = small_group`,
`evolution_tier = iterating`, `pain_points = []`, and `purpose` = the Step 1 draft
marked "(unconfirmed)". If only some questions are skipped, apply the default for
those fields only. Whenever any default is used, mark the report header with
"Assumptions: judged using default profile (small group, actively iterating) because
the interview was skipped or incomplete."
