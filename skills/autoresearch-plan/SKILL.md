---
name: autoresearch-plan
description: Runs a Karpathy-autoresearch-style comparative experiment loop over candidate technical approaches (API designs, algorithms, data-flow strategies) after a plan has been reviewed but before it's handed to an implementer. Picks a winning approach against an explicit metric and records the baseline, so downstream implementation isn't built on an unvalidated guess. Use this whenever the user wants to "test approaches before committing", "spike a few options", "compare designs experimentally", mentions autoresearch/Karpathy in a planning context, or after gstack's /autoplan when the plan contains more than one viable technical direction.
triggers:
  - autoresearch plan
  - compare candidate approaches
  - spike before implementing
  - test approaches experimentally
  - karpathy autoresearch plan
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - AskUserQuestion
  - Agent
---

# Bridge: Autoresearch (Plan-Level)

**Announce at start:** "I'm using the bridge:autoresearch-plan skill to experimentally compare candidate approaches before we commit to one."

## Purpose

karpathy/autoresearch's actual design (an agent iterating on `train.py`, fixed 5-minute budget, single metric `val_bpb`, keep-or-discard) works because three things are nailed down before any iteration starts: the **scope** of what varies, a **fixed budget**, and a **single, directional metric**. This skill exists to enforce that same discipline at the plan stage — after a plan has been shaped (e.g. by gstack's `/autoplan`) but before it's frozen into an implementation spec. Its job is not to write code; it's to spend a small, bounded amount of effort testing 2+ real candidate approaches against real data, so the plan that reaches `writing-plans` / `gstack-to-plan` encodes a validated decision instead of a guess.

Do not run this skill on a plan that only has one viable approach — there's nothing to compare, and manufacturing fake alternatives to satisfy this skill defeats its purpose. Skip straight to the next pipeline step in that case and say so.

## Step 1 — Locate the plan and candidate approaches

Find the source plan using the same search order as `gstack-to-plan` Step 1 (explicit path arg → `docs/plan.md` → `docs/spec.md` → most recently modified `.md` under `docs/` or `.gstack/`). Read it in full.

Look for places where the plan already names more than one option (an "alternatives considered" section, a note like "could do X or Y", or an open architecture question). If the plan commits to a single approach with no alternatives mentioned, ask the user: do they want to (a) proceed as-is with no experiment, or (b) name 2-4 candidate approaches themselves right now? Don't invent candidates unprompted — a fabricated alternative that nobody actually wants is wasted effort.

## Step 2 — Pin down scope, budget, and metric

This is the step that matters most. Before spawning anything, establish all three of:

1. **Scope** — what specifically varies between candidates (e.g. "sync vs. async job queue", "REST vs. gRPC for this one internal call", "which caching strategy"). Keep it to one axis of variation at a time, same as autoresearch limiting the agent to one file (`train.py`) — comparing approaches that differ on five axes at once makes the result uninterpretable.
2. **Budget** — a hard cap on how much experimentation happens: number of candidates × number of rounds, or a wall-clock/turn limit. Without this the loop can run indefinitely.
3. **Metric + direction** — one quantity that's measured for every candidate, and whether higher or lower is better (latency lower-is-better, throughput higher-is-better, cost lower-is-better, correctness/success-rate higher-is-better). It must be something a subagent can actually produce a number for within this repo's constraints — not an aspirational quality like "which one feels more maintainable."

Try to derive these three from context already on hand before asking the user anything:
- The plan's own "success metrics" / "acceptance criteria" section
- Any office-hours notes or prior planning docs in `docs/`
- Relevant project or feedback memory (recent decisions, prior benchmarks run in this repo)

Only fall back to `AskUserQuestion` for whichever of the three you couldn't confidently derive. State what you inferred and let the user correct it rather than silently assuming.

## Step 3 — Run the comparison round(s)

For each candidate approach, spawn one subagent via the `Agent` tool to produce the metric for that candidate. Keep what each subagent does proportionate to the metric — this is a spike, not a feature build:
- If the metric is measurable by reasoning/analysis (e.g. estimated complexity, a calculation, reading existing benchmarks for a library), have the subagent do that analysis and report the number with its reasoning.
- If the metric requires running something (a timing test, a small prototype call), have the subagent build the minimal harness needed to produce that one number, in a scratch location — not wired into the real codebase yet.

Collect all candidates' scores before comparing (this is a genuine barrier: you need every candidate's number to declare a winner). Rank by the metric's stated direction.

If the budget allows another round and the result is ambiguous (e.g. top two candidates are within noise of each other, or a hybrid of the top two seems promising), refine and re-run within the remaining budget. Otherwise stop and declare the winner — don't keep iterating past the budget just because the answer feels unsatisfying; a bounded-but-imperfect answer beats an unbounded loop.

## Step 4 — Record the outcome

Write the result to `docs/autoresearch/plan/YYYY-MM-DD-<feature-slug>.md` (today's date; derive the slug from the plan title). Use this structure:

```markdown
# Autoresearch (Plan-Level): <Feature Name>

_Source plan: <path>_
_Run: <today's date>_

## Scope of variation
<the one axis that was compared>

## Metric
<what was measured, and which direction is better>

## Budget used
<candidates × rounds actually run, vs. the cap>

## Candidates and results
| Candidate | Score | Notes |
|---|---|---|
| ... | ... | ... |

## Winner
<which candidate, and why — reference the metric, not vibes>

## Discarded alternatives
<each non-winning candidate and the concrete reason it lost>
```

## Step 5 — Hand off

Tell the user the winning approach and point them at the recorded file. If the next step in their pipeline is `gstack-to-plan` or `writing-plans`, note explicitly that the winning approach (not the plan's original default, if they differed) is the technical decision to encode as an Architecture Decision — don't let the downstream step silently fall back to whatever the plan said before this experiment ran.
