# Architecture checklist

Sixteen items in five dimensions. For each item: read the evidence field in the facts
JSON, apply the threshold, assign the base severity, then apply the tier adjustments at
the end of this file. Every finding in the report must cite the concrete paths and
numbers from the JSON. Never report an item without evidence.

Severity levels:
- **must_fix**: will cause an incident or block development soon.
- **should_fix**: not painful today, will be within six months on the user's stated path.
- **note**: worth knowing; no action required.

Format of each item below: what it is (plain words) / evidence / threshold / base
severity / what happens if ignored / usual fix.

## A. Layers and responsibilities

### A1. Giant file
- **Plain words:** One file does far too many things. Nobody, human or AI, can hold it in their head.
- **Evidence:** `largest_files[].lines`
- **Threshold:** any file over 500 lines is reported.
- **Base severity:** should_fix for 501 to 1000 lines; must_fix over 1000 lines.
- **If ignored:** Every change touches the same file, merge conflicts and regressions pile up, AI edits get sloppy.
- **Usual fix:** Split by responsibility (routes, data access, business rules, UI) into separate files under a folder named after the feature.

### A2. One file mixes screens, network calls and database work
- **Plain words:** The same file does two or more of: drawing screens, calling the network, talking to the database.
- **Evidence:** `layer_mixing[]` (the script only lists files that hit two or more of `ui`, `network`, `data`; each entry's `categories` says which).
- **Threshold:** any entry.
- **Base severity:** should_fix.
- **If ignored:** You cannot change where data comes from without rewriting screens; testing the screen requires a live database.
- **Usual fix:** Split the file so that screen code, network calls and database access each live in their own module (`lib/` or `services/` for the last two).

### A3. Business logic lives in routes or pages
- **Plain words:** The rules of your app are written inside the request handlers or page files instead of a place of their own.
- **Evidence:** `largest_files[]` entries with a path segment (a directory name, or the file name without its extension) equal to one of `page pages route routes views api handlers`, and whose `lines` exceed 300. Match whole segments, not substrings: `src/api/users.ts` and `app/page.tsx` match; `src/apiClient.ts` and `rapid/x.py` do not.
- **Threshold:** any such file.
- **Base severity:** should_fix.
- **If ignored:** The same rule gets copied into the next route; fixing it once no longer fixes it everywhere.
- **Usual fix:** Extract the rules into plain functions in a `services/` or `domain/` folder; routes only parse input and call them.

### A4. One "god utils" file
- **Plain words:** A single helper file that almost everything depends on and that keeps growing.
- **Evidence:** `dependency.most_imported[]` and `largest_files[]`.
- **Threshold:** a file imported by more than 30% of `scale.source_files` and longer than 300 lines.
- **Base severity:** should_fix.
- **If ignored:** Any edit to it can break the whole app; it becomes the file nobody dares touch.
- **Usual fix:** Split it by topic (`date.ts`, `format.ts`, `validation.ts`) and update imports.

## B. Dependencies and coupling

### B1. Circular dependency
- **Plain words:** File A needs B and B needs A. Loading order becomes fragile and neither can be understood alone.
- **Evidence:** `dependency.cycles[]`.
- **Threshold:** non-empty.
- **Base severity:** must_fix.
- **If ignored:** Mysterious "undefined" errors, imports that work in one place and fail in another, impossible to extract either file.
- **Usual fix:** Move the shared piece both files need into a third file that neither imports from.

### B2. Orphan files and dead code
- **Plain words:** Files nothing uses any more.
- **Evidence:** `dependency.orphans[]`.
- **Threshold:** non-empty; more than 10 raises severity.
- **Base severity:** note; should_fix when over 10.
- **If ignored:** Readers and AI waste time on code that does nothing; old bugs get "fixed" in files that never run.
- **Usual fix:** Confirm each is unused, then delete it (git keeps history).

### B3. Dependency direction is inverted
- **Plain words:** Low-level helper code reaches up and imports from screens or routes.
- **Evidence:** `dependency.edges[]`. To find a file's layer, drop a leading `src/`, compare the file name without its extension, and scan the path segments left to right. At each position try the segment joined with the next one (`shared/lib`), then the segment alone. The first hit in the layer order is the file's layer. Files with no hit have no layer and their edges are ignored. Use the matched template's layer order from `reference-architectures.md`; if no template matched, use this generic order, low to high: `utils`/`lib`/`shared` < `services`/`db`/`models`/`data` < `components`/`hooks` < `pages`/`app`/`routes`/`api`/`views`. An edge whose `from` layer is lower than its `to` layer is inverted.
- **Threshold:** any inverted edge.
- **Base severity:** should_fix.
- **If ignored:** Nothing is reusable; the helper cannot be tested without the whole app.
- **Usual fix:** Pass the needed value in as a parameter instead of importing it from above.

## C. Duplication and consistency

### C1. Near-duplicate files
- **Plain words:** `utils.ts`, `utils2.ts` and `helpers.ts` all exist; nobody knows which is current.
- **Evidence:** `duplication.similar_filenames[]`.
- **Threshold:** non-empty.
- **Base severity:** should_fix.
- **If ignored:** Fixes land in one copy; the other copy keeps the bug.
- **Usual fix:** Merge into one file, delete the rest.

### C2. Same logic copied in several places
- **Plain words:** A function with the same name is defined in several files.
- **Evidence:** `duplication.repeated_function_names[]`.
- **Threshold:** non-empty; a name in more than 5 files raises severity.
- **Base severity:** note; should_fix when any name appears in over 5 files.
- **If ignored:** Behavior drifts between copies.
- **Usual fix:** Keep one definition in a shared module and import it.

### C3. Inconsistent naming
- **Plain words:** Some files are `userService.ts`, others `user_service.ts`, others `user-service.ts`.
- **Evidence:** `naming.file_case_styles`, `naming.dir_case_styles`.
- **Threshold:** within either map, the second most common style is over 20% of the total count, and the total classified count in that map is at least 10.
- **Base severity:** note.
- **If ignored:** Harder to find files; AI guesses wrong paths.
- **Usual fix:** Pick one convention per language (kebab-case for JS/TS files, snake_case for Python) and rename gradually.

## D. Engineering hygiene

### D1. No tests
- **Plain words:** Nothing automatically checks that the app still works after a change.
- **Evidence:** `hygiene.has_tests`.
- **Threshold:** `false`.
- **Base severity:** should_fix.
- **If ignored:** Every change is a gamble; AI cannot verify its own edits.
- **Usual fix:** Add one test file for the most important function, then grow from there.

### D2. Secrets hard-coded
- **Plain words:** A password, API key or token is written directly in the code.
- **Evidence:** `hygiene.suspected_secrets[]` (positions only) and `hygiene.committed_env_files[]` (root `.env` files that `.gitignore` does not exclude; names only).
- **Threshold:** either list is non-empty.
- **Base severity:** must_fix. Never lowered by any tier rule.
- **If ignored:** Anyone with the code, including public repos and AI logs, has your key.
- **Usual fix:** Move to environment variables, add `.env` to `.gitignore`, rotate the exposed key, and delete the committed `.env` from git history if it held real keys.

### D3. Missing `.env.example` or `.gitignore`
- **Plain words:** No template showing which settings the app needs, or no list of files git should ignore.
- **Evidence:** `hygiene.has_env_example`, `hygiene.has_gitignore`, `hygiene.config_files`, `hygiene.suspected_secrets`, `hygiene.committed_env_files`.
- **Threshold:** `has_gitignore` is `false`, or `has_env_example` is `false` and any of `config_files`, `suspected_secrets`, `committed_env_files` is non-empty.
- **Base severity:** should_fix.
- **If ignored:** New machines cannot run the app; secrets and build junk get committed.
- **Usual fix:** Add both files; list every required variable in `.env.example` with placeholder values.

### D4. No lint or format configuration
- **Plain words:** No tool enforces consistent style or catches obvious mistakes.
- **Evidence:** `hygiene.has_lint_config`, `hygiene.has_format_config`.
- **Threshold:** either is `false`.
- **Base severity:** note.
- **If ignored:** Style drifts, trivial bugs slip through.
- **Usual fix:** Add ESLint + Prettier (JS/TS) or Ruff (Python) with default config.

## E. Ability to evolve

### E1. Folders grouped by file type instead of feature
- **Plain words:** Everything is in `components/`, `utils/`, `hooks/`, `types/`; a single feature is scattered across all of them.
- **Evidence:** `tree[]` entries at depth 1 or 2 whose last path segment is one of `components utils hooks types helpers` and whose `files` exceed 20.
- **Threshold:** any such directory.
- **Base severity:** note.
- **If ignored:** Adding a feature means touching six folders; deleting one means hunting through all of them.
- **Usual fix:** Group by feature (`features/todos/`, `features/auth/`) with shared code in `shared/`.

### E2. Configuration and constants scattered
- **Plain words:** Settings live in several files in several places.
- **Evidence:** `hygiene.config_files[]`.
- **Threshold:** more than 3 files across more than one directory.
- **Base severity:** note.
- **If ignored:** Changing a setting requires finding every copy.
- **Usual fix:** One `config/` module that reads environment variables and exports typed values.

## Tier adjustment rules

Apply in this order. Each step moves severity by at most one level. Floor is `note`,
ceiling is `must_fix`. D2 is never lowered.

1. `scale_tier == personal`: lower every D and E item by one level, except D2.
2. `evolution_tier == collaborative`: raise C3, D1, E1 by one level.
3. `evolution_tier in (launching, collaborative)`: raise D1, D3 by one level.
4. `pain_points` contains `breaks_elsewhere`: raise every A and B item by one level.
5. `pain_points` contains `ai_struggles`: raise A1, A4, E1 by one level.
6. Final cap, applied after all of the above: if `evolution_tier == frozen`, set every E item to `note`.

Ordering, not severity: items touched by rules 4 or 5 are listed first within their severity group in the report.

## Out-of-scope projects

When `scale.out_of_scope` is true, evaluate only D1-D4 and E1 (top-level structure).
The script skips the import graph, layer mixing and duplication for these projects:
`dependency` and `duplication` carry `"skipped": "out_of_scope"` with empty lists, and
`layer_mixing` is empty. State in the report that per-file analysis was not performed.

## Unreliable dependency data

When `dependency.unresolved_imports` exceeds 30% of `dependency.edge_count` plus
`dependency.unresolved_imports`, mark every B item "needs confirmation" and say why. These items
still count toward the verdict at their assigned severity.

## Projects that are not JS/TS or Python

When `scale.source_files` is 0, there is nothing to judge: tell the user no supported
source files were found (notebooks are not analyzed), stop, and write no report.

Otherwise, when `project_type.languages` contains none of `javascript`, `typescript`,
`python`, evaluate only D3. State in the report that tests, secrets and lint could not
be checked for this language. No template applies; say in the report that this version
has reference architectures for JS/TS and Python only.
