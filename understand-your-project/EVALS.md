# Manual evaluation

Run the skill on each fixture with the default profile (`small_group`, `iterating`,
no pain points) and compare the findings in `ARCHITECTURE_REVIEW.md` against the table.
Re-run after any change to `SKILL.md`, `references/checklist.md` or the script.

How to run: in a Claude Code session, `cd` into the fixture and say
"analyze my project structure". Answer the interview with: Q2=B, Q3=B, Q4=D.

| Fixture | Must be reported | Must NOT be reported | Expected verdict |
|---|---|---|---|
| `tests/fixtures/clean-next` | (nothing) | A1 A2 B1 B2 C1 D1 D2 D3 D4 | Healthy |
| `tests/fixtures/monolith-py` | A1 (must_fix, 700+ lines), A2 or A3 (main.py mixes network and data), D1, D2 (must_fix, main.py:6), D3, D4 | B1, C1 | Needs a proper tidy-up |
| `tests/fixtures/cyclic-node` | B1 (must_fix, handlers.js <-> routes.js), B2 (legacy.js), D1, D4 | A1, A2, D2 | Needs a proper tidy-up |

Also check for every run:
- Every path in the report exists in the fixture.
- No secret value appears anywhere in the report.
- Section 5 has one entry per finding and each has a paste-ready task.
- The report is in the language you spoke to the agent in.

Record results here with the date:

| Date | Fixture | Pass | Notes |
|---|---|---|---|
