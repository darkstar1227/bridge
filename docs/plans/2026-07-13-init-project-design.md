# Design: `bridge:init-project` skill

_Date: 2026-07-13_

## Purpose

A self-detecting skill that initializes a brand-new project or audits/corrects
an existing one against Justin's standard conventions, then writes those
conventions into the target project's `CLAUDE.md`. One skill covers both
"fresh project" and "existing project checkup" — it detects which applies.

## Trigger phrases

「初始化專案」「setup my project」「check my project setup」「幫我體檢專案設定」

## Scope detection

Runs against the current working directory (target project, not the `bridge`
repo itself). Each module below is independently optional — absence of its
marker file means the module is skipped entirely, no forced setup of
irrelevant tech.

| Module | Detected by |
|---|---|
| Python | `pyproject.toml` exists, or `*.py` files present |
| Docker | `Dockerfile` / `docker-compose*.yml` present, or user confirms they want it |
| Supabase | `supabase/` directory or `SUPABASE_*` env vars present, or user confirms |
| Git/Env (always runs) | any git repo |

## Module behaviors

### Python
- No `pyproject.toml` → `uv init`
- Check `[tool.ruff]` config enables PEP8 rule groups (`E`, `W`); write default
  ruff config if missing
- Check `.pre-commit-config.yaml` has a ruff hook; create it + prompt
  `pre-commit install` if missing
- Install a `.git/hooks/commit-msg` hook: on `feat:`/`fix:` commit messages,
  auto patch-bump the `version` field in `pyproject.toml` and amend it into
  the commit

### Docker
- If no compose file, ask which profile set: `dev/prod` or
  `dev/staging/prod` (project-dependent, always ask — no default)
- Ensure stateful services (DB, Redis, queues) are separate Compose services
  from the app layer, gated by `profiles:` so app-only commands never touch
  them
- Generate a `Makefile` where `make dev` / `make prod` run
  `up -d --no-deps --build app` — never recreates db/redis

### Supabase
- Check `supabase` CLI is installed (`supabase --version`)
- Check `supabase/` is initialized (`supabase init` if not)
- Document in CLAUDE.md: schema/DB changes always go through Supabase
  migrations, never manual DB edits

### Git / Env (always runs)
- Confirm `.env` is in `.gitignore`
- Scan code for env vars in use; sync `.env.example` to match
- Document (not enforce) Conventional Commits and `type/short-desc` branch
  naming in the CLAUDE.md conventions block

## Folder structure module

Applies mainstream, per-ecosystem conventions — no custom template:

- **Python**: src-layout (`src/<package>/`, `tests/`)
- **Docker**: `docker/` holds Dockerfile + per-profile compose overrides;
  root keeps base `docker-compose.yml` + `docker-compose.dev.yml` /
  `docker-compose.prod.yml`
- **Supabase**: untouched, uses whatever `supabase init` produces
  (`supabase/migrations/`, `supabase/config.toml`)

For existing projects that don't match: skill only ever proposes a **move
list** (source → destination, plus every import/reference that needs
updating, found via grep). Never auto-moves. Waits for explicit confirmation,
then executes via `git mv` so history is preserved.

## CLAUDE.md handling

1. Read the target project's current `CLAUDE.md` (empty if none exists)
2. Build a conventions block from whichever modules were detected/run
3. Write/replace only the content between
   `<!-- bridge:conventions:start -->` and `<!-- bridge:conventions:end -->`
   — everything else in the file is left untouched
4. After writing, automatically invoke `claude-md-management:claude-md-improver`
   as a **post-hoc quality review only** (no second auto-write) — its
   findings are appended to the report for Justin to act on manually if
   desired

## Output

`docs/init-project-report-YYYY-MM-DD.md` containing:
- Modules detected and what each did
- Pending decisions (folder move list awaiting confirmation, profile-set
  choice, etc.)
- claude-md-improver's post-hoc quality review of the resulting CLAUDE.md

## Non-goals

- Does not enforce branch naming (documents only)
- Does not auto-bump versions outside the commit-msg hook trigger
- Does not move files without explicit per-item confirmation
