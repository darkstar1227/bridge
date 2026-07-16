# Gstack Handoff: OpenCode Bridge Skill (Phase 1)

_Source plan: /Users/ds-anxing/.gstack/projects/darkstar1227-bridge/ds-anxing-main-design-20260714-201742.md_
_Bridged: 2026-07-15_

## Overview

A Claude Code skill (`skills/opencode-bridge/`) that lets Claude Code delegate a coding task to OpenCode as a subagent, and reliably know when it's done, failed, or timed out — without building a custom HTTP client, poller, or session registry. It wraps OpenCode's own `opencode run --format json` CLI (which already emits a structured, typed JSON event stream and exits when finished) with a thin Python helper that adds only what OpenCode doesn't already provide: correct (repo, topic)-scoped session reuse, a model/fallback chain, and a structured handoff report shaped for downstream code review.

## Goal

Let Claude Code reliably learn when a delegated OpenCode task is done (or failed/timed out) and reuse the correct prior session for a given (repo, topic) — without re-injecting context every delegation, and without rebuilding infrastructure OpenCode's CLI already provides.

## Success Metrics

- Claude Code can dispatch a task to OpenCode via the skill and reliably learn when it's done, failed, or timed out — via `step_finish`/`reason` + process exit, never polling or guessing.
- Repeated delegations to the same (repo, topic) correctly reuse the *right* OpenCode session, not just "a recent one."
- If the default model fails or times out (and no files were mutated first), the skill automatically retries against the configured fallback model(s) before reporting failure.
- The entire implementation installs as a normal skill inside this `bridge` plugin repo, the same way every other skill here does.
- The skill's handoff report can be handed directly to `subagent-driven-development`'s `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md` steps (run in their existing sequential order, plus `/codex:review` as a third sequential step), or to `executing-plans`' per-batch reporting step, without those steps needing to know the implementer was OpenCode instead of a Claude subagent.

## Scope

- `skills/opencode-bridge/SKILL.md` — the skill definition (frontmatter, `allowed-tools`, `triggers`, per this repo's existing skill-authoring conventions).
- `skills/opencode-bridge/scripts/dispatch.py` — a Python helper (PEP 723 inline metadata, invoked via `uv run`) that:
  - Launches `opencode run --format json --session <id> -m <provider/model> --dir <repo>` as a subprocess in its own process group (`start_new_session=True`).
  - Parses the JSON event stream line-by-line for a terminal `step_finish` event with `reason:"stop"`.
  - Classifies every outcome as `DONE`, `FAILED` (with a specific reason), or `TIMED_OUT`.
  - Detects non-retryable failures (bad model name, auth failure, missing binary, permission denied, malformed args) vs. retryable/transient ones (connection failure, timeout, rate-limit) — only retryable failures ever trigger automatic retry/fallback.
  - Snapshots `git status --porcelain --untracked-files=all` before and after each dispatch (same mechanism serves both the mutation-guard and the files-changed report).
  - Short-circuits all automatic retry/fallback the moment the working tree shows any mutation — a partially-edited tree is returned to the caller as an explicit failure, never silently retried.
  - Maintains a `(repo, topic) -> session_id` mapping at `~/.opencode-bridge/state/sessions.json` (user-level, never committed to any repo) so repeated delegations reuse the correct session — never blind `-c`, and never a session_id whose (repo,topic) doesn't match the current dispatch.
  - Maintains model/fallback config at `~/.opencode-bridge/config.json` (also user-level).
  - Treats corrupted config/state files as: quarantine (rename to `<name>.corrupt-<timestamp>`), warn, then start fresh — never silently discard.
  - Enforces both a per-attempt timeout and a separate chain-level timeout (bounding total worst-case wall-clock time across all retry/fallback attempts).
  - Kills the entire process group (`os.killpg`) on any timeout, not just the immediate child (grandchild tool-call processes can outlive the immediate OpenCode process — verified against real OpenCode bugs, see Architecture Decisions).
  - Builds a structured handoff report: files changed, OpenCode's final text summary, test results (or explicitly "not reported by OpenCode" — never fabricated), and the session_id.
- SKILL.md-level interactive first-run setup: if `~/.opencode-bridge/config.json` is missing or fails to parse, Claude (not the Python script) asks the user for a default model + fallback list via AskUserQuestion, then writes the config once.
- SKILL.md wraps the `uv run scripts/dispatch.py ...` invocation in a shell `timeout` command slightly longer than the configured chain-level deadline, as an outer safety net independent of the Python process's own cleanup.
- Bump `.claude-plugin/plugin.json` version and update `README.md` to describe the new skill.

## Non-Goals

- **Background/async dispatch** (`Popen` instead of blocking `subprocess.run()`), **parallel independent-task dispatch**, **per-subagent process ownership of background processes**, **concurrent multi-reviewer aggregation** (`/codex:review` + spec-reviewer + code-quality-reviewer running at once), and a **wave-based DAG task scheduler** — all explicitly deferred to a separate "Phase 2" design that needs its own design pass, adversarial review, and live verification. Do not build any of this now.
- **Modifying `subagent-driven-development` or `executing-plans` themselves** (both live in the separate `superpowers` plugin) to automatically select OpenCode as an implementer. This skill only produces output shaped compatibly with those workflows' existing review steps; the user manually decides per-task whether to route to `/opencode-bridge`.
- **`/codex:review` as a concurrent reviewer** — only add it as a third *sequential* step after the existing two.
- Any GUI, dashboard, or session-tree visualization.
- Multi-tenant/shared-team usage — this is a personal, single-operator tool.
- A standalone Python package/repo — this ships as a skill inside the existing `bridge` plugin repo, not a separate distributable.

## Technical Constraints

- Language: Python (per this repo's `CLAUDE.md` convention: use `uv`/`uv run`, never bare `python`/`pip install`). `dispatch.py` must carry PEP 723 inline script metadata declaring its one dependency (`filelock`).
- Must not build a custom HTTP client, SSE client, polling loop, or session registry/policy engine — completion detection and session continuity are provided natively by the `opencode` CLI (verified: `opencode --version` reports v1.17.15 locally; `opencode run --format json` streams typed JSON events ending in `step_finish`/`reason:"stop"`; `--session <id>` correctly preserves conversation context — verified live in the source design).
- Runs inside this existing `bridge` Claude Code plugin repo (a markdown-skills-only repo today; this introduces its first Python code).
- Config and session-mapping state must live at the user level (`~/.opencode-bridge/`), never inside the `bridge` repo or any target repo (session IDs are machine-local; committing them would leak into version control).
- Must follow this repo's existing skill-authoring conventions (YAML frontmatter with `name`, `description`, `allowed-tools`, `triggers` — see CLAUDE.md's "Adding a new skill" section and any existing `skills/*/SKILL.md` for the pattern).

## Architecture Decisions

- **Dispatch flow** (already diagrammed in the source plan's "Dispatch Flow (Phase 1)" ASCII diagram): resolve session_id → subprocess launch with `--dir`/`--session`/`-m` → timeout/exit-code/JSON-parse classification → mutation-guard check → retry/fallback only if clean and retryable → build handoff report → return.
- **Retry + fallback algorithm**: for each model in the chain (default first, then fallbacks in order), one attempt; on a *retryable* failure with a *clean* working tree, retry the same model once using a **fresh temporary session** (never the mapping's persisted session_id — a failed session may be internally wedged); if that also fails cleanly, advance to the next model. A single mutation before any failure short-circuits the entire chain immediately — no further automatic attempts. The (repo,topic) mapping is only updated with a new session_id on eventual success.
- **Non-retryable failure taxonomy**: unknown/invalid model name, auth failure, missing `opencode` executable, permission denied, malformed CLI arguments — these fail immediately, no retry, regardless of mutation state. Retryable: connection failure, timeout-with-subprocess-alive, rate-limit responses. (Note: matching these categories against `opencode`'s actual error JSON shapes is still an open implementation task — see Open Questions.)
- **Process lifecycle**: launch with `start_new_session=True` (own process group); on timeout, `os.killpg()` the entire group, not just the immediate PID — verified necessary against two real, verified OpenCode GitHub issues (#8203: hangs forever on API errors; #17516, still open: hangs after tool calls complete due to a grandchild process outliving the parent). An outer shell `timeout` wrapper (in SKILL.md, around `uv run dispatch.py`) is a second layer of protection in case the Bash tool call itself is cancelled before Python's own cleanup runs.
- **Files-changed / mutation detection**: snapshot `git status --porcelain --untracked-files=all` (cwd = the target repo, same path passed via `--dir`) before and after dispatch; the diff between the two snapshots is used both as the mutation-guard signal and as the handoff report's files-changed list. (`git diff --stat` was considered and rejected — it misses untracked files and can't distinguish pre-existing changes from OpenCode's own.) **Verified live during the source design's eng review**: OpenCode does not isolate itself in a separate worktree/sandbox — a file it created showed up correctly in this snapshot taken in the caller's own cwd.
- **Session scoping — verified live, more nuanced than assumed**: passing a session_id across a *different* directory than where it was created **hung the OpenCode process indefinitely** (had to be killed after 60s, zero output) — this is a live reproduction of the same hang-bug class as #8203/#17516. Separately, `opencode session list` showed session storage is neither purely global nor strictly per-exact-directory — it appears bucketed by some workspace/repo identity, behaving inconsistently for non-git directories. **Implication for implementation**: `dispatch.py` must never pass a session_id whose original (repo,topic) doesn't match the current dispatch — treat any such mismatch as "no session" (create new) rather than ever attempting cross-context reuse, since it has been observed to hang rather than merely pick the wrong context.
- **Config/state placement**: model/fallback preferences are user-level (`~/.opencode-bridge/config.json`) since a user's model preference isn't tied to which repo they're bridging — deliberately not following this repo's `.bridge/email-config.json` per-target-repo precedent, which doesn't fit here. Session mapping is separate local ephemeral state (`~/.opencode-bridge/state/sessions.json`).
- **Malformed-state handling**: never silently treat a corrupt config/mapping file as "just start fresh" — quarantine it (rename with a timestamp suffix), surface a warning, then proceed with a fresh file. All writes use write-to-temp-file + atomic rename, never in-place edits.
- **Layering**: `dispatch.py` is a plain non-interactive Python script — it cannot invoke Claude's AskUserQuestion UI. All interactive first-run setup logic lives in `SKILL.md` at the Claude level; `dispatch.py`'s own job is narrow — validate config/state and fail deterministically with a clear error if either is missing/malformed, never prompt or guess.
- **Packaging**: PEP 723 inline script metadata (`# /// script` block, `dependencies = ["filelock"]`) at the top of `dispatch.py`; invoked via `uv run scripts/dispatch.py ...` — `uv` handles dependency installation automatically, consistent with this repo's existing Python convention (no `pyproject.toml`, no manual `pip install`).

## File Structure Assumptions

- `skills/opencode-bridge/SKILL.md` — [NEW] skill definition, frontmatter + instructions, including the interactive first-run config setup flow and the outer `timeout`-wrapped invocation of `dispatch.py`.
- `skills/opencode-bridge/scripts/dispatch.py` — [NEW] the Python helper implementing the full dispatch flow described above.
- `skills/opencode-bridge/scripts/tests/test_dispatch.py` — [NEW] pytest suite covering the codepaths enumerated in the source design's Test Review coverage diagram (see the companion test plan artifact below).
- `.claude-plugin/plugin.json` — [EXISTING] bump version per repo convention.
- `README.md` — [EXISTING] add a section describing the new skill; currently describes only gstack-bridge/email-digest/pipeline-review skills and would be misleading otherwise.
- `~/.opencode-bridge/config.json` — [NEW, outside this repo] user-level model/fallback config, created by the SKILL.md-level first-run setup flow, not checked into any repo.
- `~/.opencode-bridge/state/sessions.json` — [NEW, outside this repo] user-level (repo,topic)→session_id mapping, not checked into any repo.

## Proposed Implementation Areas

1. **`dispatch.py` core** — subprocess wrapper, process-group launch/kill, JSON event parsing and classification (DONE/FAILED/TIMED_OUT), non-retryable/retryable failure taxonomy, mutation-guard via git-status snapshots, retry/fallback algorithm with fresh-session-on-retry, per-attempt and chain-level timeouts. This is the highest-risk, highest-value area — everything else depends on its output shape and correctness.
2. **`dispatch.py` state/config layer** — PEP 723 metadata, `~/.opencode-bridge/config.json` and `~/.opencode-bridge/state/sessions.json` handling, quarantine-on-corrupt, atomic writes, filelock-guarded reads/writes. Separate concern from the core dispatch logic — different failure modes (I/O, parsing) vs. process/protocol concerns.
3. **`dispatch.py` handoff report** — building the structured report (files changed via git-status diff, OpenCode's final text, test results or "not reported", session_id) in the exact shape `subagent-driven-development`'s `implementer-prompt.md` contract expects (what was implemented / tested+results / files changed / self-review findings / issues). Depends on area 1's classification output.
4. **`SKILL.md`** — the Claude-facing instructions: interactive first-run config setup (AskUserQuestion-driven, writes once), invocation of `dispatch.py` via `uv run` wrapped in an outer shell `timeout`, and presenting the handoff report back to the calling context. Depends on area 3's finalized report schema.
5. **Repo metadata updates** — `.claude-plugin/plugin.json` version bump, `README.md` update. Independent of the above; can be done any time before landing.

## Verification Expectations

- Unit tests (pytest, per the source design's Test Plan Artifact at `~/.gstack/projects/darkstar1227-bridge/ds-anxing-main-eng-review-test-plan-20260715-123635.md`) covering: session resolution (found/missing/malformed mapping), command construction (`--dir`/`--session` always present), subprocess outcomes (zero-exit+step_finish, non-zero exit, TimeoutExpired+killpg, error-shaped JSON event, zero-exit-with-no-terminal-event), JSON parsing (well-formed vs. malformed-on-zero-exit vs. truncated-on-kill), retry/fallback (transient failure + clean tree → retry succeeds; retry fails → advances to next model; all models exhausted → FAILED with per-model reasons; mutation detected → short-circuits immediately, no auto-retry), handoff report construction (files changed populated correctly, test results "not reported" when absent, never fabricated), and config/state corruption handling (quarantine + fresh start, not silent discard).
- Manual test: delete `~/.opencode-bridge/config.json`, invoke the skill, confirm the interactive setup prompt appears exactly once and writes the config; invoke again and confirm no re-prompt.
- Manual test: dispatch twice to the same (repo, topic) and confirm the second call reuses the first call's session_id (no context re-injection) — mirroring the source design's live Test 2.
- Manual test: dispatch a task that creates a new file, confirm the handoff report's files-changed list includes it (untracked-file case, mirroring the source design's live Test A).
- Manual dry run: feed a real handoff report into `subagent-driven-development`'s `spec-reviewer-prompt.md` and confirm it can be reviewed without modification to that prompt.

## Open Questions / Explicit Assumptions

- [OPEN] Exact JSON/error shapes for the non-retryable vs. retryable failure taxonomy — needs empirical testing against `opencode run --format json` with induced failures (bad model name, forced auth error, missing binary, permission denied) before `dispatch.py`'s classification logic can be finalized. (Source design's Next Steps #1.)
- [OPEN] Exact handoff-report field names/schema — a small dataclass/dict (e.g. `implemented_summary`, `files_changed`, `test_results`, `self_review_notes`, `session_id`, `terminal_state`) needs to be nailed down against `subagent-driven-development`'s and `executing-plans`' real expectations before implementation, not decided in the abstract.
- [OPEN] Exact SKILL.md wording for the interactive first-run setup flow — the flow itself (check → ask via AskUserQuestion if missing/malformed → write once) is decided, but the literal skill text isn't drafted yet.
- [OPEN] Default per-attempt timeout and chain-level timeout values — not yet decided; must be configurable (same config file as model/fallback), not hardcoded, since task complexity varies.
- [OPEN] `/opencode-bridge`'s exact invocation surface from Claude's side (single blocking skill call vs. dispatch+check-status split) — current default assumption is a single blocking call since `subprocess.run()` is synchronous; only revisit if that proves unacceptably slow in real usage.
- [ASSUMPTION] The skill's slash-command name is `/opencode-bridge` — the source design uses this as a working name ("or similar") but it isn't finalized; confirm naming before writing SKILL.md frontmatter.
- [ASSUMPTION] `~/.opencode-bridge/` is an acceptable, non-conflicting location for user-level state — not verified against any existing tool/directory naming conflict on the user's machine.
