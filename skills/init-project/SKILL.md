---
name: init-project
description: Detect a target project's stack (Python/uv, Docker, Supabase, Git) and initialize or audit it against standard conventions — ruff/PEP8, docker-compose profiles, Supabase migrations, .env hygiene, commit/branch conventions, folder layout — then write the result into the target repo's CLAUDE.md.
triggers:
  - initialize project
  - init project
  - setup my project
  - check my project setup
  - project checkup
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Bridge: Init Project

**Announce at start:** "I'm using the bridge:init-project skill to detect and set up this project's environment."

## Purpose

One skill for two situations: initializing a brand-new project's tooling, or auditing/correcting an existing one. It self-detects which applies — no need to tell it in advance.

## Step 1 — Detect Applicable Modules

Run against the current working directory (the target project):

```bash
test -f pyproject.toml && echo "PYTHON: pyproject.toml found"
find . -maxdepth 2 -name "*.py" | head -1 | grep -q . && echo "PYTHON: .py files found"
find . -maxdepth 1 -iname "Dockerfile" -o -maxdepth 1 -iname "docker-compose*.yml" | grep -q . && echo "DOCKER: compose/Dockerfile found"
test -d supabase && echo "SUPABASE: supabase/ found"
grep -rl "SUPABASE_" --include="*.env*" . 2>/dev/null | head -1 | grep -q . && echo "SUPABASE: env vars found"
git rev-parse --is-inside-work-tree 2>/dev/null && echo "GIT: repo confirmed"
```

For any module with no positive signal, ask the user a single yes/no question: "This project doesn't show signs of using <X>. Do you want it set up here?" Skip the module entirely on "no". The Git/Env module always runs — every project handled by this skill is expected to be a git repo.

Record which modules are active before continuing; every later step is gated by this list.

## Step 2 — Python Module (if active)

1. No `pyproject.toml` → run `uv init`.
2. Check for a `[tool.ruff]` table in `pyproject.toml` (or a `ruff.toml`/`.ruff.toml` file). If missing, add to `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I"]
```

3. Check for `.pre-commit-config.yaml` with a `ruff` hook. If missing, create it:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
      - id: ruff-format
```

Tell the user to run `pre-commit install` — do not run it for them (it mutates their local git hooks config).

4. Check for a version-bump `commit-msg` hook at `.git/hooks/commit-msg`. If missing, create it (mode `755`):

```bash
#!/bin/sh
MSG_FILE="$1"
FIRST_LINE=$(head -n1 "$MSG_FILE")
case "$FIRST_LINE" in
  feat:*|fix:*)
    if [ -f pyproject.toml ]; then
      CURRENT=$(grep -m1 '^version' pyproject.toml | sed -E 's/version *= *"([^"]+)"/\1/')
      if [ -n "$CURRENT" ]; then
        IFS='.' read -r MAJ MIN PATCH <<EOF
$CURRENT
EOF
        NEW="$MAJ.$MIN.$((PATCH + 1))"
        sed -i.bak -E "s/^version *= *\"$CURRENT\"/version = \"$NEW\"/" pyproject.toml
        rm -f pyproject.toml.bak
        git add pyproject.toml
      fi
    fi
    ;;
esac
```

## Step 3 — Docker Module (if active)

1. If no compose file exists, ask the user: "Which profile set does this project need — `dev/prod` or `dev/staging/prod`?" There is no default; always ask.
2. Lay out files under `docker/`:
   - `docker/Dockerfile`
   - `docker-compose.yml` (base: app + stateful services, no profiles)
   - `docker-compose.dev.yml` / `docker-compose.prod.yml` (and `.staging.yml` if chosen) — override files for the app service only
3. In the base compose file, put stateful services (db, redis, queue, etc.) under a `profiles: ["infra"]` key, separate from the app service. This means `docker compose up app` never touches them.
4. Generate/update `Makefile`:

```makefile
.PHONY: dev prod infra-up

infra-up:
	docker compose --profile infra up -d

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --no-deps --build app

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --build app
```

If a `Makefile` already exists, show the proposed `dev`/`prod`/`infra-up` targets as a diff and ask before merging — never blindly overwrite an existing Makefile.

## Step 4 — Supabase Module (if active)

1. Check the CLI is available: `supabase --version`. If missing, tell the user to install it (`brew install supabase/tap/supabase`) — do not install it for them.
2. Check `supabase/config.toml` exists. If not, run `supabase init`.
3. Do not modify anything under `supabase/migrations/` — this skill only confirms the directory exists.
4. Record for the CLAUDE.md conventions block: "Schema/DB changes go through Supabase migrations (`supabase migration new <name>`), never manual DB edits."

## Step 5 — Git/Env Module (always runs)

1. Confirm `.gitignore` contains `.env` (add the line if missing; create `.gitignore` if it doesn't exist).
2. Scan for environment variable usage:

```bash
grep -rhoE '(os\.environ\[.[A-Z_]+.\]|os\.getenv\(.[A-Z_]+.|process\.env\.[A-Z_]+)' --include="*.py" --include="*.ts" --include="*.js" . 2>/dev/null
```

Normalize the matches to bare variable names, then diff against keys already in `.env.example` (create the file if missing). Add any missing keys with an empty value and a `# TODO: set value` comment. Never overwrite existing values in `.env.example`.
3. Record for the CLAUDE.md conventions block: Conventional Commits (`feat:`/`fix:`/`chore:`/etc.) and `type/short-desc` branch naming — documented as convention, not enforced by the skill.

## Step 6 — Folder Structure Module (if Python or Docker modules are active)

Compare current layout against mainstream per-ecosystem conventions:

| Stack | Convention |
|---|---|
| Python | src-layout: `src/<package>/`, `tests/` |
| Docker | `docker/` for Dockerfile + compose overrides (see Step 3) |
| Supabase | untouched — whatever `supabase init` produces |

If the current layout doesn't match:

1. Build a move list: `source path -> destination path`.
2. For each Python file being moved, `grep -rn` the whole repo for `import`/`from` references to its module path and list those as "needs reference update" alongside the move.
3. Present the full move list (paths + reference updates) to the user and stop. Do NOT move anything until the user confirms.
4. On confirmation, execute moves with `git mv` (preserves history) one at a time, then apply the corresponding import-path edits, then verify nothing else references the old path (`grep -rn "<old_module_path>"` returns empty).
