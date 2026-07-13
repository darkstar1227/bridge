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
