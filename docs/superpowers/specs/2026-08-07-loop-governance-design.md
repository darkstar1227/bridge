# Loop Governance Design

Date: 2026-08-07
Status: Approved (brainstorming), pending implementation plan

## Problem

`bridge` currently helps target repos with tooling setup (`init-project`) and
with executing a plan → implement → review → QA sequence (`full-pipeline`,
`superpowers-pipeline`). It has no equivalent for Andrew Ng's three-layer
loop framing at the *process governance* level:

- No standard place to record task specs with explicit scope/acceptance
  criteria before implementation starts (Loop 1 discipline).
- No mechanism for feeding QA/review outcomes, incidents, or user feedback
  back into a durable record that shapes future backlog decisions (Loop 3).

The existing pipelines already cover Loop 1 (agentic coding) and Loop 2
(developer review) execution. This design adds the missing scaffolding and
wires it into the existing pipelines so it's actually used, not just present
as unused directories.

## Goals

- Give target repos a lightweight `specs/` + `docs/loops/` + `docs/feedback/`
  structure, scaffolded on demand by a new skill.
- Make `full-pipeline` and `superpowers-pipeline` autonomously judge whether
  a task needs a spec file before implementing, using a documented rule
  instead of asking the user every time.
- Make both pipelines write a feedback record after every run — minimal on
  success, detailed on any flagged anomaly — so Loop 3 signal accumulates
  without manual bookkeeping.
- Degrade gracefully in target repos that haven't opted into governance:
  skip the new steps, point at the new skill, never block the existing flow.

## Non-goals

- No infra/observability/k8s/terraform scaffolding — out of scope for a
  skill-only, no-deploy tool repo.
- No enforcement mechanism (git hooks, CI gates) forcing spec creation —
  judgment stays with the AI/orchestrator, not a hard gate.
- Not merged into `init-project` — kept as an independent skill so tooling
  setup and process governance stay separately triggerable.

## Design

### 1. New skill: `bridge:loop-governance-init`

Independent skill, parallel to `init-project`. Scaffolds process-governance
files into a target repo; does not execute any pipeline itself.

Output structure (created in the target repo):

```
specs/backlog/          # TASK-*.md / BUG-*.md, in/out scope + acceptance criteria
specs/active/
specs/done/
docs/loops/definition-of-done.md
docs/loops/release-checklist.md
docs/feedback/pipeline-log.md      # one line per pipeline run, success case
docs/feedback/incidents.md         # detailed entries for flagged anomalies
```

Templates for `specs/backlog/*.md`, `definition-of-done.md`, and
`release-checklist.md` are simplified versions of the ones in the user's
original three-layer-loop reference doc, with infra/observability/k8s
sections dropped as out of scope for this tool repo's target audience.

After scaffolding, the skill writes a CLAUDE.md conventions block into the
target repo (own marker pair, does not collide with `init-project`'s):

```markdown
<!-- bridge:loop-governance:start -->
## Loop Governance (managed by bridge:loop-governance-init)

### Spec-need judgment (autonomous, no need to ask user)
Before implementing, judge whether to open `specs/backlog/TASK-*.md` first:
- Needed: multi-file changes, breaking changes (schema/API/contract),
  new external dependency, uncertain blast radius
- Not needed: single-line fixes, typos, low-risk small changes
Only ask the user when genuinely unsure — don't ask every time.

### Feedback write-back (autonomous)
After every `full-pipeline` / `superpowers-pipeline` run:
- Clean finish → append one line to `docs/feedback/pipeline-log.md`
  (task / result / duration)
- QA or review caught an issue, or the user reports a problem after the
  fact → write a detailed entry to `docs/feedback/incidents.md`

_Last updated: <date> by bridge:loop-governance-init_
<!-- bridge:loop-governance:end -->
```

Follows `init-project`'s pattern: only replace content between the markers,
leave the rest of CLAUDE.md untouched; append the block if markers don't
exist yet.

### 2. Pipeline changes: `full-pipeline` and `superpowers-pipeline`

Both orchestrators get two new steps. Both steps no-op (with a one-line
pointer to `/loop-governance-init`) if the target repo has no
`docs/feedback/` directory — governance is opt-in, never a blocker.

**New Step 0 (before office-hours / before the first planning skill):**

Judge, using the CLAUDE.md rule written by `loop-governance-init`, whether
the incoming task needs a spec file. If yes: create
`specs/backlog/TASK-*.md` (or `BUG-*.md`) with scope/acceptance criteria
filled in, then continue into the existing sequence. If no: continue
directly, and state the judgment + reason in the step's output (e.g.
"judged no spec needed: single-file typo fix").

**New final step (after QA / code-review, end of sequence):**

Append one line to `docs/feedback/pipeline-log.md` unconditionally. If any
earlier step flagged an anomaly (review blocking issue, QA failure,
`autoresearch-impl` discarding most variants, etc.), also write a detailed
entry to `docs/feedback/incidents.md` (problem, root cause if known,
resolution taken).

### Interaction with existing skills

- `init-project` is unrelated/untouched — different marker block, different
  concern (tooling vs. process).
- `gstack-to-plan`, `autoresearch-plan`, `autoresearch-impl`,
  `subagent-driven-development` etc. are unaffected; the new steps wrap
  around the existing sequence, they don't alter any individual skill in it.

## Open questions for the implementation plan

- Exact spec template content (field list) for `TASK-*.md`/`BUG-*.md` —
  reference doc has a fuller example to adapt.
- Whether `opencode-subagent-driven-development` (the OpenCode-backed
  variant) also needs the same two steps, or is out of scope for this pass.
