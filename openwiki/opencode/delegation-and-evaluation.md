---
type: Integration Guide
title: OpenCode delegation and evaluation
description: "Guarded OpenCode task delegation, session and retry behavior, and the repository's fast availability checks and deep model benchmark workflow."
resource: skills/opencode-bridge/scripts/dispatch.py
tags: [opencode, delegation, evaluation, python, testing]
---

# OpenCode delegation and evaluation

## Role in Bridge

Bridge offers OpenCode as a guarded coding implementer rather than treating a CLI exit code as sufficient evidence of success. This subsystem **depends on** [the plugin and skill model](../architecture/plugin-and-skill-model.md) for interactive setup and operator-facing safety rules, and it **is selected from** [planning and pipeline workflows](../workflows/planning-and-pipelines.md) when a user chooses OpenCode in the Superpowers implementation loop.

The bare `bridge:opencode-bridge` skill performs delegation and returns a handoff report. It deliberately has no specification-compliance or code-quality review. For plan execution, `bridge:opencode-subagent-driven-development` is the integration point that retains those review gates while choosing OpenCode as the implementer.

## Configuration and state

The skill’s first-run flow writes a user-scoped `~/.opencode-bridge/config.json` with a default model, ordered fallbacks, per-attempt timeout, chain timeout, and ping timeout. The helper reads it and reports `CONFIG_ERROR` when required configuration is missing or malformed.

Session mappings are stored separately at `~/.opencode-bridge/state/sessions.json`, keyed by `(repo, topic)`. In [`dispatch.py`](../../skills/opencode-bridge/scripts/dispatch.py), file locking prevents concurrent map updates, writes use a temporary file and atomic replacement, and corrupt JSON is quarantined under a timestamped name. This avoids cross-task session reuse and makes broken local state recoverable.

## Dispatch lifecycle

For each configured model, the helper:

1. Runs a cheap `opencode run --format json` ping in a temporary directory, with a no-file-access prompt. Ping failures skip the real task for that model.
2. Snapshots `git status --porcelain --untracked-files=all` in the target repository.
3. Invokes `opencode run <task> --format json -m <model> --dir <repo>`, using a matching session only for the first configured model’s initial attempt.
4. Requires a JSON `step_finish` event whose reason is `stop`; a zero process exit by itself is not success.
5. On a timeout, kills and reaps the subprocess process group, avoiding child-process leakage.
6. After a failed attempt, compares the git snapshots. Any mutation stops automatic retry/fallback and reports the partial files.
7. When the tree remains clean, retries transient failure classes once and then moves through fallbacks within the chain deadline. Invalid models, auth, missing executable, and permission failures are non-retryable; connection, timeout, and rate-limit signals are retryable.

A successful report includes `DONE`, final implementation text, changed files, a narrowly parsed test result when present, and the session ID. Failure reports include terminal state, issue text, partial changed files, and session ID. The helper’s comments record why event-stream inspection is necessary: OpenCode can emit error events while returning exit code zero.

The user-facing skill also checks whether an ad-hoc caller should instead use the review-preserving wrapper, offers to allow `Bash(uv run *)` locally, and prohibits simultaneous dispatches into the same worktree without worktree/subagent isolation. Sources: [`skills/opencode-bridge/SKILL.md`](../../skills/opencode-bridge/SKILL.md) and [`skills/opencode-bridge/scripts/dispatch.py`](../../skills/opencode-bridge/scripts/dispatch.py).

## Model evaluation: fast check vs. benchmark

Use the two model-testing skills for different questions:

| Tool | Question answered | Method | Artifact |
| --- | --- | --- | --- |
| `check-opencode-models` | Is a model reachable, correct on a minimal coding task, and not slow right now? | Temporary-repo ping plus a real `calc.py` `add_one(x)` edit, independently imported and asserted. | Optional JSON output; terminal-only without `--out`. |
| `benchmark-opencode-models` | How does a model behave across realistic task shapes and protocol constraints? | Five isolated repositories per model: short/detailed feature, short/detailed bugfix, and explicit red-to-green TDD; independent acceptance checks never trust a `DONE` report alone. | Incrementally written JSON under `docs/opencode-model-tests/`. |

The availability script defaults to a 30-second ping, 150-second prompt test, and a 45-second slow threshold. The benchmark captures elapsed time, changed/unexpected files, no-op detection, independent acceptance results, issues, and deterministic quality/completeness/autonomy/discipline/TDD scores. The benchmark’s model-level tests remain sequential, even where current worktree changes add inter-model concurrency.

The fast check and benchmark both reuse dispatch primitives, so a change to command construction, JSON classification, or timeouts can affect operational delegation and testing. Sources: [`skills/check-opencode-models/SKILL.md`](../../skills/check-opencode-models/SKILL.md), [`skills/check-opencode-models/scripts/check.py`](../../skills/check-opencode-models/scripts/check.py), [`skills/benchmark-opencode-models/SKILL.md`](../../skills/benchmark-opencode-models/SKILL.md), and [`skills/benchmark-opencode-models/scripts/smoke_test.py`](../../skills/benchmark-opencode-models/scripts/smoke_test.py).

## Verification and change checklist

The dispatcher test suite at [`skills/opencode-bridge/scripts/tests/test_dispatch.py`](../../skills/opencode-bridge/scripts/tests/test_dispatch.py) covers JSON/config recovery, atomic writes, scoped session lookup, command creation, ping isolation, event parsing, failure classes, process-group timeout cleanup, retry/fallback behavior, mutation stops, and handoff reports. Run:

```bash
cd skills/opencode-bridge/scripts
uv run pytest tests/test_dispatch.py -v
```

When modifying this area:

- Never relax the mutation guard or treat a zero exit code as sufficient success.
- Keep session reuse constrained to the exact repository/topic key.
- Preserve the distinction between bare delegation and the wrapper with review gates.
- Independently validate generated code in model checks; do not rely on model self-report.
- Treat concurrency changes as worktree-safety changes, especially where multiple model tests or dispatches may run at once.
