---
name: autoresearch-impl
description: Runs a Karpathy-autoresearch-style keep-or-discard iteration loop over an already-implemented branch — propose one variant, run it against tests/benchmarks, keep it if the metric improves or discard and revert, repeat within a fixed budget — before handing off to code-review/QA. Use this after subagent-driven-development (or opencode-subagent-driven-development) finishes a task, whenever the user wants to "squeeze out more performance", "try a few implementation variants", "iterate on this implementation before review", or mentions autoresearch/Karpathy about code that already runs.
triggers:
  - autoresearch implementation
  - iterate on implementation before review
  - benchmark implementation variants
  - try a few variants and keep the best
  - karpathy autoresearch impl
allowed-tools:
  - Bash
  - Read
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Agent
---

# Bridge: Autoresearch (Implementation-Level)

**Announce at start:** "I'm using the bridge:autoresearch-impl skill to iterate on the implementation against a metric before it goes to review."

## Purpose

This mirrors karpathy/autoresearch's actual loop more directly than the plan-level version does, because there's now real code and (usually) real tests to run: propose a change to one file/module, run it for a fixed budget, check whether a single metric got better, keep or discard, repeat. The autoresearch repo enforces this by restricting the agent to one file (`train.py`) and running every variant for a fixed 5-minute wall-clock budget so results are comparable. Do the same here: keep each round's diff small and reviewable, and bound the loop by rounds or wall-clock time, not by "iterate until it feels done."

Only run this on real, working code — an implementation that already passes its own tests/builds. This skill improves a working baseline; it is not a substitute for finishing the implementation first.

## Step 0 — Confirm there's something to iterate on

Run `git status` and `git diff` (or check the relevant worktree/branch) to confirm there's a completed implementation to work from. If the working tree is dirty with unrelated changes, stop and ask before touching anything — per this repo's git safety rules, uncommitted work that isn't yours to discard must be stashed or committed first, never dropped.

## Step 1 — Pin down scope, budget, and metric

Same three knobs as the plan-level skill, but scoped to code:

1. **Scope** — which file(s) or module(s) are fair game to modify this round. Keep this narrow (ideally one file or one clearly-bounded module), same as autoresearch limiting changes to `train.py` — a wide scope makes it impossible to attribute a metric change to a specific diff.
2. **Budget** — a hard cap: max number of rounds, or a wall-clock limit for the whole loop. Decide this now, not mid-loop.
3. **Metric + direction** — a command that produces one number, and which direction is better. Good candidates already sitting in most repos: a test suite's pass rate or runtime, a benchmark script's output, a bundle-size check, a lint/type-error count. It must be a command you can actually run here — not a metric that requires infrastructure this repo doesn't have (e.g. don't invent a load-test metric if there's no load-testing setup).

Derive these from context first — the plan's verification/acceptance-criteria section, an existing benchmark script, CI config, or `package.json`/`Makefile` test targets — and only ask the user for whichever piece isn't recoverable that way.

## Step 2 — Isolate each round so a bad variant is cheap to discard

Before the first round, note the current commit (or create one if the implementation isn't committed yet) as the recovery point. For each round:

1. Spawn a subagent (via `Agent`) with the scope, the current best state, and the metric command, instructed to propose and apply exactly one variant within the scope.
2. Run the metric command yourself (or have the subagent run it and report the raw number, not just "better/worse" — verify the claim before trusting it).
3. Compare to the current best score.
   - **Improved** → keep it: commit with a message noting the round and the metric delta, and make this the new baseline for the next round.
   - **Not improved** → discard: `git checkout -- <files>` (or `git reset --hard` to the last kept commit) to cleanly revert before the next round starts. Never leave a discarded variant's changes sitting in the working tree into the next round — that contaminates the next diff's attribution.
4. Log the round's result (see Step 4) regardless of outcome.

Never run multiple variants concurrently against the same working tree — same conflict risk called out in `opencode-subagent-driven-development`. If the user explicitly wants true parallel variant exploration, that requires isolated worktrees per variant; ask before doing that, since it's a heavier operation than this skill defaults to.

## Step 3 — Stop condition

Stop when any of these hit first: the round budget is exhausted, the wall-clock limit is reached, or N consecutive rounds (agree this number with the user up front if not obvious — 2 or 3 is reasonable) produce no improvement. Report the final kept state as the answer; don't keep spending rounds chasing marginal gains past the agreed budget.

## Step 4 — Record the log

Write to `docs/autoresearch/impl/YYYY-MM-DD-<feature-slug>.md`:

```markdown
# Autoresearch (Implementation-Level): <Feature Name>

_Scope: <file(s)/module(s) that were fair game>_
_Metric: <command + direction>_
_Budget: <cap>_
_Run: <today's date>_

## Rounds
| Round | Variant summary | Metric score | Kept? | Reason |
|---|---|---|---|---|
| 1 | ... | ... | yes/no | ... |

## Final result
<final metric score vs. the starting baseline>

## Stopped because
<budget exhausted / wall-clock hit / N rounds with no improvement>
```

## Step 5 — Hand off

Confirm the working tree is on the best-kept state (not mid-round), then hand off to `code-review` / `codex:review` and `/qa` as the pipeline already does. Mention the metric improvement (or lack of one) in the handoff so reviewers know what changed and why.
