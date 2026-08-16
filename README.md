# bridge

A Claude Code marketplace hosting three independently installable plugins: **`bridge-dev`** (development-workflow skills, anchored by bridging [gstack](https://github.com/garrytan/gstack) reviewed plans into [Superpowers](https://github.com/obra/superpowers) `writing-plans` format), **`bridge-fin`** (financial-workflow skills), and **`bridge-mind`** (ESTP-tuned decision-support skills). Future skill series live here as additional plugins.

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

Add this repo as a marketplace in Claude Code settings, then install `bridge-dev`, `bridge-fin`, and/or `bridge-mind` independently — each is a separately installable plugin.

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

Designed around the ESTP cognitive-function stack: Se (extraverted sensing, live in the moment, grab concrete data) → Ti (introverted thinking, fast logical breakdown) → Fe (extraverted feeling) → Ni (introverted intuition, weakest, used last). This ordering means an ESTP thinker naturally acts first and thinks while doing, resists getting stuck in abstract planning, and prefers reasoning backward from empirical results over building a complete theory before executing. Combined with a DevOps/LLM/quant-trading background, the problem these skills solve is: in situations that call for careful planning, long-horizon thinking, or counter-intuitive decisions, structured skills force in the steps an ESTP naturally tends to skip — upfront risk assessment, delayed-gratification-style compound learning, trade-offs that don't pay off immediately.

Fully autonomous, no slash command needed to trigger — Claude loads only each skill's `name` + `description` (~100 tokens) at startup, and only reads the full `SKILL.md` when a request matches that description ("progressive disclosure"). So each skill's `description` is written to be precise enough that it actually fires in the real situations it's meant for. Each one leans into or braces against a specific part of the Se → Ti → Fe → Ni stack: fast empirical validation where Se/Ti strengths shine, structured checklists where Ni (long-horizon planning) is naturally weak.

Two cross-cutting properties apply to every skill in this series:

- **Bilingual triggering.** Each `description` carries both English and Traditional Chinese phrasings, so a skill fires on 「要部署了」 as reliably as on "about to deploy". A risk check that only recognizes English is a risk check that misses the half of your sentences that aren't.
- **Exempt from compression modes.** Every skill explicitly overrides any active terseness style (caveman mode or similar) for its own output. Compression is right for machine-facing text and wrong here: an ambiguous risk warning is worse than none, and a curt tone-check rewrite reproduces the exact defect it exists to catch. Structural compactness (fixed verdict blocks, tables) is kept; grammatical compression is not.

### `bridge-mind:rapid-prototype-thinking`

For technical evaluations (new APIs, frameworks, K8s configs, cheap-to-reverse architecture options). Replaces theoretical "in theory this should work" answers with the smallest runnable experiment that produces observable proof, converging by elimination instead of expanding every branch at once. Splits from `system-design-devil-advocate` on **cost to reverse**, not topic — cheap to undo lands here, expensive to undo lands there.

**Triggers:** "should I try this", "is this approach viable", "let's do a quick POC", "which option is better", "does this design look right" · 「這樣可行嗎」「快速試試看」「哪個比較好」「這設計對嗎」

### `bridge-mind:risk-brake-thinking`

Checklist before irreversible actions — production deploys, DB migrations, force-pushes, or taking a trading strategy live. Forces reversibility check, worst-case quantification, and a rollback plan before an execution plan, then emits a fixed 5-field verdict block scannable in seconds.

Three mechanisms keep it from being either ignorable or annoying:

- **A `PreToolUse` guard** (`hooks/risk-brake-guard.sh`) matches Bash commands against seven irreversible-action classes (`trade`, `destructive-sql`, `migration`, `deploy`, `force-push`, `publish`, `delete`) and injects context telling Claude to run the skill. Deterministic where description-matching is probabilistic — and **non-blocking**, so it never stalls an unattended `/loop` waiting on an answer nobody is there to give.
- **A decision journal** at `.bridge/decisions.jsonl` (gitignored) records every warning, override, and eventual outcome. The skill reads it first: overridden three times in a class with no bad outcome and it backs off; a real past failure and it leads with that record. ESTPs update on experience, not argument — so the log becomes the only argument that reliably lands.
- **A push-back rule**: state the worst case once, then comply. Never repeat a warning already given in the same session. One warning is a signal; two is noise, and a muted skill protects nothing.

**Triggers:** "about to deploy", "about to place the order", "about to migrate", "taking this strategy live", "ship it" · 「要部署了」「要下單」「要跑 migration」「這個策略要進實盤」「直接推上去」

### `bridge-mind:compound-learning-tracker`

For long-horizon skill learning (music theory, Rust, quant trading, an instrument) that hits a plateau. Measures **first** — commit counts, diff sizes, backtest outputs over a 2-week window — before asking how it's been going, since the gut feeling is the thing under investigation and can't also be the evidence. Separates real stagnation from perceived stagnation (the common case), redesigns the feedback loop to surface a visible result within 3 days, and allows lateral pivots instead of full abandonment.

**Triggers:** "I can't keep going with this", "feels like no progress", "should I switch methods", "is this exercise even useful" · 「卡住了」「沒進步」「練不下去」「要不要換方法」

### `bridge-mind:system-design-devil-advocate`

Plays skeptic on designs that are expensive to reverse (data models, service boundaries, public API contracts, deployment topologies) instead of agreeing with the user's excitement — stress-tests from a "maintaining this in six months" vantage point, surfacing only the 1-2 most painful issues with a concrete minimal-change fix. Explicitly stands down for cheap-to-reverse decisions, for settled decisions the user is now implementing, and for anything already mid-execution (that's `risk-brake-thinking`).

**Triggers:** "I'm planning to design it this way", "here's the architecture diagram", "should I split this into multiple services" · 「我打算這樣設計」「要不要拆服務」「這個 schema 這樣設計」

### `bridge-mind:unfinished-work-audit`

Counters Se novelty-chase — the pull toward whatever is newest and most stimulating, which makes the design phase compelling and the finishing phase not. Gathers hard evidence (unmerged and stale branches, untracked files, uncommitted work, stale TODO markers) and cross-references committed design specs against the codebase to find **specs with no implementation** — the most deceptive item in the audit, because the commit log reads as if something shipped.

Each item gets a **ship / kill / park** recommendation, where killing counts explicitly as a success outcome, and a WIP ceiling of 3 open threads is enforced. Doesn't moralize about discipline and doesn't block starting something new — it shows the pile, asks one question, and respects the answer.

**Triggers:** "what should I work on", "what's still open", "did I finish that", "I have too many things going", "let's start something new" · 「還有什麼沒做完」「東西太多了」「那個做完了嗎」「來做個新的」

### `bridge-mind:tone-check-before-send`

Covers the tertiary-Fe blind spot: under time pressure or deep technical focus, delivery drops out and what remains is Ti's raw correctness, landing far harder than intended. The author can't detect this from the inside — the text reads as merely efficient to whoever wrote it, because they have the friendly intent and the recipient has only the words.

A translation layer, not a politeness lecture: **every technical claim survives at full strength**, only delivery changes — softening a correct objection into vagueness would be a worse failure than bluntness. Scores how the draft lands (collaborative / neutral / blunt / harsh), stays silent when it's already fine, and returns finished sendable text rather than a list of suggestions. Runs on outward-facing text only; skips private notes entirely.

**Triggers:** "review this PR", "leave a comment", "reply to this", "how does this sound", "push back on this" · 「幫我回這個」「這樣回可以嗎」「寄給他」「這樣講會不會太兇」

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
