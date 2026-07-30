---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
---

# Subagent-Driven Development

Execute plan by dispatching a fresh implementer subagent per task. Nothing
checks or reviews a task at task level — implementers implement, test,
commit, and report, and the controller logs each report straight to the
ledger. Every check in the whole flow — spec compliance, code quality, and
whether each task's tests are real, not just claimed — happens exactly once,
in a single whole-branch review dispatched after every task is done, with a
short capped fix loop.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused and succeed at their task. They should never inherit your session's context or history — you construct exactly what they need. This also preserves your own context for coordination work.

**Core principle:** Fresh subagent per task, zero review overhead until
every task is done, one broad review at the end = minimum review dispatches
for the whole plan.

**Narration:** between tool calls, narrate at most one short line — the
ledger and the tool results carry the record.

**Continuous execution:** Do not pause to check in with your human partner between tasks. Execute all tasks from the plan without stopping. The only reasons to stop are: BLOCKED status you cannot resolve, ambiguity that genuinely prevents progress, or all tasks complete. "Should I continue?" prompts and progress summaries waste their time — they asked you to execute the plan, so execute it.

## When to Use

Have a plan, tasks mostly independent, staying in this session → use this skill.
Tasks tightly coupled or no plan yet → brainstorm/plan first. Independent tasks
but need a parallel session instead → use `executing-plans`.

**vs. Executing Plans (parallel session):** same session (no context switch),
fresh subagent per task (no context pollution), zero review overhead per
task and one broad review at the end, faster iteration (no human-in-loop
between tasks).

**Trade-off of skipping all per-task review:** a spec gap in an early task
isn't caught until the final whole-branch review, after every later task may
have built on it. This skill accepts that trade-off for speed and the lowest
possible review overhead — if a plan's tasks are unusually risky or tightly
interdependent, consider reviewing more often than this skill defaults to.

## The Process

Setup (worktree, ledger check, read plan, pre-flight review) → per task:
dispatch implementer → answer its questions if any → it implements, tests,
commits, and reports → append completion to ledger, mark todo complete, next
task. When no tasks remain: dispatch the final whole-branch review — spec
compliance, code quality, and a verification-evidence audit across every
task's reports, all in one pass — → clean? → delete this plan's workspace →
use `superpowers:finishing-a-development-branch`. Findings? → fix round
(cap 2): ONE fix dispatch covering every open finding → batch was
Minor-only? skip re-review, just confirm the fix report's tests →
otherwise scoped re-review → all addressed? → clean, proceed to finish.
Round cap hit with findings still open → adjudicate each: load-bearing →
STOP, report BLOCKED; not load-bearing → park in ledger with ruling, then
proceed to finish.

## Setup

Ensure the work happens in an isolated workspace: use
superpowers:using-git-worktrees to create one or verify the existing one.
Never start implementation on a main/master branch without your human
partner's explicit consent.

Conversation memory does not survive compaction. In real sessions,
controllers that lost their place have re-dispatched entire completed task
sequences — the single most expensive failure observed. Track progress in
a ledger file, not only in todos.

- Each plan owns a workspace: at skill start, run this skill's
  `scripts/sdd-workspace PLAN_FILE` — it prints the plan's git-ignored
  directory (`<repo-root>/.superpowers/sdd/<plan-basename>/`), home to
  every artifact for THIS plan: ledger, briefs, reports, review packages.
  Another plan's directory is never yours to read or write.
- Check for this plan's ledger at `<workspace>/progress.md`. If its first
  line names your plan file, tasks with a `Task <N>: complete` line are DONE
  — do not re-dispatch them; resume at the first task without one. A ledger
  whose first line names a different plan file — or a stray ledger at the
  old flat path `.superpowers/sdd/progress.md` — is another plan's
  progress: leave it in place and start your own, fresh.
- Create the ledger with its identity as the first line:
  `# SDD ledger — plan: <plan file path>`.
- The ledger is your recovery map: the commits it names exist in git even
  when your context no longer remembers creating them. After compaction,
  trust the ledger and `git log` over your own recollection.
- `git clean -fdx` will destroy the workspace (it's git-ignored scratch); if
  that happens, recover from `git log`.

Read the plan once, note its context and Global Constraints, and create a
todo per task.

Before dispatching Task 1, scan the plan once for conflicts:

- tasks that contradict each other or the plan's Global Constraints
- anything the plan explicitly mandates that the final review's rubric
  treats as a defect (a test that asserts nothing, verbatim duplication of
  a logic block)

Present everything you find to your human partner as one batched question —
each finding beside the plan text that mandates it, asking which governs —
before execution begins, not one interrupt per discovery mid-plan. If the
scan is clean, proceed without comment. Since there's no review of any kind
until every task is done, this pre-flight scan is the only thing catching
plan-level conflicts before the final review.

## Model Selection

Use the least powerful model that can handle each role to conserve cost and speed.

**Mechanical implementation tasks** (isolated functions, clear specs, 1-2 files): use a fast, cheap model. Most implementation tasks are mechanical when the plan is well-specified.

**Integration and judgment tasks** (multi-file coordination, pattern matching, debugging): use a standard model.

**Architecture and design tasks**: use the most capable available model.
The final whole-branch review is one of these — dispatch it on the most
capable available model, not the session default.

**The final review's fix-round re-reviews:** scale to the fix diff's size
and risk — a small mechanical fix takes a cheap-to-mid tier; a subtle
concurrency fix needs a standard-or-better model.

**Always specify the model explicitly when dispatching a subagent.** An
omitted model inherits your session's model — often the most capable and
most expensive — which silently defeats this section.

**Turn count beats token price.** Wall-clock and context cost scale with how
many turns a subagent takes, and the cheapest models routinely take 2-3× the
turns on multi-step work — costing more overall. Use a mid-tier model as the
floor for implementers working from prose descriptions. When the task's plan
text contains the complete code to write, the implementation is transcription
plus testing: use the cheapest tier for that implementer. Single-file
mechanical fixes also take the cheapest tier.

**Task complexity signals (implementation tasks):**
- Touches 1-2 files with a complete spec → cheap model
- Touches multiple files with integration concerns → standard model
- Requires design judgment or broad codebase understanding → most capable model

## The Task Loop

Everything you paste into a dispatch prompt — and everything a subagent
prints back — stays resident in your context for the rest of the session
and is re-read on every later turn. Hand artifacts over as files.

### 1. Dispatch the implementer

Record BASE (`git rev-parse HEAD`) before dispatching — you need it for the
ledger's commit range, and for the final review's diff if this is the last task.

- **Task brief:** before dispatching an implementer, run this skill's
  `scripts/task-brief PLAN_FILE N` — it extracts the task's full text to a
  uniquely named file and prints the path. Compose the dispatch so the
  brief stays the single source of
  requirements. Your dispatch should contain: (1) one line on where this
  task fits in the project; (2) the brief path, introduced as "read this
  first — it is your requirements, with the exact values to use verbatim";
  (3) interfaces and decisions from earlier tasks that the brief cannot
  know; (4) your resolution of any ambiguity you noticed in the brief;
  (5) the report-file path and report contract. Exact values (numbers,
  magic strings, signatures, test cases) appear only in the brief. Never
  make a subagent read the whole plan file.
- **Report file:** name the implementer's report file after the brief
  (brief `…/task-N-brief.md` → report `…/task-N-report.md`) and put it in
  the dispatch prompt. The implementer writes the full report there and
  returns only status, commits, a one-line test summary, and concerns.
- A dispatch prompt describes one task, not the session's history. Do not
  paste accumulated prior-task summaries ("state after Tasks 1-3") into
  later dispatches — a real session's dispatch hit 42k chars of which 99%
  was pasted history. A fresh subagent needs its task, the interfaces it
  touches, and the global constraints. Nothing else.
- If an earlier task parked a finding in the area this task touches, carry
  a pointer to that ledger entry in the dispatch.
- Record the implementer's agent identity from the dispatch result — the
  final review's fix loop may resume this agent for findings in this task.
- Never dispatch multiple implementation subagents in parallel (conflicts).

Template: [implementer-prompt.md](implementer-prompt.md)

### 2. Handle the report

Implementer subagents report one of four statuses. Handle each appropriately:

**DONE:** nothing checks the report at task level. Append the completion
line to the ledger and move on — the final whole-branch review is where
this task's tests, and every other task's, get checked for real.

**DONE_WITH_CONCERNS:** The implementer completed the work but flagged doubts. Read the concerns before proceeding. If the concerns are about correctness or scope, address them before marking complete — resume the implementer or fix inline yourself if trivial. If they're observations (e.g., "this file is getting large"), note them in the ledger and proceed.

**NEEDS_CONTEXT:** The implementer needs information that wasn't provided. Provide the missing context and re-dispatch.

**BLOCKED:** The implementer cannot complete the task. Assess the blocker:
1. If it's a context problem, provide more context and re-dispatch with the same model
2. If the task requires more reasoning, re-dispatch with a more capable model
3. If the task is too large, break it into smaller pieces
4. If the plan itself is wrong, escalate to the human

**Never** ignore an escalation or force the same model to retry without changes. If the implementer said it's stuck, something needs to change.

If the implementer asks questions — before starting or mid-task — answer
clearly and completely, provide additional context if needed, and don't
rush it into implementation.

### 3. Complete the task

Once the report is DONE (or DONE_WITH_CONCERNS resolved), append the
completion line to the ledger in the same message as your other bookkeeping:

`Task <N>: complete (commits <base7>..<head7>)`

Then mark the todo complete and move on to the next task.

## Final Review

The final whole-branch review gets a package too: run
`scripts/review-package PLAN_FILE MERGE_BASE HEAD` (MERGE_BASE = the commit the
branch started from, e.g. `git merge-base main HEAD`) and include the
printed path in the final review dispatch, so the final reviewer reads
one file instead of re-deriving the branch diff with git commands. Dispatch
on the most capable available model (see Model Selection), using
superpowers:requesting-code-review's
[code-reviewer.md](../requesting-code-review/code-reviewer.md). This is the
only review dispatch in the whole flow, so it carries everything that would
otherwise have been checked task-by-task: spec compliance and code quality
across the full diff, same as before, plus one thing that used to be a
per-task gate and is now folded in here instead —

**Verification-evidence audit.** Point the reviewer at the ledger and the
directory of task report files (`<workspace>/task-*-report.md`) alongside
the diff. For each task, it should be able to find a real command and real
output backing the claim — a pass count, "0 failures," or the specific
assertion that now holds — not just "tests pass" with nothing behind it.
A task whose report claims success without evidence is a finding, at the
same severity as a task whose tests don't actually cover the change: this
is the one place in the whole flow that catches an implementer who claimed
DONE without really verifying, so it isn't optional scope.

**If clean:** proceed to Finish.

**If it returns findings**, enter a fix loop capped at **2 rounds**:

- Dispatch ONE fix subagent per round with the complete findings list — not
  one fixer per finding. Per-finding fixers each rebuild context and re-run
  suites; a real session's final-review fix wave cost more than all its
  tasks combined.
- **Skip the re-review when the round was Minor-only.** If every finding in
  that round's batch was Minor severity, confirm the fix report names the
  covering tests and shows passing output, then treat the batch as
  addressed without dispatching a re-reviewer. If the round included any
  Critical or Important finding, dispatch exactly one scoped re-review of
  the fix diff (`scripts/review-package PLAN_FILE FIX_BASE HEAD`,
  [re-review-prompt.md](re-review-prompt.md)) — never skip re-review for a
  batch that mixes severities.
- **After round 2**, or as soon as a round comes back fully addressed:
  adjudicate any residual findings yourself, the same way — real but
  nothing downstream builds on it → park it in the ledger with a ruling;
  real and load-bearing (a defect that would compound, or reveals a plan
  problem) → STOP and report BLOCKED to your human partner with the
  finding, the plan text it collides with, and the fix history. There is no
  third round — residual load-bearing findings surface to your human
  partner when finishing-a-development-branch presents the options.

## Finish

When the final whole-branch review is clean (or its residual findings are
parked with rulings) and any fixes are merged, delete this plan's workspace
(`rm -rf <workspace>`) — the git history is the record now. Sibling
directories belong to other plans; leave them alone.

Use superpowers:finishing-a-development-branch.

## Common Rationalizations

Spec gaps aren't "close enough" — fix them or park with an explicit ruling;
those are the only exits. Never fix findings yourself in the controller
session (pollutes context, skips review) — dispatch the fix subagent.
Skipping re-review is only for Minor-only batches — a round that includes
any Critical/Important finding always gets a scoped re-review, even if the
fix looked small. Adjudicate residual findings only after the round cap, and
every ruling is a ledger entry — silent discards are forbidden. "The
implementer already said DONE, the evidence check is redundant" is the
rationalization that makes the whole flow trust unverified claims — the
verification-evidence audit is scoped into the final review precisely
because nothing checks it before then; don't hand-wave it as covered by the
implementer's own report. The ledger is what survives compaction —
controllers without one have re-dispatched entire completed task sequences.
