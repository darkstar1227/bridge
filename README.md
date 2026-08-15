# bridge

A Claude Code marketplace. Its first plugin, **`bridge-dev`**, bridges [gstack](https://github.com/garrytan/gstack) reviewed plans into [Superpowers](https://github.com/obra/superpowers) `writing-plans` format, plus a set of related development-workflow skills. Future skill series live here as additional, separately installable plugins.

## What it does

gstack produces strategic plans reviewed by CEO / design / eng / DX lenses. Superpowers `writing-plans` needs execution-level specs: exact files, bite-sized tasks, test commands. This plugin bridges the gap.

**Workflow:**

```
/autoplan          → gstack reviews your plan
/bridge-dev:gstack-to-plan  → transforms it into a Superpowers-compatible spec
                         → auto-invokes superpowers:writing-plans
/superpowers:executing-plans  → implement
```

## Install

### Via Claude marketplace (GitHub URL)

```
/plugin install https://github.com/darkstar1227/bridge
```

### Manual

Add this repo as a marketplace in Claude Code settings, then install the `bridge-dev` plugin — this marketplace can host other skill series alongside it later, each installable independently.

## Skills (`bridge-dev` series)

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

## Requirements

- [gstack](https://github.com/garrytan/gstack) — for `/autoplan`
- [superpowers](https://github.com/obra/superpowers) — for `writing-plans`
- [Resend](https://resend.com) account and API key, plus [`resend-mcp`](https://github.com/resend/resend-mcp) available via `npx` — for `/bridge-dev:setup-email-updates`, which registers one dedicated MCP connection per repo (`send-update-email` doesn't need an API key itself)
- [`opencode`](https://opencode.ai) CLI on `PATH`, plus [`uv`](https://docs.astral.sh/uv/) — for `/bridge-dev:opencode-bridge`
- [`relay`](https://github.com/darkstar1227/relay) CLI with a configured LiteLLM provider (no `--subagent-model` set) — for `/bridge-dev:setup-relay-provider-template`

## License

MIT
