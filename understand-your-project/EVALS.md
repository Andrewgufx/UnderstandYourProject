# Manual evaluation

Run the skill on each fixture with the default profile (`small_group`, `iterating`,
no pain points) and compare the findings in `ARCHITECTURE_REVIEW.md` against the table.
Re-run after any change to `SKILL.md`, `references/checklist.md` or the script.

How to run: in a Claude Code session, `cd` into the fixture and say
"analyze my project structure". Answer the interview with: Q1 = confirm the draft,
Q2=B, Q3=B, Q4=D. Run on a copy of the fixture outside the repo so the report does not
land in the tracked tree.

| Fixture | Must be reported | Must NOT be reported | Expected verdict |
|---|---|---|---|
| `tests/fixtures/clean-next` | (nothing) | A1 A2 B1 B2 C1 D1 D2 D3 D4 | Healthy |
| `tests/fixtures/monolith-py` | A1 (should_fix, 700+ lines), A2 (main.py mixes network and data), D1, D2 (must_fix, main.py:6), D3, D4 | B1, C1 | Needs a proper tidy-up |
| `tests/fixtures/cyclic-node` | B1 (must_fix, handlers.js <-> routes.js), B2 (legacy.js), D1, D3, D4 | A1, A2, D2 | Needs a proper tidy-up |

Also check for every run:
- Every path in the report exists in the fixture.
- No secret value appears anywhere in the report.
- Section 5 has one entry per must_fix/should_fix finding and each has a paste-ready task.
- The report is in the language you spoke to the agent in.

Record results here with the date:

| Date | Fixture | Pass | Notes |
|---|---|---|---|
| 2026-09-30 | monolith-py | fail | Verdict correct (Needs a proper tidy-up). Missing: A2/A3 (checklist cannot fire: layer_mixing has no `ui` category and `main.py` matches no A3 path keyword), D3 (checklist requires non-empty `config_files`, which is empty). A1 reported as should_fix, not must_fix: 709 lines is in the checklist's 501-1000 should_fix band. D1, D2 (must_fix, main.py:6), D4 present; no B1/C1. |
| 2026-09-30 | clean-next | pass | Zero findings, verdict Healthy, T1 matched. Section 4 has only "no findings" lines; Section 5 has no fix entries and an empty target structure. |
| 2026-09-30 | monolith-py | pass | Second run after the fix wave. D2 must_fix (main.py:6); A1 should_fix (709 lines); A2 should_fix (network + data); D1, D3 should_fix; D4 note. No B1/C1. T3 matched. Verdict Needs a proper tidy-up. main.py could not be opened (it is in suspected_secrets), so the A1/A2 fix tasks cannot name routes. |
| 2026-09-30 | cyclic-node | pass | B1 must_fix (src/handlers.js <-> src/routes.js); D1, D3 should_fix; B2 note (src/legacy.js); D4 note. No A1/A2/D2. T2 matched. Verdict Needs a proper tidy-up. B3 ignored both handlers.js edges because T2's layer order has no `handlers`. |
| 2026-09-30 | oversize (synthetic) | pass | 850 one-line files + express. out_of_scope true, announced before the interview; only D1-D4 and E1 evaluated: D1, D3 should_fix, D4 note. Header Scope line, verdict sentence says hygiene and top-level structure only, Section 4 has "Not checked in this version". Verdict Healthy, which reads oddly for an unanalyzed project. |
| 2026-09-30 | unresolved (synthetic) | pass | 3 TS files with `@/` imports, no tsconfig. unresolved_imports 5 vs edge_count 0 (100%). B2 note (all 3 files orphans) marked "needs confirmation", reason stated once at top of Section 4; D1, D3 should_fix; D4 note. No template matched (said in Sections 2 and 5). Verdict Healthy. |
