---
type: Workflow Guide
title: Planning and pipeline workflows
description: "How Bridge turns reviewed ideas into executable plans and sequences full or Superpowers-only delivery flows with conditional research and database-review gates."
resource: skills/full-pipeline/SKILL.md
tags: [workflows, planning, gstack, superpowers, autoresearch]
---

# Planning and pipeline workflows

## Purpose and boundaries

The planning family bridges the gap between strategic review and execution, then sequences external skills without impersonating them. It is implemented through the [plugin and skill model](../architecture/plugin-and-skill-model.md): individual prompts define the durable contracts, while the orchestrators carry artifacts and decisions forward.

## From reviewed plan to execution-ready handoff

`bridge:gstack-to-plan` reads a source plan in a defined priority order: an explicit argument, conventional `docs/` or repository-root plan/spec names, then the most recent Markdown candidate. It extracts the goal, success criteria, scope and non-goals, user workflow, constraints, architecture decisions, risks, and implementation hints.

Before it writes anything, the skill requires a problem statement, scope boundary, technical constraint, and verification method. Missing material becomes an explicit assumption rather than an invented fact. It writes `docs/superpowers/input/gstack-handoff-YYYY-MM-DD-<feature-slug>.md`, then dispatches to `superpowers:writing-plans` and stops before implementation.

That handoff **depends on the authoring rules in** [the plugin and skill model](../architecture/plugin-and-skill-model.md): explicit assumptions, exact artifact paths, and verification-first requirements keep the strategic-to-execution transformation inspectable. Source: [`skills/gstack-to-plan/SKILL.md`](../../skills/gstack-to-plan/SKILL.md).

## Full pipeline

`bridge:full-pipeline` is the broad sequencer for an idea-to-QA flow:

1. gstack `/office-hours` clarifies the problem.
2. gstack `/autoplan` produces a reviewed plan.
3. **Database checkpoint A** detects proposed tables, migrations, indexes, RLS, foreign keys, or schema work; only then it calls `supabase:supabase-postgres-best-practices`.
4. `bridge:autoresearch-plan` runs only for genuine technical alternatives.
5. `superpowers:writing-plans` turns the selected direction into implementation tasks; `bridge:gstack-to-plan` is the explicit transform option.
6. `superpowers:subagent-driven-development` implements the plan.
7. `bridge:autoresearch-impl` runs only when a meaningful metric justifies iterative experimentation.
8. **Database checkpoint B** inspects the actual diff for migrations, DDL/schema, or ORM model changes and conditionally reruns the Supabase guidance.
9. Code review runs through `code-review` or `codex:review`.
10. gstack `/qa` performs end-to-end verification.

The full pipeline **can surface** [OpenCode delegation and evaluation](../opencode/delegation-and-evaluation.md) through the implementation layer, but it does not silently substitute an implementer or reviewer. It pauses wherever a downstream skill needs a user decision. Source: [`skills/full-pipeline/SKILL.md`](../../skills/full-pipeline/SKILL.md).

## Lean Superpowers pipeline

`bridge:superpowers-pipeline` removes gstack review and both autoresearch loops for work that already has a spec. It finds a spec using the same conventional search approach, stops if none exists, then runs:

1. `superpowers:writing-plans`
2. Database checkpoint A
3. `superpowers:subagent-driven-development`, optionally replaced with `bridge:opencode-subagent-driven-development` when the user explicitly selects OpenCode
4. Database checkpoint B
5. `superpowers:finishing-a-development-branch`

If the user later wants gstack review or comparative experimentation, the lean workflow directs them to the full pipeline rather than bolting new phases into the middle. This workflow therefore **selects OpenCode only through** [OpenCode delegation and evaluation](../opencode/delegation-and-evaluation.md)’s guarded wrapper, not the bare dispatcher. Source: [`skills/superpowers-pipeline/SKILL.md`](../../skills/superpowers-pipeline/SKILL.md).

## Autoresearch gates

The two autoresearch skills are opt-in decision loops, not a default tax on every change:

- `autoresearch-plan` compares two or more real technical alternatives under a pinned variation axis, budget, and directional metric. It records the winner in `docs/autoresearch/plan/YYYY-MM-DD-<feature-slug>.md` so the resulting architecture decision can feed planning.
- `autoresearch-impl` requires a baseline, a clean/non-conflicting worktree, and one narrow measured variant per round. It keeps an improvement as a commit or fully reverts a rejected change, writing `docs/autoresearch/impl/YYYY-MM-DD-<feature-slug>.md`.

Both are invoked conditionally by the full pipeline, and their outputs become evidence rather than untracked conversational preference. The relevant automated orchestrator cases are in `skills/full-pipeline/evals/evals.json` and `skills/superpowers-pipeline/evals/evals.json`.

## Change checklist

When changing this family:

- Preserve the difference between a sequencer and an implementer.
- Keep both database checkpoints conditional and tied to the plan/diff evidence at that stage.
- Preserve interactive pauses; do not pre-answer a downstream skill’s question.
- Keep the `gstack-to-plan` handoff template and readiness checks synchronized with its stated output contract.
- Review the pipeline eval cases after edits, especially skip/run decisions, database gates, missing-spec handling, and no-substitution behavior.
