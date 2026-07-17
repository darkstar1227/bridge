---
name: superpowers-pipeline
description: A lighter orchestrator than full-pipeline — chains only the core Superpowers loop (writing-plans, subagent-driven-development, finishing-a-development-branch) without gstack's office-hours/autoplan or the autoresearch experiment steps, for when a spec already exists or gstack-level planning isn't wanted. Still judges at two checkpoints whether the change touches database schema and invokes supabase:supabase-postgres-best-practices if so. Use when the user wants "just the superpowers flow", already has a spec/plan and wants straight to implementation, or explicitly says they don't need the gstack review layers or autoresearch for this task.
triggers:
  - just the superpowers pipeline
  - superpowers only flow
  - skip gstack go straight to implementation
  - writing plans to finishing branch
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - AskUserQuestion
  - Agent
---

# Bridge: Superpowers-Only Pipeline Orchestrator

**Announce at start:** "I'm using the bridge:superpowers-pipeline skill to run just the core Superpowers loop, checking for database changes along the way."

## Purpose

This is `full-pipeline` minus the gstack planning layer (`/office-hours`, `/autoplan`) and minus the `autoresearch-plan`/`autoresearch-impl` experiment loops. Use it when a spec already exists (the user has a plan doc, or wants to hand Claude a spec directly) and the extra review/experimentation layers aren't wanted for this task. Same sequencer rule as `full-pipeline`: this skill does no work itself, it invokes the real skills in order and carries output forward.

If partway through the user decides they actually want the gstack review layer or an autoresearch comparison after all, don't try to bolt it on ad hoc — stop and suggest switching to `bridge:full-pipeline` instead, since it already has those steps wired in correctly.

## Step 1 — Confirm there's a spec to work from

Unlike `full-pipeline`, there's no `/office-hours` or `/autoplan` step generating one. Check for an existing plan/spec file (same search order as `gstack-to-plan` Step 1: explicit path arg → `docs/plan.md` → `docs/spec.md` → most recently modified `.md` under `docs/`). If nothing is found, ask the user directly for the spec, or for the requirements to write one from — don't invent scope.

## Sequence

1. **`superpowers:writing-plans`** — turn the spec into an execution-level implementation plan.
2. **Database checkpoint A** — see below, run against the plan produced in step 1.
3. **`superpowers:subagent-driven-development`** — execute the plan's tasks. If the user wants OpenCode as the implementer instead of a Claude subagent, use `bridge:opencode-subagent-driven-development` here instead — same review gates either way.
4. **Database checkpoint B** — see below, run against the actual diff produced in step 3.
5. **`superpowers:finishing-a-development-branch`** — decide merge/PR/cleanup once implementation and reviews are done.

## Database checkpoint (runs at steps 2 and 4)

Same judgment as `full-pipeline`'s checkpoint — don't invoke the review skill reflexively, only when there's an actual signal:

- At the plan checkpoint (step 2): does the plan mention new tables, migrations, indexes, RLS policies, foreign keys, or other schema changes?
- At the implementation checkpoint (step 4): does `git diff --stat` against the files subagent-driven-development touched show migration files (`supabase/migrations/*.sql`), schema definition files, or ORM model files mapping to database tables?

If either signal is present, invoke `supabase:supabase-postgres-best-practices` before continuing to the next step. If not, note briefly that no schema changes were detected and move on.
