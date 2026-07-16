---
name: opencode-bridge
description: Delegate a coding task to OpenCode and get back a structured handoff report (done/failed/timed-out, files changed, implementation summary) — for use as an OpenCode-backed implementer step in subagent-driven-development or executing-plans.
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
