# Reference architectures

Use these to draw the "suggested target structure" in the report. Rules:

1. Pick the template by the rule in each heading. If none matches, skip the target
   structure entirely and say so in the report.
2. Only include directories that relate to a finding in the report. Do not ask the
   user to rearrange parts that are already fine.
3. Every added or moved directory in the target structure must be annotated with the
   checklist item ID that motivates it.
4. Layer order is listed low to high; checklist B3 treats an import from a lower
   layer to a higher one as inverted.

## T1. Next.js / React front-end app
Matches when `frameworks` contains `next` or `react` and no back-end framework
(`express`, `fastify`, `nest`, `koa`, `hono`, `fastapi`, `django`, `flask`).

```
src/
  app/            routes and pages only; each file wires a screen together
  features/       one folder per user-facing feature: its components, hooks, logic
    <feature>/
      components/
      hooks/
      api.ts      calls to the backend for this feature
  shared/         reused by several features
    components/   generic UI (Button, Modal)
    hooks/
    lib/          pure helpers, no React
  config/         environment reading, constants
```
Skip when small: `features/` is unnecessary under about 15 components; keep
`components/` and `lib/` flat until then.
Layer order: `shared/lib` < `config` < `shared/components`, `shared/hooks` < `features` < `app`.

## T2. Node back-end API
Matches when `frameworks` contains any of `express fastify nest koa hono`.

```
src/
  routes/         HTTP wiring: parse request, call a service, send response
  services/       business rules; no HTTP objects in here
  db/             database access: queries, models, migrations
  lib/            pure helpers
  config/         environment reading
  server.ts       creates the app and starts listening
```
Skip when small: under about 5 routes, `services/` may be one file.
Layer order: `lib` < `config` < `db` < `services` < `routes` < `server`.

## T3. Python back-end API
Matches when `frameworks` contains any of `fastapi django flask`.

```
app/
  api/            route handlers (FastAPI routers, Flask blueprints, Django views)
  services/       business rules
  models/         database models and schemas
  db/             session, connection, migrations
  core/           settings, logging, shared helpers
  main.py         builds the app
tests/
```
Django note: keep Django's per-app layout (`<app>/models.py`, `views.py`, `urls.py`);
map `services/` to a `services.py` inside each app.
Skip when small: under about 5 endpoints, `services/` and `api/` may each be one file.
Layer order: `core` < `db` < `models` < `services` < `api` < `main`.

## T4. Python scripts or data tool
Matches when `languages` is only `python` and no web framework is present.

```
<package_name>/
  __init__.py
  cli.py          argument parsing and entry point
  core.py         the actual work, importable and testable
  io.py           reading and writing files, APIs
  config.py
scripts/          one-off scripts that import the package
tests/
```
Skip when small: a single-purpose script under about 200 lines can stay one file.
Layer order: `config` < `io` < `core` < `cli` < `scripts`.

## T5. Full-stack single repo
Matches when both a front-end template (T1) and a back-end template (T2 or T3) match,
or `monorepo` is true.

```
apps/
  web/            front-end, laid out per T1
  api/            back-end, laid out per T2 or T3
packages/         code shared by both (types, validation)
```
Skip when small: without a build tool that understands workspaces, `frontend/` and
`backend/` as two top-level folders is enough.
Layer order: `packages` < `apps/api` < `apps/web`.
