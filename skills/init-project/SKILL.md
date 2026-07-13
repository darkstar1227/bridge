---
name: init-project
description: Detect a target project's stack (Python/uv, Node/TypeScript, Docker, Supabase, Git) and initialize or audit it against standard conventions — ruff/PEP8 or eslint/prettier, docker-compose profiles, Supabase migrations, .env hygiene, commit/branch conventions, folder layout — then write the result into the target repo's CLAUDE.md.
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
test -f package.json && echo "NODE: package.json found"
find . -maxdepth 2 \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" | head -1 | grep -q . && echo "NODE: .ts/.tsx files found"
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

4. Version bumping is handled by the shared hook in Step 4 — do not install a Python-specific version-bump hook here.

## Step 3 — Node/TypeScript Module (if active)

1. No `package.json` → ask the user which package manager (`npm`/`pnpm`/`yarn`), then run the matching init command (e.g. `pnpm init`).
2. No `tsconfig.json` → create one with a conservative strict baseline:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

3. Check for an ESLint config (`eslint.config.js`/`.eslintrc*`). If missing, create a flat config using `typescript-eslint`:

```javascript
// eslint.config.js
import tseslint from "typescript-eslint";

export default tseslint.config(
  ...tseslint.configs.recommended
);
```

Note in the skill's recommendation that the user still needs to `npm install -D typescript-eslint eslint` (or the `pnpm`/`yarn` equivalent) — do not run installs for them.

4. Check for a Prettier config (`.prettierrc*` or a `prettier` key in `package.json`). If missing, add a minimal `.prettierrc.json`:

```json
{
  "semi": true,
  "singleQuote": false
}
```

5. Check `.pre-commit-config.yaml` (if the project already uses pre-commit for Python) or a `lint-staged`/`husky` setup for a lint hook. If neither exists, suggest `husky` + `lint-staged` running `eslint --fix` and `prettier --write` on staged files, but only wire it up if the user confirms — installing git hook tooling via npm packages is not something to do silently.

## Step 4 — Version Bump Hook (if Python or Node module active)

Install a single `commit-msg` hook at `.git/hooks/commit-msg` (mode `755`) that bumps whichever manifest(s) exist. If missing, create it:

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
    if [ -f package.json ]; then
      CURRENT=$(grep -m1 '"version"' package.json | sed -E 's/.*"version": *"([^"]+)".*/\1/')
      if [ -n "$CURRENT" ]; then
        IFS='.' read -r MAJ MIN PATCH <<EOF
$CURRENT
EOF
        NEW="$MAJ.$MIN.$((PATCH + 1))"
        sed -i.bak -E "s/\"version\": *\"$CURRENT\"/\"version\": \"$NEW\"/" package.json
        rm -f package.json.bak
        git add package.json
      fi
    fi
    ;;
esac
```

If both manifests exist, the hook bumps both independently — this only matters for monorepo-style projects that pair a Python service with a TS package; single-language projects just get the one branch that applies.

## Step 5 — Docker Module (if active)

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

## Step 6 — Supabase Module (if active)

1. Check the CLI is available: `supabase --version`. If missing, tell the user to install it (`brew install supabase/tap/supabase`) — do not install it for them.
2. Check `supabase/config.toml` exists. If not, run `supabase init`.
3. Do not modify anything under `supabase/migrations/` — this skill only confirms the directory exists.
4. Record for the CLAUDE.md conventions block: "Schema/DB changes go through Supabase migrations (`supabase migration new <name>`), never manual DB edits."

## Step 7 — Git/Env Module (always runs)

1. Confirm `.gitignore` contains `.env` (add the line if missing; create `.gitignore` if it doesn't exist).
2. Scan for environment variable usage:

```bash
grep -rhoE '(os\.environ\[.[A-Z_]+.\]|os\.getenv\(.[A-Z_]+.|process\.env\.[A-Z_]+)' --include="*.py" --include="*.ts" --include="*.js" . 2>/dev/null
```

Normalize the matches to bare variable names, then diff against keys already in `.env.example` (create the file if missing). Add any missing keys with an empty value and a `# TODO: set value` comment. Never overwrite existing values in `.env.example`.
3. Record for the CLAUDE.md conventions block: Conventional Commits (`feat:`/`fix:`/`chore:`/etc.) and `type/short-desc` branch naming — documented as convention, not enforced by the skill.

## Step 8 — Folder Structure Module (if Python, Node, or Docker modules are active)

Compare current layout against mainstream per-ecosystem conventions:

| Stack | Convention |
|---|---|
| Python | src-layout: `src/<package>/`, `tests/` |
| Node/TypeScript | `src/` for source, compiled output in `dist/` (matches the `tsconfig.json` from Step 3), tests in `tests/` or colocated `*.test.ts` |
| Docker | `docker/` for Dockerfile + compose overrides (see Step 5) |
| Supabase | untouched — whatever `supabase init` produces |

If the current layout doesn't match:

1. Build a move list: `source path -> destination path`.
2. For each Python or TypeScript/JavaScript file being moved, `grep -rn` the whole repo for references to its module path — `import`/`from` for Python, `import ... from`/`require(...)` for TS/JS — and list those as "needs reference update" alongside the move.
3. Present the full move list (paths + reference updates) to the user and stop. Do NOT move anything until the user confirms.
4. On confirmation, execute moves with `git mv` (preserves history) one at a time, then apply the corresponding import-path edits, then verify nothing else references the old path (`grep -rn "<old_module_path>"` returns empty).

## Step 9 — Write CLAUDE.md Conventions Block

1. Read the target project's `CLAUDE.md` (treat as empty if it doesn't exist).
2. Build a conventions block containing only sections for modules that were actually active this run — omit sections for skipped modules entirely.
3. Write/replace only the region between these markers, leaving everything else in the file untouched:

```markdown
<!-- bridge:conventions:start -->
## Conventions (managed by bridge:init-project)

<module sections here — Python/ruff, Node/TypeScript (eslint/prettier), Docker profiles, Supabase, Git/Env>

_Last updated: <today's date> by bridge:init-project_
<!-- bridge:conventions:end -->
```

If the markers don't exist yet, append the whole block to the end of the file. If they exist, replace only the content between them.

4. After writing, invoke `claude-md-management:claude-md-improver` against the target `CLAUDE.md` as a **read-only, post-hoc quality pass** — do not let it perform a second auto-write. Capture its quality report for the output report in Step 10.

## Step 10 — Write the Report

Save to: `docs/init-project-report-YYYY-MM-DD.md` (today's date, in the target project).

```markdown
# Init Project Report — <date>

## Modules Detected
<list of active modules and why they were detected/confirmed>

## Actions Taken
<per module: what was created/modified, with file paths>

## Pending Decisions
<folder move list awaiting confirmation, profile-set choice if unresolved, anything else needing user input>

## CLAUDE.md Quality Review (via claude-md-improver)
<paste the improver's quality report verbatim>
```

Do not implement any application code as part of this skill — it only sets up tooling/config/docs.
