---
name: opencode-subagent-driven-development
description: Wraps Superpowers' subagent-driven-development plan-execution loop, asking upfront whether the implementer step should be a Claude subagent (default) or OpenCode via opencode-bridge — spec-compliance and code-quality review stay identical either way.
triggers:
  - subagent driven development with opencode
  - opencode subagent driven development
  - use opencode as implementer
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
  - Agent
---

# Bridge: Subagent-Driven Development ↔ OpenCode Implementer

**Announce at start:** "I'm using the bridge:opencode-subagent-driven-development skill to run the plan, and I'll ask which implementer to use."

Plain `/subagent-driven-development` (Superpowers) always uses a Claude subagent as the implementer. This skill exists because that choice is otherwise silent — it asks up front whether to swap the implementer for `opencode-bridge` instead, while keeping every review gate from `subagent-driven-development` unchanged.

## Step 1: Ask which implementer to use

Ask via AskUserQuestion: "For this plan's implementer step, use a Claude subagent (Superpowers default) or delegate implementation to OpenCode via opencode-bridge?"

- **Claude subagent** → this skill is a pure passthrough: invoke `superpowers:subagent-driven-development` normally and stop here. Do not duplicate its logic.
- **OpenCode via opencode-bridge** → continue to Step 2.

## Step 2: Locate the review prompt templates

Find Superpowers' review templates (path is version-suffixed, so search rather than hardcode):
```bash
find ~/.claude/plugins -path "*subagent-driven-development/spec-reviewer-prompt.md" 2>/dev/null
find ~/.claude/plugins -path "*subagent-driven-development/code-quality-reviewer-prompt.md" 2>/dev/null
```
If either search returns nothing, stop and tell the user the Superpowers plugin isn't installed — this skill requires it for the review stage. If multiple matches, use the most recently modified file.

## Step 3: Read the plan, extract tasks

Same as `subagent-driven-development`: read the plan file once, extract full text and context for every task, create a TodoWrite entry per task. Do not re-read the plan file per task.

## Step 4: Per-task loop (OpenCode implementer, unchanged reviews)

For each task, in order:

1. **Implement via opencode-bridge**: run that skill's Step 0–3 flow (Step 0 will already be satisfied — this *is* the plan-execution context it checks for, so it should proceed straight to dispatch) with:
   - `--task` = the full task text + scene-setting context (same completeness bar as `subagent-driven-development`'s implementer-prompt: the subagent/OpenCode gets everything upfront, no plan-file reading)
   - `--repo` = the target repo absolute path
   - `--topic` = a stable per-task slug (e.g. `task-<n>-<short-name>`) — reuse this exact topic string for every dispatch related to this task, so opencode-bridge's session mapping reuses the same OpenCode session across fix rounds instead of losing context.
2. If `terminal_state` isn't `DONE`: surface `issues`/`files_changed` to the user exactly as opencode-bridge's own Step 3 describes (don't auto-retry past what opencode-bridge already tried; ask the user how to proceed). Do not advance to review.
3. **Spec-compliance review**: dispatch a fresh Claude subagent using the located `spec-reviewer-prompt.md` template, pointing it at the files OpenCode changed (`files_changed` from the handoff report) instead of a Claude implementer's own commit.
   - Issues found → feed the specific gaps back into another opencode-bridge dispatch (same `--topic`, so it's a continuation) asking OpenCode to fix exactly those gaps. Re-review. Repeat until compliant.
4. **Code-quality review**: once spec-compliant, dispatch a fresh Claude subagent using `code-quality-reviewer-prompt.md` against the same diff.
   - Issues found → same fix-via-opencode-bridge-retry loop as spec review, then re-review.
5. Mark the task complete in TodoWrite. Move to the next task.

## Step 5: Wrap up

Once all tasks are complete: dispatch a final code-reviewer subagent for the entire implementation (same as `subagent-driven-development`), then hand off to `superpowers:finishing-a-development-branch`.

## Rules (same spirit as subagent-driven-development's Red Flags)

- Never let an OpenCode-implemented task skip spec-compliance or code-quality review — that gap is exactly what this skill exists to close (see the opencode-bridge skill's own Step 0 warning about standalone use).
- Never dispatch multiple tasks' OpenCode implementations in parallel against the same repo (same conflict risk as parallel Claude implementer subagents).
- Keep `--topic` stable per task across all dispatch/fix-retry calls; use a new topic per task, never reuse one task's topic for another.
- If the user picks "Claude subagent" in Step 1, don't second-guess it later in the same run — the choice is per plan-execution, not per task.
