# TODOS

## OpenCode Bridge — Phase 2 (background execution, parallel dispatch, wave scheduling)

**What:** Background/async OpenCode dispatch, parallel independent-task execution for `subagent-driven-development`, per-subagent process ownership, concurrent multi-reviewer aggregation (`/codex:review` + spec-reviewer + code-quality-reviewer at once), and a wave-based DAG scheduler for grouping tasks by dependency/file-overlap.

**Why:** Phase 1 (`skills/opencode-bridge/`) ships single, sequential, synchronous OpenCode dispatch only. The user wants richer concurrent delegation later, but two independent adversarial reviews found the concurrency design was drifting back into the exact orchestrator complexity (poller, registry, process supervisor) that Phase 1 exists to avoid — with none of Phase 1's live-verification rigor behind it.

**Context:** Full direction (not a committed spec) is captured in the "Phase 2 — Deferred" section of `~/.gstack/projects/darkstar1227-bridge/ds-anxing-main-design-20260714-201742.md`. Concrete open problems: async completion detection without it just being a renamed polling loop, safe orphan-process cleanup across subagent lifecycles, session-mapping correctness under concurrency, and a mutation-safety story for concurrent reviewers touching a shared working tree.

**Depends on / blocked by:** Phase 1 must ship and be used for real first — the design explicitly wants usage data before committing to Phase 2's scope, not a scope decision made in the abstract.
