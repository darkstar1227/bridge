---
name: unfinished-work-audit
description: Use when starting a work session, when the user asks what they should work on next, when they mention having too many things in flight, or when a new project is about to start while others are unfinished. Triggers on phrases like "what should I work on", "what's still open", "did I finish that", "I have too many things going", "let's start something new", "clean up my repos", and on their Traditional Chinese equivalents 「還有什麼沒做完」「我該做什麼」「東西太多了」「那個做完了嗎」「來做個新的」「清一下」. Surfaces abandoned in-flight work as concrete evidence (unmerged branches, untracked files, design specs with no implementation, stale TODOs) and forces an explicit ship / kill / park decision on each — countering the Se-driven pull toward whatever is newest and most stimulating.
triggers:
  - what should I work on
  - what's still open
  - did I finish that
  - I have too many things going
  - let's start something new
  - clean up my repos
  - 還有什麼沒做完
  - 我該做什麼
  - 東西太多了
  - 那個做完了嗎
  - 來做個新的
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Unfinished Work Audit

**Announce at start:** "I'm using the bridge-mind:unfinished-work-audit skill to surface what's still in flight before adding anything new."

## Core Principle

Se pulls attention toward whatever is newest and most stimulating right now. The design phase of a project
supplies exactly that — it is novel, concrete, and gives fast feedback — while the finishing phase supplies
none of it. The predictable result is a trail of well-specified work that was never completed.

This failure mode is invisible because nothing breaks. No test goes red when a design spec is abandoned.
The work simply evaporates, and the cost only shows up much later as "didn't we already solve this?"

**This skill does not moralize about discipline.** Telling an ESTP to be more disciplined does nothing.
It produces a visible pile of concrete items and asks for a decision on each, because a visible pile is
something Se actually engages with.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)** for the
per-item recommendations. The table itself is naturally compact and stays that way; the reasoning attached
to each recommendation needs to be complete, because "kill" and "ship" are decisions the user will act on
directly and a compressed justification invites the wrong call.

Never adopt a disappointed or scolding register. This skill reports findings; it does not grade the user.

## Step 1 — Gather Evidence

Run these in the target repo (adapt paths to the project):

```bash
echo "=== unmerged branches ==="
git branch --no-merged main 2>/dev/null

echo "=== stale branches (no commit in 30+ days) ==="
git for-each-ref --sort=committerdate refs/heads/ --format='%(committerdate:short) %(refname:short)' 2>/dev/null

echo "=== untracked files and directories ==="
git status --porcelain 2>/dev/null | grep '^??'

echo "=== uncommitted modifications ==="
git status --porcelain 2>/dev/null | grep -v '^??'

echo "=== design specs and plans on disk ==="
ls -la docs/superpowers/plans/ docs/superpowers/specs/ docs/plans/ 2>/dev/null

echo "=== stale TODO/FIXME markers ==="
grep -rIn --exclude-dir={.git,node_modules,.venv,dist,build} -E '(TODO|FIXME|XXX|HACK)' . 2>/dev/null | head -40
```

Use context-mode (`ctx_batch_execute` / `ctx_execute_file`) for this gathering pass when the repo is large —
only the derived findings belong in the conversation, not the raw output of every command.

## Step 2 — Find Specs Without Implementations

This is the highest-signal check and the one that requires actual judgment rather than a command.

For each design spec, plan, or PRD found in Step 1, determine whether the thing it describes actually
exists. A spec names a deliverable — a skill directory, a module, an endpoint, a table. Check whether that
deliverable is present in the codebase.

```bash
git log --oneline --all | grep -iE 'design spec|spec for|plan for|PRD'
```

Cross-reference every spec found against the code. A committed spec with no corresponding implementation is
abandoned work that looks like progress in the git history — the single most deceptive item in this audit,
because the commit log reads as if something shipped.

## Step 3 — Classify Each Item

Build one table. Do not editorialize inside it.

```
| Item | Evidence | Age | Recommendation |
|---|---|---|---|
| loop-governance-init skill | docs/.../2026-08-07-loop-governance.md (21K spec), no skill dir | 9 days | ship — spec is complete, implementation is mechanical |
| todo-tracker skill | commit 2f1de5d spec, no skill dir | 6 weeks | kill — superseded by this audit skill |
| skills/ stray directory | untracked, 3 subdirs | unknown | park — determine whether it duplicates plugins/ |
```

Three recommendations only:

- **ship** — the remaining work is small and mechanical relative to what is already done. Estimate the
  remaining effort concretely, in hours, so the user can judge it against a fresh project.
- **kill** — delete it, and say what makes it obsolete. **Killing is a success outcome, not a failure.**
  State this explicitly. An ESTP who believes this audit only ever adds obligations will stop running it,
  and half the value here is permission to close things out.
- **park** — genuinely valuable but not now. Requires a written reason and a condition that would revive
  it ("when the API contract settles"), otherwise it is a kill wearing a disguise.

## Step 4 — Enforce the WIP Ceiling

Count items recommended **ship** plus items already actively in progress.

If the total exceeds **3**, say so directly and ask which ones to demote. More than three genuinely open
threads means none of them are getting the sustained attention needed to finish, which is the mechanism
that produced this backlog in the first place.

## Step 5 — When the User Wants to Start Something New

If this skill was triggered by the user proposing a new project while unfinished work exists, do not block
them and do not lecture. Show the table, then ask one question:

> "Ship, kill, or park — which of these before the new one?"

Then respect the answer, including "none of them, I want the new thing." Autonomy preserved is what keeps
the skill trusted enough to be run at all next time.

## Example

Triggered at session start in a repo with two committed design specs and no matching implementations.

Don't: "You have a pattern of not finishing what you start."

Do: show both specs with sizes and ages, note that one is 21K of complete design whose implementation is
maybe two hours of mechanical work, recommend killing the other as superseded, and ask which to take.
