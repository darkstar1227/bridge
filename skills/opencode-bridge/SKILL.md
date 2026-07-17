---
name: opencode-bridge
description: Delegate a coding task to OpenCode and get back a structured handoff report (done/failed/timed-out, files changed, implementation summary) — for use as an OpenCode-backed implementer step in subagent-driven-development or executing-plans. For a full plan-execution loop with review gates already wired in, use bridge:opencode-subagent-driven-development instead of calling this standalone.
allowed-tools:
  - Bash
  - AskUserQuestion
triggers:
  - delegate to opencode
  - use opencode for this task
  - opencode bridge
---

# OpenCode Bridge

**Announce at start:** "I'm using the opencode-bridge skill to delegate this task to OpenCode."

## Step 0: Check whether this should be a standalone call

This skill only does one thing: hand a task to OpenCode and return a handoff report. It has **no spec-compliance review, no code-quality review, and no test enforcement** — `test_results` and `self_review_notes` in the report are literally "not reported by OpenCode". Those review gates only exist in `superpowers:subagent-driven-development` (or `superpowers:executing-plans`), which can use this skill as their implementer step instead of a Claude subagent.

Before running Step 1, check: is this invocation already happening as the implementer step inside an active `/subagent-driven-development` or `/executing-plans` run for this task (i.e. that skill's process is already driving this task, and it will handle spec/quality review after this skill returns)?

- **Yes** → proceed directly to Step 1, no prompt needed.
- **No** (this is a bare/ad-hoc request to "delegate this to opencode" for a single task, with no surrounding plan-execution flow tracking review gates) → stop and ask the user via AskUserQuestion:
  - **Question**: "opencode-bridge alone skips spec-compliance and code-quality review. Run this through `bridge:opencode-subagent-driven-development` instead (recommended — same review gates as subagent-driven-development, with OpenCode as the implementer), or continue standalone?"
  - Options: "Use bridge:opencode-subagent-driven-development" (invoke that skill instead — it wraps `superpowers:subagent-driven-development`'s loop with this skill as the implementer step) vs. "Continue standalone anyway" (proceed to Step 1 as normal).

Do not re-ask within the same standalone session once the user has picked "continue standalone" — only re-prompt for a genuinely new task/invocation.

## Step 1: Check config

Run:
```bash
test -f ~/.opencode-bridge/config.json && echo EXISTS || echo MISSING
cat ~/.opencode-bridge/config.json 2>/dev/null
```

If `MISSING`, or if the file exists but fails to parse as JSON: ask the user via AskUserQuestion for:
- Default model (`provider/model` format, e.g. `opencode/kimi-k2.7-code` — list available models with `opencode models` if the user wants to see options)
- Fallback model list (ordered, can be empty)
- Per-attempt timeout in seconds (default suggestion: 300)
- Chain-level timeout in seconds (default suggestion: 600 — must be greater than per-attempt timeout)

Write the answers to `~/.opencode-bridge/config.json`:
```json
{
  "default_model": "<answer>",
  "fallback_models": ["<answer>", "..."],
  "per_attempt_timeout_seconds": <answer>,
  "chain_timeout_seconds": <answer>
}
```

Do this only once — do not re-ask on subsequent invocations once the file exists and parses.

## Step 1b: Check the Bash permission allowlist

This skill's Step 2 shells out to `uv run .../dispatch.py`, which in turn invokes the `opencode` CLI — an external coding agent. Without an allow rule, some permission configurations (or hook-based classifiers layered on top of Claude Code's own permission system) may flag or prompt on this pattern every time, since it looks like handing code/tasks to a third-party tool.

Check whether the current project's `.claude/settings.local.json` (or `.claude/settings.json`) already allows this Bash pattern:
```bash
grep -r "uv run" .claude/settings.local.json .claude/settings.json 2>/dev/null
```

If no matching rule exists, ask the user via AskUserQuestion whether to add one:
- **Question**: "This skill needs to run `uv run .../dispatch.py` without a permission prompt each time. Add a Bash allow rule to `.claude/settings.local.json`?"
- If yes, add (creating the file/`permissions.allow` array if absent):
  ```json
  { "permissions": { "allow": ["Bash(uv run *)"] } }
  ```
  (merge into any existing `permissions.allow` array rather than overwriting it).
- If the user declines, proceed anyway — Step 2 will simply prompt for permission on each dispatch call.

Do this only once per project — do not re-ask once the rule is present.

## Step 1c: Parallel dispatch requires isolation

`dispatch.py` shells out with `--dir <repo>` and diffs `git status` before/after directly against that repo path — it has no isolation of its own. Running two or more dispatches against the **same repo path** at the same time will race on git state (one call's in-flight edits pollute another's before/after snapshot).

Before running Step 2, check: will this be the only dispatch running against this repo path at once?

- **Yes (single dispatch, or multiple dispatches each against a different repo path)** → proceed directly to Step 2.
- **No (multiple dispatches needed concurrently against the same repo)** → do not invoke Step 2 directly in parallel. Instead, use one of:
  - **Worktree isolation**: create a separate `git worktree` per concurrent task (see `superpowers:using-git-worktrees`) and pass each worktree's absolute path as `--repo` — this gives each dispatch its own working tree and git state.
  - **Subagent dispatch**: have Claude Code launch one Agent (subagent) per concurrent task, each running its own Step 2 `uv run dispatch.py` call scoped to its own worktree/repo path — do not fan out raw parallel Bash calls against one shared repo path from the main loop.

## Step 2: Dispatch

Run (substituting the actual task description, target repo absolute path, and a short topic string identifying this line of work — e.g. the feature/branch name):

```bash
timeout <chain_timeout_seconds + 30> uv run skills/opencode-bridge/scripts/dispatch.py \
  --task "<task description>" --repo "<absolute repo path>" --topic "<topic>"
```

The outer `timeout` value must exceed the configured `chain_timeout_seconds` — it exists so that if Claude's own Bash tool call is itself cancelled or times out, the OpenCode process group still gets reaped rather than surviving as an orphan.

## Step 3: Handle the result

Parse the JSON handoff report from stdout.

- If `terminal_state` is `DONE`: present `implemented_summary`, `files_changed`, and `test_results` to the user/calling workflow. This report can be handed directly to `subagent-driven-development`'s `spec-reviewer-prompt.md` step.
- If `terminal_state` is `FAILED` or `TIMED_OUT`: present `issues` and any partial `files_changed`. If the failure happened after files were mutated, say so explicitly and do not automatically retry — ask the user how to proceed (continue manually, discard partial edits, or something else).
- If `terminal_state` is `CONFIG_ERROR`: re-run Step 1.
