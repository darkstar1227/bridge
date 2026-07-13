# bridge:init-project Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new `bridge:init-project` skill that detects a target project's stack (Python/uv, Docker, Supabase, Git) and either scaffolds fresh conventions or audits/corrects an existing project, writing the result into the target's `CLAUDE.md`.

**Architecture:** A single `SKILL.md` prompt file under `skills/init-project/`, following the same frontmatter + numbered-steps structure as `skills/gstack-to-plan/SKILL.md`. No code — this is a markdown instruction file that Claude Code executes directly. Verification is manual: run the skill's documented steps against a scratch fixture directory and confirm the described behavior/output.

**Tech Stack:** Markdown skill definitions (this repo has no build/runtime — see `CLAUDE.md`). Design source: `docs/plans/2026-07-13-init-project-design.md`.

---

### Task 1: Scaffold the skill directory and frontmatter

**Files:**
- Create: `skills/init-project/SKILL.md`

**Step 1: Create the directory and frontmatter block**

```markdown
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
```

**Step 2: Verify frontmatter is well-formed**

Run: `awk '/^---$/{c++} END{print c}' skills/init-project/SKILL.md`
Expected: `2` (opening and closing `---` delimiters)

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: scaffold bridge:init-project skill"
```

---

### Task 2: Write the detection step (Step 1)

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append the Purpose and detection logic**

```markdown
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
```

**Step 2: Verify the step renders correctly**

Run: `grep -c "^## Step" skills/init-project/SKILL.md`
Expected: `1` (only Step 1 exists so far)

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add module detection step to init-project skill"
```

---

### Task 3: Write the Python module (Step 2)

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append Step 2**

```markdown
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
```

**Step 2: Verify with a scratch fixture**

```bash
mkdir -p /tmp/init-project-fixture-py && cd /tmp/init-project-fixture-py
uv init --quiet
```
Expected: `pyproject.toml` exists with a `[project]` table.

Manually add the `[tool.ruff]` block per the skill instructions and confirm `cat pyproject.toml` shows it.

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add Python module (ruff/pre-commit/version-bump hook) to init-project skill"
```

---

### Task 4: Write the Docker module (Step 3)

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append Step 3**

```markdown
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
```

**Step 2: Verify**

Run: `grep -A2 "^dev:" skills/init-project/SKILL.md | head -5`
Expected: shows the `dev` target's `--no-deps` flag, confirming stateful services are excluded.

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add Docker profile module to init-project skill"
```

---

### Task 5: Write the Supabase module (Step 4)

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append Step 4**

```markdown
## Step 4 — Supabase Module (if active)

1. Check the CLI is available: `supabase --version`. If missing, tell the user to install it (`brew install supabase/tap/supabase`) — do not install it for them.
2. Check `supabase/config.toml` exists. If not, run `supabase init`.
3. Do not modify anything under `supabase/migrations/` — this skill only confirms the directory exists.
4. Record for the CLAUDE.md conventions block: "Schema/DB changes go through Supabase migrations (`supabase migration new <name>`), never manual DB edits."
```

**Step 2: Verify**

Run: `grep -c "supabase migration new" skills/init-project/SKILL.md`
Expected: `1`

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add Supabase module to init-project skill"
```

---

### Task 6: Write the Git/Env module and folder-structure module (Steps 5–6)

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append Step 5 (Git/Env, always runs)**

```markdown
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
```

**Step 2: Verify**

Run: `grep -c "git mv" skills/init-project/SKILL.md`
Expected: `1` or more.

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add Git/Env and folder-structure modules to init-project skill"
```

---

### Task 7: Write the CLAUDE.md write step and claude-md-improver handoff (Step 7)

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append Step 7**

```markdown
## Step 7 — Write CLAUDE.md Conventions Block

1. Read the target project's `CLAUDE.md` (treat as empty if it doesn't exist).
2. Build a conventions block containing only sections for modules that were actually active this run — omit sections for skipped modules entirely.
3. Write/replace only the region between these markers, leaving everything else in the file untouched:

```markdown
<!-- bridge:conventions:start -->
## Conventions (managed by bridge:init-project)

<module sections here — Python/ruff, Docker profiles, Supabase, Git/Env>

_Last updated: <today's date> by bridge:init-project_
<!-- bridge:conventions:end -->
```

If the markers don't exist yet, append the whole block to the end of the file. If they exist, replace only the content between them.

4. After writing, invoke `claude-md-management:claude-md-improver` against the target `CLAUDE.md` as a **read-only, post-hoc quality pass** — do not let it perform a second auto-write. Capture its quality report for the output report in Step 8.
```

**Step 2: Verify**

Run: `grep -c "bridge:conventions:start" skills/init-project/SKILL.md`
Expected: `1`

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add CLAUDE.md conventions-block writer and claude-md-improver handoff"
```

---

### Task 8: Write the report generation step (Step 8) and finalize skill doc

**Files:**
- Modify: `skills/init-project/SKILL.md`

**Step 1: Append Step 8**

```markdown
## Step 8 — Write the Report

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
```

**Step 2: Read the full file back and sanity-check structure**

Run: `grep "^## " skills/init-project/SKILL.md`
Expected: `Purpose`, `Step 1 — Detect Applicable Modules`, `Step 2 — Python Module (if active)`, `Step 3 — Docker Module (if active)`, `Step 4 — Supabase Module (if active)`, `Step 5 — Git/Env Module (always runs)`, `Step 6 — Folder Structure Module (if Python or Docker modules are active)`, `Step 7 — Write CLAUDE.md Conventions Block`, `Step 8 — Write the Report`

**Step 3: Commit**

```bash
git add skills/init-project/SKILL.md
git commit -m "feat: add report-generation step to init-project skill"
```

---

### Task 9: Bump plugin version and update README

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `README.md`

**Step 1: Bump version**

Read current version (`1.5.0`), bump minor (new skill = feature): set `"version": "1.6.0"` in `.claude-plugin/plugin.json`.

**Step 2: Add skill to README's skill list**

Read `README.md`, find the skill listing section, add a one-line entry for `init-project` matching the format of existing entries (e.g. `gstack-to-plan`).

**Step 3: Verify**

Run: `grep version .claude-plugin/plugin.json && grep init-project README.md`
Expected: shows `"version": "1.6.0"` and a README line mentioning `init-project`.

**Step 4: Commit**

```bash
git add .claude-plugin/plugin.json README.md
git commit -m "chore: bump plugin to 1.6.0 for init-project skill"
```

---

### Task 10: Manual smoke test against a scratch fixture project

**Files:**
- None (verification only, uses scratch directory)

**Step 1: Build a minimal fixture**

```bash
mkdir -p /private/tmp/claude-501/init-project-smoke/pkg
cd /private/tmp/claude-501/init-project-smoke
git init -q
printf 'print("hi")\n' > pkg/main.py
```

**Step 2: Manually walk the skill's steps against the fixture**

Follow `skills/init-project/SKILL.md` Steps 1–8 by hand against this fixture directory. Confirm:
- Step 1 detects Python (via `.py` files), correctly reports Docker/Supabase as inactive after a "no" answer
- Step 2 creates `pyproject.toml` with the ruff block and the commit-msg hook
- Step 5 creates `.gitignore` with `.env` and an empty `.env.example` (no env vars found, so it should stay effectively empty)
- Step 6 is skipped or proposes `src/pkg/` layout — confirm the move list is proposed, not auto-executed
- Step 7 writes a `<!-- bridge:conventions:start -->` block into a fresh `CLAUDE.md`
- Step 8 writes `docs/init-project-report-<date>.md` with all four expected sections

**Step 3: Clean up the fixture**

```bash
rm -rf /private/tmp/claude-501/init-project-smoke
```

No commit for this task — it's a manual verification pass, not a code change.
