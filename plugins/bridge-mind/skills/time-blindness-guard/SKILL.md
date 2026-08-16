---
name: time-blindness-guard
description: Use when estimating how long work will take, when checking how long a session has run, when the user has lost track of elapsed time, or when a task has overrun its estimate. Triggers on phrases like "how long will this take", "how long have I been at this", "this should be quick", "I'll just finish this one thing", "what time is it even", "did I take a break", and on their Traditional Chinese equivalents 「這要多久」「我做多久了」「應該很快」「弄完這個就好」「現在幾點了」「我是不是又忘記休息」. Compensates for the two faces of ADHD time blindness — elapsed time that never registers during hyperfocus, and duration estimates that are systematically too low — using recorded history rather than intuition.
triggers:
  - how long will this take
  - how long have I been at this
  - this should be quick
  - I'll just finish this one thing
  - what time is it even
  - 這要多久
  - 我做多久了
  - 應該很快
  - 弄完這個就好
  - 我是不是又忘記休息
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
---

# Time Blindness Guard

**Announce at start:** "I'm using the bridge-mind:time-blindness-guard skill to check elapsed time against the record rather than against how it feels."

## Core Principle

ADHD time blindness is not carelessness about time. It is the absence of an internal clock. Twenty minutes and three hours produce the same subjective sensation when attention is fully engaged, which is why "I'll just finish this one thing" is sincere and also reliably wrong.

It shows up in two directions, and both are handled here:

- **Elapsed time does not register.** Hyperfocus consumes hours that are simply not felt. Meals, breaks, and other commitments pass unnoticed.
- **Duration estimates are systematically low.** Not occasionally — systematically, and by a fairly stable personal multiplier. Which means it is correctable, if the multiplier is measured instead of guessed.

The fix for both is the same: **replace the internal sense with an external record.** Not willpower, not trying harder to notice.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)**. Compatible with `i-have-adhd` output shaping if active.

Report elapsed time as a neutral number. **Never as a reprimand.** "You have been at this 4h20m" is information. "You've been at this 4h20m again" is a judgment, and a tool that judges gets muted — at which point it stops providing the external clock that is the entire reason it exists.

## Part A — Elapsed Time

The `focus-timer.sh` hook (`UserPromptSubmit`) tracks this automatically and nudges once at 120 minutes and once at 240. This skill is the manual counterpart, for when the user asks directly.

```bash
test -f .bridge/focus-state.json && cat .bridge/focus-state.json || echo "NO_SESSION_STATE"
date '+%Y-%m-%d %H:%M'
```

Compute elapsed from `session_start`. Report:

```
Session:  started 09:12, now 13:40 — 4h28m
Breaks:   none recorded
Goal:     "fix the deploy pipeline"    (from focus-state / active plan)
Actually: auth retry logic             (from git diff)
```

Two checks worth making, both briefly:

1. **Physical** — food, water, standing up. Not a lecture; one clause. Hyperfocus suppresses hunger and thirst signals outright, so their absence is not evidence that the needs were met.
2. **Drift** — is the current work still the stated goal? Compare against `.bridge/focus-state.json`, an active plan file, or session memory via `ctx_search`. Report divergence as an observation, never as a correction: the drifted work is sometimes the more valuable thread, and the user is the one who can tell.

## Part B — Estimate Calibration

Estimates do not improve by trying to estimate better. They improve by **multiplying the honest estimate by a measured personal ratio.**

### Recording

When the user states an estimate, log it to `.bridge/focus-log.jsonl` (read the file, append one line, write it back):

```json
{"date":"2026-08-16","task":"add retry wrapper to auth","estimate_min":45,"actual_min":null,"kind":"feature"}
```

When the task finishes — or when the user next mentions it as done — fill in `actual_min`. An estimate with no recorded actual teaches nothing, and this file is only worth keeping if it gets closed out.

### Feeding It Back

Before answering any "how long will this take", read the log first:

```bash
test -f .bridge/focus-log.jsonl && cat .bridge/focus-log.jsonl || echo "NO_LOG"
```

Compute the median ratio of `actual_min / estimate_min` across entries where both exist. Then:

- **Fewer than 5 completed entries** → not enough data. Say so, give the plain estimate, and record it. Do not invent a multiplier from a handful of points.
- **5 or more** → apply it and show the arithmetic:

  > "You estimated 45 minutes. Your median across 11 recorded tasks is 2.4x, so realistically 1h50m. Worth knowing before you commit to anything at 3pm."

- **Ratio differs by task kind** (`bugfix` vs `feature` vs `refactor`) → report the relevant one. Debugging in particular tends to have a far wider spread than feature work, because it is bounded by an unknown rather than by scope.

Show the multiplier rather than silently applying it. A number the user can see is one they can argue with, and it is far more persuasive than a revised estimate handed down without provenance.

## Part C — The "Just One More Thing" Check

When the user says they will "just finish this one thing" late in a long session, that sentence is a reliable marker: it is produced by the same broken clock that has already lost the afternoon.

Respond with the actual number and a concrete alternative, once:

> "That's the 4h30m mark. 'One more thing' has historically been about 50 minutes for you. If you want to stop soon, the cheapest resumable point is committing the retry wrapper now and leaving the failing test as the marker."

Then let it go. If they continue, help them continue — do not raise it again, and do not add a closing remark about it.

## Boundary vs Other Skills

| Situation | Skill |
|---|---|
| How long has this taken / will this take | **this skill** |
| About to do something irreversible | `risk-brake-thinking` |
| Lost the thread after a long session | `resume-interrupted-work` |
| Long session produced many half-finished threads | `unfinished-work-audit` |

## Example

User says: 「這個應該很快,大概半小時」

Read `.bridge/focus-log.jsonl`, find 9 completed entries with a median ratio of 2.6x, and answer:

> "Recorded: 30 min estimate. Your median is 2.6x across 9 tasks, so plan for about 80 minutes. I'll log the actual when it's done so the ratio stays current."
