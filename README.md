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

## Skills (`bridge-fin` series)

### `/bridge-fin:setup-finance-sources`

Creates or edits `.bridge/finance-config.json` — the market/account data sources `market-account-report`, `valuation-model`, and `strategy-backtest` all need: an MCP connection (e.g. [`okx-agent-trade-kit`](https://github.com/okx) for crypto, [`FinMind-MCP`](https://github.com/FinMind/FinMind-MCP) — FinMind's own official MCP — for TW 台股 fundamentals/candles), a direct HTTP API (Finnhub for US equities, called directly since there's no single official Finnhub MCP), or a local Python package (`yfinance`, for historical US-equity candles where Finnhub's free tier restricts them) — plus a base currency and default watchlist. Also documents Fugle/`shioaji`/Alpha Vantage/Polygon.io as options for when you already have an account with one. Gitignores the config since an `http` source can hold a plaintext token.

**Triggers:**
- `/bridge-fin:setup-finance-sources`
- "setup finance sources"
- "configure finance data sources"
- "init bridge finance config"

### `/bridge-fin:market-account-report`

Pulls balances, positions, and activity from whatever sources `.bridge/finance-config.json` names, shapes them into the [`anthropics/financial-services`](https://github.com/anthropics/financial-services) `wealth-management` vertical's `client-report` input contract, writes the handoff to `docs/finance/reports/`, then invokes `/client-report` — or renders the same content directly if that plugin isn't installed.

**Triggers:**
- `/bridge-fin:market-account-report`
- "market account report"
- "financial account report"
- "portfolio report"
- "generate client report"

### `/bridge-fin:valuation-model`

Checks whether a ticker/asset is even DCF-shaped (refuses to fabricate cash flows for a pure token/commodity), pulls whatever market data is locally available from connected sources, gathers growth assumptions from you, writes the handoff to `docs/finance/valuations/`, then invokes the `financial-analysis` core plugin's `dcf-model` (`/dcf`) — which sources everything else itself (SEC EDGAR, Daloopa, web search).

**Triggers:**
- `/bridge-fin:valuation-model`
- "valuation model"
- "build a dcf"
- "dcf valuation"
- "financial model for"

### `/bridge-fin:strategy-backtest`

Pulls historical candles from a configured source and backtests a simple rule-based long/flat strategy (SMA crossover or RSI threshold) via a sandboxed `uv run` script (`plugins/bridge-fin/skills/strategy-backtest/scripts/backtest.py`), reporting CAGR, Sharpe, max drawdown, win rate, and trade count to `docs/finance/backtests/`. No official `financial-services` skill covers backtesting, so this one is standalone. Simulation-only — never places live orders, even on a connection that also exposes trade-execution tools.

**Triggers:**
- `/bridge-fin:strategy-backtest`
- "strategy backtest"
- "backtest my strategy"
- "trading strategy performance"

### `/bridge-fin:finnhub-query`

Owns every direct call to [Finnhub](https://finnhub.io)'s REST API (quote, company profile, basic financials, historical candles, company news) in one place — endpoint shapes, auth, and error handling (including the free-tier `/stock/candle` restriction) — using the `finnhub` source in `.bridge/finance-config.json`. `market-account-report`, `valuation-model`, and `strategy-backtest` invoke this skill instead of each building their own curl calls, so a Finnhub API change only needs fixing here.

**Triggers:**
- `/bridge-fin:finnhub-query`
- "query finnhub"
- "finnhub quote"
- "finnhub api"
- "finnhub candles"

## Skills (`bridge-mind` series)

ESTP-tuned decision-support skills — fully autonomous, no slash command needed to trigger. Each one leans into or braces against a specific part of the Se → Ti → Fe → Ni function stack: fast empirical validation where Se/Ti strengths shine, structured checklists where Ni (long-horizon planning) is naturally weak.

### `bridge-mind:rapid-prototype-thinking`

For technical evaluations (new APIs, frameworks, K8s configs, architecture options). Replaces theoretical "in theory this should work" answers with the smallest runnable experiment that produces observable proof, converging by elimination instead of expanding every branch at once.

**Triggers:** "should I try this", "is this approach viable", "let's do a quick POC", "which option is better", "does this design look right"

### `bridge-mind:risk-brake-thinking`

Mandatory checklist before irreversible actions — production deploys, DB migrations, or taking a trading strategy live. Forces reversibility check, worst-case quantification, and a rollback plan before an execution plan, plus a delayed-gratification check when the user is in a hurry.

**Triggers:** "about to deploy", "about to place the order", "about to delete", "about to migrate", "taking this strategy live"

### `bridge-mind:compound-learning-tracker`

For long-horizon skill learning (music theory, Rust, quant trading, an instrument) that hits a plateau. Diagnoses real vs. perceived stagnation against concrete output, redesigns the feedback loop to surface a visible result within days, and allows lateral pivots instead of full abandonment.

**Triggers:** "I can't keep going with this", "feels like no progress", "should I switch methods", "is this exercise even useful"

### `bridge-mind:system-design-devil-advocate`

Plays skeptic on new system/architecture designs (K8s topology, microservice splits, agent architectures) instead of agreeing with the user's excitement — stress-tests the design from a "maintaining this in six months" vantage point, surfacing only the 1-2 most painful issues with a concrete minimal-change fix.

**Triggers:** "I'm planning to design it this way", "here's the architecture diagram", "should I split this into multiple services"

## Requirements

- [gstack](https://github.com/garrytan/gstack) — for `/autoplan`
- [superpowers](https://github.com/obra/superpowers) — for `writing-plans`
- [Resend](https://resend.com) account and API key, plus [`resend-mcp`](https://github.com/resend/resend-mcp) available via `npx` — for `/bridge-dev:setup-email-updates`, which registers one dedicated MCP connection per repo (`send-update-email` doesn't need an API key itself)
- [`opencode`](https://opencode.ai) CLI on `PATH`, plus [`uv`](https://docs.astral.sh/uv/) — for `/bridge-dev:opencode-bridge`
- [`relay`](https://github.com/darkstar1227/relay) CLI with a configured LiteLLM provider (no `--subagent-model` set) — for `/bridge-dev:setup-relay-provider-template`
- At least one market/account data source, plus [`uv`](https://docs.astral.sh/uv/) — for the financial series (`/bridge-fin:setup-finance-sources`, `/bridge-fin:market-account-report`, `/bridge-fin:valuation-model`, `/bridge-fin:strategy-backtest`). Any combination works: an MCP connection (e.g. `okx-agent-trade-kit` for crypto accounts, [`FinMind-MCP`](https://github.com/FinMind/FinMind-MCP) with a `FINMIND_TOKEN` for TW equities) registered via `claude mcp add`/`/mcp`; a Finnhub API key for direct-HTTP US-equity quotes; or nothing extra at all for `yfinance`-based historical US-equity candles (`uv run --with yfinance ...`, no key needed)
- [`anthropics/financial-services`](https://github.com/anthropics/financial-services) marketplace, with the `financial-analysis` core plugin and the `wealth-management` vertical installed — for `/bridge-fin:market-account-report` and `/bridge-fin:valuation-model` to hand off to `/client-report`/`/dcf` (optional: both skills still produce a standalone handoff/report without it)

## License

MIT
