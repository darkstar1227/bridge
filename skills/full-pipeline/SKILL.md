---
name: full-pipeline
description: Orchestrates the user's full end-to-end workflow in order — gstack office-hours, autoplan, autoresearch-plan, superpowers writing-plans and subagent-driven-development, autoresearch-impl, code-review, and qa — invoking each skill in sequence and handing its output forward as the next step's input. At two fixed checkpoints (after the plan is locked, and after implementation lands) it judges whether the change touches database schema and if so invokes supabase:supabase-postgres-best-practices before continuing. Use whenever the user wants to "run the whole pipeline", "go from idea to shipped", "do the full flow", or asks Claude Code to chain their office-hours → autoplan → superpowers → qa workflow automatically instead of invoking each skill by hand.
triggers:
  - run the full pipeline
  - full workflow from office hours to qa
  - chain the whole pipeline
  - go from idea to shipped
  - orchestrate the entire flow
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - AskUserQuestion
  - Agent
---

# Bridge: Full Pipeline Orchestrator

**Announce at start:** "I'm using the bridge:full-pipeline skill to run the workflow end-to-end, chaining each step's output into the next."

## Purpose

This skill doesn't do any of the work itself — it's a sequencer. Each numbered step below is a real skill invocation; this skill's only job is to run them in order, carry the right file/output forward as the next step's input, and stop to surface a decision back to the user whenever a step can't proceed without one (e.g. `autoresearch-plan` finding no real alternatives to compare, or a review step failing). Don't skip a step to save time, and don't silently substitute a different skill for the one named — if the user wants a different implementer or reviewer mid-run, that's a decision to surface, not one to make unilaterally.

Because every step runs in the same conversation, this pipeline accumulates context as it goes. For a long-running or multi-day pipeline, it's fine — expected, even — for the conversation to pause between steps and resume later; nothing here requires unattended execution.

## Sequence

1. **`/office-hours`** (gstack) — clarify the problem, constraints, and rough direction before any plan exists.
2. **`/autoplan`** (gstack) — CEO/design/eng triple review, produces a locked, reviewed plan.
3. **Database checkpoint A** — see "Database checkpoint" below, run against the plan from step 2.
4. **`bridge:autoresearch-plan`** — only if the locked plan contains more than one real candidate technical approach worth comparing; that skill's own Step 1 will tell you to skip if not, in which case move straight to step 5 and say so.
5. **`superpowers:writing-plans`** — feed it the plan from step 2 (with the winning approach from step 4 folded in as an Architecture Decision, if step 4 ran). If the user wants the gstack→Superpowers spec transform done explicitly rather than inline, use `bridge:gstack-to-plan` here instead and let it invoke `writing-plans` itself.
6. **`superpowers:subagent-driven-development`** — execute the written plan's tasks.
7. **`bridge:autoresearch-impl`** — only if there's a metric worth iterating against (ask if unclear rather than assuming every task warrants an iteration loop; a lot of implementation work doesn't need this step, and running it needlessly burns budget for no benefit).
8. **Database checkpoint B** — see "Database checkpoint" below, run against the actual diff produced by steps 6-7.
9. **`code-review`** / **`codex:review`** — standard diff review.
10. **`/qa`** (gstack) — end-to-end browser verification and regression check.

## Database checkpoint (runs at steps 3 and 8)

At each checkpoint, decide whether the change touches database schema before deciding to invoke `supabase:supabase-postgres-best-practices`. Signals to check for:

- At the plan checkpoint (step 3): does the plan's text mention new tables, migrations, indexes, RLS policies, foreign keys, or schema changes anywhere in scope/architecture sections?
- At the implementation checkpoint (step 8): does the actual diff touch migration files (e.g. `supabase/migrations/*.sql`), schema definition files (Prisma schema, SQL DDL), or ORM model files that map to database tables? A quick `git diff --stat` against the files changed in steps 6-7 is enough to check this.

If either signal is present, invoke `supabase:supabase-postgres-best-practices` before moving to the next step — at the plan checkpoint this catches a bad schema decision while it's still cheap to change; at the implementation checkpoint it reviews the actual SQL/migration that will ship. If neither signal is present, say so briefly and move on — don't invoke the skill on every run regardless of relevance, that trains the user to ignore the checkpoint.

## Stopping and resuming

If any step in the sequence itself stops to ask the user something (all of these skills do this by design — e.g. `autoresearch-plan`/`autoresearch-impl`'s scope/budget/metric questions), let it. This orchestrator doesn't pre-answer those on the user's behalf. Once the user answers, resume the sequence from wherever it paused.
