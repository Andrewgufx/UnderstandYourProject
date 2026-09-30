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
| 2026-09-30 | monolith-py | fail | Verdict correct (Needs a proper tidy-up). Missing: A2/A3 (checklist cannot fire: layer_mixing has no `ui` category and `main.py` matches no A3 path keyword), D3 (checklist requires non-empty `config_files`, which is empty). A1 reported as should_fix, not must_fix: 709 lines is in the checklist's 501-1000 should_fix band. D1, D2 (must_fix, main.py:6), D4 present; no B1/C1. |
| 2026-09-30 | clean-next | pass | Zero findings, verdict Healthy, T1 matched. Section 4 has only "no findings" lines; Section 5 has no fix entries and an empty target structure. |
