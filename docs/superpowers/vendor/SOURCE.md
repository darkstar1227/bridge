Source: https://github.com/obra/superpowers
44c9b2d6e889982ac18c27d05a19fefe335194e1
cloned 2026-07-30T07:08:05Z

## Simplification pass (2026-07-30)

All 14 SKILL.md files condensed to cut context/token cost: removed
duplicate ASCII flowcharts that restated adjacent prose, illustrative
"Example Workflow"/"Real Example" sections, and repetitive
rationalization/red-flag tables — while keeping every operational rule,
template, checklist, and code example load-bearing to executing the skill.

Deleted entirely (dev/eval artifacts, not runtime content):
- `brainstorming/visual-companion.md` + `brainstorming/scripts/` (browser
  mockup companion — out of scope for this plugin's pipeline skills)
- `systematic-debugging/CREATION-LOG.md`,
  `systematic-debugging/test-academic.md`,
  `systematic-debugging/test-pressure-{1,2,3}.md` (skill-authoring eval
  scenarios, not needed to use the skill)

Untouched: `anthropic-best-practices.md` (Anthropic's official docs, only
loaded on demand), `persuasion-principles.md`,
`testing-skills-with-subagents.md`, and the per-platform reference files
under `using-superpowers/references/` — all lazy-loaded reference material
with no steady-state cost.

SKILL.md total: 3185 → 2273 lines. Vendor directory: 540K → 408K.

## subagent-driven-development: review-count rewrite (2026-07-30)

Restructured to cut review dispatches, per user request:

- **Removed the per-task reviewer entirely.** Each implementer's own
  self-review (already part of `implementer-prompt.md`) is now the task's
  only quality gate — no `task-reviewer-prompt.md` dispatch after each task.
  Deleted `task-reviewer-prompt.md` (unused after this change).
- **One review for the whole plan**, not one per task: the final
  whole-branch review is now the sole reviewer dispatch, running once after
  every task is implemented.
- **Fix loop capped at 2 rounds** (previously effectively unbounded per
  task at up to 5 rounds each). Since there's no more per-task safety net,
  the final review's fix loop gets a couple of tries instead of the old
  single-shot final-review fix wave.
- **Re-review skipped for Minor-only fix batches** — a scoped re-review now
  only runs when a fix round addressed a Critical/Important finding.

Trade-off (documented in the skill's "When to Use" section): a spec gap in
an early task is no longer caught until the final review, after later tasks
may have built on it. Accepted deliberately for lower review overhead;
plans with unusually risky or interdependent tasks should review more often
than this skill now defaults to.

## subagent-driven-development: dropped the implementer self-review too (2026-07-30)

Follow-up per user feedback that per-task review was still too heavy even
after the previous pass. Removed the implementer's formal self-review
checklist (completeness/quality/discipline/testing) from
`implementer-prompt.md` entirely — implementers now just implement, test,
commit, and report; no review of any kind, self or otherwise, happens at
task level. The single final whole-branch review is the only quality check
in the whole plan. Updated all "self-review" references in SKILL.md
(Overview, When to Use, Process, Setup, Task Loop) to match.

## subagent-driven-development: controller confirms verification evidence (2026-07-30)

Follow-up: user felt zero per-task checking (previous pass) was too little,
compared against executing-plans — which has no reviewer subagent either,
but does run each step's plan-specified verification inline and see the
real output itself. Brought that back without adding a subagent dispatch:
the controller now checks that an implementer's DONE report names the
actual verification command(s) and real output (pass count / "0 failures" /
the specific assertion that now holds) before logging the task complete —
a bare "DONE" or "tests pass" with nothing to back it gets sent back, same
treatment as DONE_WITH_CONCERNS. Tightened implementer-prompt.md's report
format so this evidence is always present, not just for TDD tasks.

## subagent-driven-development: moved the evidence check into the final review (2026-07-30)

Follow-up: rather than having the controller check verification evidence
per task (previous pass), moved that check into the single final
whole-branch review instead — consistent with "no check of any kind at task
level; every check happens once, at the end." The final review now audits
three things in one dispatch: spec compliance, code quality, and (new) a
verification-evidence audit across every task's report file, checking each
claimed DONE has a real command and real output behind it. Reverted the
per-task DONE handling in SKILL.md and the implementer-prompt.md report
format back to "nothing checks this at task level" language, pointing at
the final review instead.
