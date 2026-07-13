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
