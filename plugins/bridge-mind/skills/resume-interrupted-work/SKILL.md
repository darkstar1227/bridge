---
name: resume-interrupted-work
description: Use at the start of a work session, after an interruption, after a context switch, or whenever the user has lost the thread of what they were doing. Triggers on phrases like "what was I doing", "where was I", "pick up where I left off", "I lost my train of thought", "what's the state of this", "remind me what this branch is", and on their Traditional Chinese equivalents 「我剛剛在幹嘛」「我做到哪了」「接續一下」「斷掉了」「這個分支在做什麼」「現在什麼進度」. Reconstructs the interrupted mental state from hard evidence (uncommitted diffs, stashes, recent commits, modified files, failing tests, session memory) instead of asking the user to remember, and ends on exactly one next action.
triggers:
  - what was I doing
  - where was I
  - pick up where I left off
  - I lost my train of thought
  - what's the state of this
  - 我剛剛在幹嘛
  - 我做到哪了
  - 接續一下
  - 斷掉了
  - 現在什麼進度
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Resume Interrupted Work

**Announce at start:** "I'm using the bridge-mind:resume-interrupted-work skill to reconstruct where you left off."

## Core Principle

An interruption does not just cost the seconds it takes. It discards the working-memory state that took twenty minutes to build — the half-formed model of which function was wrong, what the next edit was going to be, what had already been ruled out. With ADHD that state is both harder to rebuild and more completely lost.

**The user should not have to remember. The evidence is on disk.**

Uncommitted changes are the mental state, frozen at the moment of interruption. A failing test marks the exact spot. A branch name records the intent. Reconstruct from those, and hand back the thread rather than a request to recall it.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)**. Reconstructed context that has been compressed into fragments requires the reader to rebuild the connections — which is precisely the work they are unable to do right now.

If the `i-have-adhd` skill is active, follow its output shaping (next action first, numbered steps, restated state). It is fully compatible with this skill; that mode structures output, it does not compress it.

## Step 1 — Gather Evidence

```bash
echo "=== branch and recent trajectory ==="
git branch --show-current 2>/dev/null
git log --oneline -8 2>/dev/null

echo "=== uncommitted work: this IS the frozen mental state ==="
git status --short 2>/dev/null
git diff --stat 2>/dev/null
git diff 2>/dev/null | head -200

echo "=== stashes ==="
git stash list 2>/dev/null

echo "=== most recently touched files ==="
git diff --name-only 2>/dev/null | head -10
find . -type f -newermt '12 hours ago' -not -path './.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' 2>/dev/null | head -20

echo "=== markers added recently ==="
git diff 2>/dev/null | grep -E '^\+.*(TODO|FIXME|XXX|HACK|WIP)' | head -10
```

Use context-mode (`ctx_batch_execute` / `ctx_execute_file`) for this pass — only the derived reconstruction belongs in the conversation, not every raw diff line.

## Step 2 — Query Session Memory

Prior decisions, errors, and plans are searchable and often contain the reasoning that the diff alone cannot show:

```
ctx_search(queries: ["what was being implemented", "recent errors", "decisions made", "plan"], sort: "timeline")
```

This frequently recovers *why* an approach was chosen — the piece most completely lost in an interruption, and the piece the user is least able to reconstruct alone.

Also check for an active plan:

```bash
ls -lt docs/superpowers/plans/ ~/.claude/plans/ 2>/dev/null | head -5
```

## Step 3 — Check Whether the Work Is Still Running

An interrupted session may have left something mid-flight:

```bash
git stash list 2>/dev/null | head -3
```

If a test suite, build, or long-running command was the last thing happening, note that its result may be stale and worth re-running before trusting it.

## Step 4 — Reconstruct, Then Sanity-Check the Thread

Write the reconstruction as a short narrative, not a data dump:

> "You were on `feat/auth-retry`. Three files are modified but uncommitted — the retry wrapper in `src/auth/retry.ts` is written, and `auth.test.ts` has a new test for the 429 path that is currently failing on a timeout assertion. The last commit was the token refresh, 40 minutes before the modifications. It looks like you were mid-way through making that new test pass."

Then apply the **tangent check**. Compare the interrupted work against the session's stated goal, if one is recorded (`.bridge/focus-state.json`, an active plan file, or session memory).

If they diverge, say so plainly and without judgment:

> "Worth noting: you sat down to fix the deploy pipeline. This retry work is related but is not that. Resume it, or park it and go back?"

Resuming a rabbit hole faster is not a win. This check is the difference between restoring momentum and restoring drift.

## Step 5 — End on Exactly One Next Action

**This is the most important rule in this skill.**

Finish with a single, concrete, physically executable action. Not a summary. Not options. Not a list.

> "Next: run `npm test -- auth.test.ts` and read the timeout assertion on line 47."

A menu of choices is a decision, and decision-making is the resource that is already depleted — offering three good options is how a resumption stalls into another twenty minutes of nothing. If genuinely more than one thread is open, pick the one closest to completion, state that you picked it and why, and let the user redirect if they disagree. Choosing wrongly costs one sentence of correction; not choosing costs the session.

If the next action is small enough, **offer to do it immediately** rather than describing it.

## Boundary vs Other Skills

| Situation | Skill |
|---|---|
| One thread, interrupted recently, warm — restore it | **this skill** |
| Many threads, cold, across projects — decide what lives and dies | `unfinished-work-audit` |
| Thread restored but the user still cannot start | `task-activation` |

## Example

User says: 「我剛剛在幹嘛」

Don't: ask what they were working on, or list every modified file.

Do: read the diff, notice `auth.test.ts` has an unfinished test and the retry wrapper is already written, state that in two sentences, note that this diverges from the stated deploy-pipeline goal, and end with the single command that shows the current failure.
