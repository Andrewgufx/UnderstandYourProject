# Report template

File: `ARCHITECTURE_REVIEW.md` at the project root. Overwrite if present. Write in the
user's conversation language. Translate every heading below; keep the order and the
item IDs (A1, B2...) untouched.

Writing rules:
- No jargon. If a technical word is unavoidable, explain it in parentheses the first time.
- Every finding cites paths and numbers from the facts JSON. No "it feels messy".
- Every path cited as evidence must appear in the JSON. Paths that do not exist yet
  (in fixes and in the target structure) are always written with the suffix
  ` (proposed)`.
- Section 2 is for a reader who has never opened the code. Write it like you are
  showing someone around a house.
- After writing the file, summarize in chat in at most five sentences and give the path.

## Header

```
# Architecture review: <project name from package.json / pyproject / directory name>
Generated: <YYYY-MM-DD>
<If interview skipped: "Assumptions: judged using default profile (small group, actively iterating) because the interview was skipped.">
<If out_of_scope: "Scope: this project exceeds the per-file analysis limit; only top-level structure was reviewed.">
```

## Section 1: One-line verdict

Check in this order and stop at the first match:
1. **Needs a proper tidy-up** when there is at least one `must_fix`, or more than 5 `should_fix`.
2. **Healthy** when there are zero `must_fix` and at most 2 `should_fix`.
3. **A few things to fix** otherwise.

Follow with one sentence saying why, naming the biggest item.

## Section 2: What your project looks like today

- Two to four sentences: what kind of project (template name in plain words), how many
  files and lines, what the main folders are for.
- An ASCII tree from `facts.tree` limited to depth 3, one short comment per directory:

```
src/                 118 files   everything the app is made of
  app/                30 files   the screens users see
  components/         41 files   reusable pieces of screens
  lib/                12 files   helpers with no UI
```

If `facts.tree` is empty (all source files sit in the project root), list the entries
of `facts.largest_files` instead of drawing a tree.

## Section 3: What we assumed about your needs

Restate the requirements profile: purpose, who uses it, where it is going, what hurts.
Ask the reader to correct anything wrong, because every judgment below depends on it.

## Section 4: What we found

Group by severity in this order: must_fix, should_fix, note. Within each severity group, items raised by the user's pain points come first, then by ID. Each finding uses exactly this
shape:

```
### <ID>. <Name in plain words>
- **What it is:** one or two sentences.
- **Evidence:** `path` (N lines), `path:line`, counts. Copied from the JSON.
- **Why it matters for you:** tie to the profile (e.g. "since other people will edit this code...").
- **If ignored:** one sentence.
```

If a dimension has no findings, say so in one line ("No dependency problems found.").
If B items are marked "needs confirmation" because of unresolved imports, say so once
at the top of the section.

## Section 5: What to do about it

One entry per finding, ordered by benefit high and risk low first. Shape:

```
### Fix for <ID>: <short title>
- **Scope:** which files or folders change.
- **Risk:** low / medium / high, with one reason.
- **Effort:** small (under an hour) / medium (an afternoon) / large (a day or more).
- **Task for your agent:** a self-contained paragraph the user can paste into a new
  session. Names the files, the target layout, and what must keep working.
```

If a template matched, end with "Suggested target structure": an ASCII tree containing
only the parts that change, each annotated with the ID that motivates it.

Close with one line: this report does not change any code; pick a fix and hand its task
to your agent when ready.
