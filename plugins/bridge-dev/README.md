# bridge-dev

Development-workflow skills, anchored by bridging [gstack](https://github.com/garrytan/gstack) reviewed plans into [Superpowers](https://github.com/obra/superpowers) `writing-plans` format, plus pipeline orchestration, autoresearch experiment loops, OpenCode model benchmarking, update-email digests, and pipeline log review.

## What it does

gstack produces strategic plans reviewed by CEO / design / eng / DX lenses. Superpowers `writing-plans` needs execution-level specs: exact files, bite-sized tasks, test commands. This plugin bridges the gap.

**Workflow:**

```
/autoplan          → gstack reviews your plan
/bridge-dev:gstack-to-plan  → transforms it into a Superpowers-compatible spec
                         → auto-invokes superpowers:writing-plans
/superpowers:executing-plans  → implement
```

## Skills

### `/bridge-dev:gstack-to-plan`

Reads the latest gstack-approved plan from your project, extracts structured information (goal, scope, constraints, architecture decisions), produces a Superpowers-compatible handoff doc, and invokes `superpowers:writing-plans`.

**Triggers:**
- `/bridge-dev:gstack-to-plan`
- "bridge plan"
- "gstack to plan"
- "convert gstack plan"
- "handoff to superpowers"

### `/bridge-dev:init-project`

Detects a project's stack (Python/uv, Docker, Supabase, Git) and initializes or audits it against standard conventions — ruff/PEP8, docker-compose profiles that never recreate stateful services, Supabase migrations, `.env`/`.env.example` hygiene, commit and branch naming, and folder layout — then writes the result into a managed block in the project's `CLAUDE.md`. Each module is independently optional based on what's actually detected; folder moves always require confirmation before executing. Finishes by running `claude-md-management:claude-md-improver` as a read-only quality pass and writes a full report to `docs/init-project-report-YYYY-MM-DD.md`.

**Triggers:**
- `/bridge-dev:init-project`
- "initialize project"
- "init project"
- "setup my project"
- "check my project setup"
- "project checkup"

### `/bridge-dev:setup-email-updates`

Creates or edits the `.bridge/email-config.json` a repo needs before `/bridge-dev:send-update-email` will work — who gets notified, and (on first setup) registers a dedicated `resend-<repo-slug>` MCP connection with its own sender name, so each repo sends under its own identity. Works on a single repo, or in bulk when run from a parent folder containing multiple repos (asks one repo at a time). Interactive by design — not meant to run under `/loop`. Requires `RESEND_API_KEY` in your environment at setup time only.

**Triggers:**
- `/bridge-dev:setup-email-updates`
- "setup email updates"
- "configure update email recipients"
- "init bridge email config"

### `/bridge-dev:send-update-email`

Sends a readable, bullet-point update email via [Resend](https://resend.com) for a single repo, summarizing everything it shipped since the last send — grouped by version and by root cause, not listed commit-by-commit. Renders the email and shows it to you for confirmation before sending anything. Run manually, e.g. near the end of a session. Sends through this repo's own `resend-<repo-slug>` MCP connection (registered by `/bridge-dev:setup-email-updates`) — this skill never holds an API key or a sender address itself.

**Triggers:**
- `/bridge-dev:send-update-email`
- "send update email"
- "email changelog"
- "notify team of updates"

### `/bridge-dev:opencode-bridge`

Delegates a coding task to [OpenCode](https://opencode.ai) and gets back a structured handoff report — done/failed/timed-out, files changed, implementation summary — using OpenCode's own CLI (`opencode run --format json`) instead of custom polling/HTTP/registry infrastructure. Wraps the OpenCode subprocess in its own process group, classifies the outcome from OpenCode's JSON event stream (not just its exit code — a bad model name or auth failure both exit 0), guards against retrying once files have already been mutated, retries/falls back across a configured model chain for safe/transient failures, and manages a `(repo, topic) → session_id` mapping so follow-up dispatches resume the same OpenCode session. First run prompts once (via `AskUserQuestion`) for a default model, fallback models, and per-attempt/chain timeouts, written to `~/.opencode-bridge/config.json`. Useful as an OpenCode-backed implementer step inside `subagent-driven-development` or `executing-plans`.

**Triggers:**
- `/bridge-dev:opencode-bridge`
- "delegate to opencode"
- "use opencode for this task"
- "opencode bridge"

### `/bridge-dev:setup-relay-provider-template`

Wires [cancerfreebiotech/claude-profile-kit](https://github.com/cancerfreebiotech/claude-profile-kit)'s `claude-project-template` (orchestrator + 7 specialized subagents + native advisor) into the current project, driven entirely by an already-configured [`relay`](https://github.com/darkstar1227/relay) LiteLLM provider — queries the provider's gateway for its real model list, assigns a model per role by tier (heavy/mid/light), and writes every file (`CLAUDE.md`, `.claude/agents/*.md`, `.claude/settings.json`) without hand-editing anything. Refuses to proceed if the provider has `--subagent-model` set, since that would clobber every subagent's per-role model. Shows the full role → model mapping before writing and gives you a chance to redirect it.

**Triggers:**
- `/bridge-dev:setup-relay-provider-template`
- "setup relay provider template"
- "apply claude-project-template with relay"
- "relay provider template"

### `/bridge-dev:agy-second-voice`

Gets an independent, read-only second opinion from Antigravity CLI (`agy`, Google's coding agent) — review the current diff, adversarially challenge it, or consult it on a question/plan — as a cross-model check alongside Claude's own analysis. Read-only by design: never passes `--dangerously-skip-permissions`, so any write/delete/execute `agy` attempts is auto-denied. For a write-capable delegate, use `opencode-bridge` instead.

**Triggers:**
- "agy review"
- "agy challenge"
- "ask agy"
- "antigravity review"
- "second voice" / "second opinion"

### `/bridge-dev:autoresearch-plan`

Runs a Karpathy-autoresearch-style comparative experiment loop over candidate technical approaches (API designs, algorithms, data-flow strategies) after a plan has been reviewed but before it's handed to an implementer. Picks a winning approach against an explicit metric and records the baseline, logged to `docs/autoresearch/plan/`, so downstream implementation isn't built on an unvalidated guess.

**Triggers:**
- "autoresearch plan"
- "compare candidate approaches"
- "spike before implementing"
- "test approaches experimentally"
- "karpathy autoresearch plan"

### `/bridge-dev:autoresearch-impl`

Runs a Karpathy-autoresearch-style keep-or-discard iteration loop over an already-implemented branch — propose one variant, run it against tests/benchmarks, keep it if the metric improves or discard and revert, repeat within a fixed budget, logged to `docs/autoresearch/impl/` — before handing off to code-review/QA. Use after `subagent-driven-development` (or `opencode-subagent-driven-development`) finishes a task.

**Triggers:**
- "autoresearch implementation"
- "iterate on implementation before review"
- "benchmark implementation variants"
- "try a few variants and keep the best"
- "karpathy autoresearch impl"

### `/bridge-dev:benchmark-opencode-models`

Deep-benchmarks which OpenCode models are actually viable for `opencode-bridge` — pings each candidate model, then runs 5 canned superpowers-style task prompts per model (feature vs bugfix, short vs detailed, plus a dedicated TDD red-to-green prompt), independently verifies every result by executing the generated code (never trusts OpenCode's self-reported "done"), and scores each run on time/quality/completeness/autonomy/discipline/red-green-accuracy/test-call-discipline. Reports to `docs/opencode-model-tests/`. For a fast pass/fail availability check with no scoring, use `check-opencode-models` instead.

**Triggers:**
- "benchmark opencode models"
- "deep test opencode models"
- "which opencode models actually work"
- "smoke test opencode-bridge models"
- "tdd test opencode models"

### `/bridge-dev:check-opencode-models`

Fast two-stage check for a list of OpenCode models — ping (reachability/auth) followed by one real, minimal single-shot prompt test to catch models that ping fine but are actually slow or wrong under real dispatch. Reports which models are usable right now vs. reachable-but-slow vs. reachable-but-wrong vs. unreachable. Lighter than a full benchmark.

**Triggers:**
- "check opencode models"
- "is this opencode model available"
- "is this opencode model too slow"
- "ping opencode models"
- "which opencode models are up right now"

### `/bridge-dev:full-pipeline`

Orchestrates the user's full end-to-end workflow in order — gstack office-hours, autoplan, autoresearch-plan, superpowers writing-plans and subagent-driven-development, autoresearch-impl, code-review, and qa — invoking each skill in sequence and handing its output forward as the next step's input. At two fixed checkpoints (after the plan is locked, and after implementation lands) it judges whether the change touches database schema and if so invokes `supabase:supabase-postgres-best-practices` before continuing.

**Triggers:**
- "run the full pipeline"
- "full workflow from office hours to qa"
- "chain the whole pipeline"
- "go from idea to shipped"
- "orchestrate the entire flow"

### `/bridge-dev:superpowers-pipeline`

A lighter orchestrator than `full-pipeline` — chains only the core Superpowers loop (writing-plans, subagent-driven-development, finishing-a-development-branch) without gstack's office-hours/autoplan or the autoresearch experiment steps, for when a spec already exists or gstack-level planning isn't wanted. Still judges at two checkpoints whether the change touches database schema and invokes `supabase:supabase-postgres-best-practices` if so.

**Triggers:**
- "just the superpowers pipeline"
- "superpowers only flow"
- "skip gstack go straight to implementation"
- "writing plans to finishing branch"

### `/bridge-dev:opencode-subagent-driven-development`

Wraps Superpowers' `subagent-driven-development` plan-execution loop, asking upfront whether the implementer step should be a Claude subagent (default) or OpenCode via `opencode-bridge` — spec-compliance and code-quality review stay identical either way.

**Triggers:**
- "subagent driven development with opencode"
- "opencode subagent driven development"
- "use opencode as implementer"

### `/bridge-dev:review-pipeline-logs`

Queries a project's local log files and reviews whether a just-developed application pipeline actually ran the way it was designed to. Reads the project's design/plan doc for the expected steps, parses the relevant log file(s), then checks the run against the plan step-by-step, flags errors/exceptions, judges whether logging is detailed and leveled clearly enough to debug from, and confirms output values matched expectations. Produces a detailed report to `docs/pipeline-reviews/` — not just a pass/fail line.

**Triggers:**
- "review pipeline logs" / "check pipeline logs" / "review the logs"
- "is the pipeline correct"
- "查詢 logs" / "log 有沒有跑對" / "review pipeline log對不對"
- "pipeline log review"

### `/bridge-dev:setup-env`

Exports the user-scope Claude Code plugins, marketplaces, and gstack installation on this machine into a portable manifest at `docs/env-setup/claude-plugins-manifest.json`, or installs from an existing manifest onto a new machine to reproduce the same Claude Code environment.

**Triggers:**
- "export my plugins"
- "back up my claude code setup"
- "install my plugins on a new machine"
- "replicate my claude code environment"
- "bootstrap this machine's claude code setup"
- "sync plugins to new machine"

## Requirements

- [gstack](https://github.com/garrytan/gstack) — for `/autoplan`
- [superpowers](https://github.com/obra/superpowers) — for `writing-plans`
- [Resend](https://resend.com) account and API key, plus [`resend-mcp`](https://github.com/resend/resend-mcp) available via `npx` — for `/bridge-dev:setup-email-updates`, which registers one dedicated MCP connection per repo (`send-update-email` doesn't need an API key itself)
- [`opencode`](https://opencode.ai) CLI on `PATH`, plus [`uv`](https://docs.astral.sh/uv/) — for `/bridge-dev:opencode-bridge`
- [`relay`](https://github.com/darkstar1227/relay) CLI with a configured LiteLLM provider (no `--subagent-model` set) — for `/bridge-dev:setup-relay-provider-template`
