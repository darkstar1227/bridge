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
