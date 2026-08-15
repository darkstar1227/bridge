# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **marketplace** (not a single plugin). It currently hosts two installable plugins:
- `bridge-dev`, bundling several skill families under the `bridge-dev` namespace: gstack-plan → Superpowers `writing-plans` bridging, pipeline orchestration, autoresearch loops, OpenCode model benchmarking, Resend-based repo update-email digests, and pipeline log review against a design doc.
- `bridge-fin`, bundling financial-workflow skills under the `bridge-fin` namespace: configurable market/account data sources, portfolio/account reporting and DCF valuation bridged into `anthropics/financial-services`, standalone strategy backtesting, and a shared Finnhub REST query skill.

Each series gets its own sibling plugin directory and its own namespace, selectable independently at install time — don't add unrelated new skill groups into an existing plugin; give them a new one instead. No build step, no runtime — pure skill definitions and plugin metadata.

## Plugin structure

```
.claude-plugin/marketplace.json                    — marketplace descriptor; lists every installable plugin and its source path
plugins/<plugin-name>/.claude-plugin/plugin.json    — one manifest per plugin (name, version, description)
plugins/<plugin-name>/skills/<skill-name>/SKILL.md  — one skill per directory; SKILL.md is the full skill prompt
README.md                                           — user-facing install and usage docs
```

Claude Code reads `plugins/<plugin-name>/skills/*/SKILL.md` for each installed plugin. The frontmatter (`---` block) controls `name`, `description`, `triggers`, and `allowed-tools`. A skill's slash-command and cross-skill-reference prefix is its plugin's `name` (e.g. `bridge-dev:init-project`), not the marketplace name.

## Adding a new skill

1. Pick the plugin it belongs to (usually `bridge-dev`, unless it starts a new series — see above).
2. Create `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` with a YAML frontmatter block followed by the skill instructions.
3. No registration needed — Claude Code discovers skills by directory structure.
4. Bump `version` in `plugins/<plugin-name>/.claude-plugin/plugin.json` (semver).

## Adding a new skill series (plugin)

1. Create `plugins/<new-plugin-name>/.claude-plugin/plugin.json` (name, version, description, author, license, keywords) and `plugins/<new-plugin-name>/skills/`.
2. Add an entry to the `plugins` array in the root `.claude-plugin/marketplace.json`: `{"name": "<new-plugin-name>", "source": "./plugins/<new-plugin-name>", "description": "..."}`.
3. Document it in README.md under its own `## Skills (\`<new-plugin-name>\` series)` section.

## Versioning

Each plugin's `version` in its `plugin.json` follows semver. Bump the minor or patch component freely as part of normal work (new skill, fix, small change). **Never bump the major (leftmost) component without the user's explicit go-ahead first** — ask before bumping it, even when the change looks breaking (removed skill, renamed provider, changed config schema).

## Python scripts

If any helper scripts are added, use `uv` for package management and `uv run` to execute them. Never use `pip install` or bare `python`.

```bash
uv add <package>
uv run script.py
```

## Skill authoring conventions

- `allowed-tools` in frontmatter restricts which Claude tools the skill may use.
- `triggers` lists natural-language phrases that should auto-invoke the skill.
- Skills must **not** implement code themselves — they instruct Claude how to act.
- Every skill that produces files must specify the output path (e.g. `docs/superpowers/input/`).
- Explicit `[ASSUMPTION: ...]` markers are preferred over silent gap-filling.
- When a skill's own steps involve parsing, filtering, or summarizing a log file or other large text output (e.g. `review-pipeline-logs` isolating a run's log block), the step should say to use context-mode (`ctx_batch_execute`/`ctx_execute_file`) for that pass instead of raw `Read`/`Bash`/`Grep` — only the derived findings should enter the conversation, not the raw bytes. Still use `Read` when the exact text is needed afterward (e.g. quoting a line verbatim in a report).
- When those findings point at source code (file paths, function names, stack traces) in a *target* repo the skill is operating on, use codegraph (`codegraph_explore`/`codegraph_node`, or the `codegraph explore`/`codegraph node` CLI) to locate the referenced code instead of `grep`/whole-file `Read`. If the target repo has no `.codegraph/` directory, run `codegraph init <path>` first — it builds the initial index automatically. If `.codegraph/` already exists, run `codegraph sync <path>` (or `codegraph index <path>` for a full rebuild) before querying it, since the code under review has often changed since the last index.

## Known output paths and shared config

- `docs/superpowers/{plans,specs}/` — gstack-to-plan handoff files
- `docs/pipeline-reviews/` — review-pipeline-logs reports
- `docs/autoresearch/plan/` — autoresearch-plan comparison logs (candidate approaches, metric, winner)
- `docs/autoresearch/impl/` — autoresearch-impl iteration logs (round-by-round variant/metric/keep-or-discard)
- `docs/opencode-model-tests/` — reports shared by `benchmark-opencode-models` (deep per-prompt time/quality/completeness/autonomy/discipline/TDD-discipline scores) and `check-opencode-models` (fast ping-only availability reports)
- `.bridge/email-config.json` (per target repo, gitignored — may hold plaintext secrets) — recipients, last-sent tracking, and a `provider`-selected send mechanism (Resend MCP connection, or a fully custom HTTP POST: endpoint/headers/body template); shared by `setup-email-updates` and `send-update-email`
- `docs/env-setup/claude-plugins-manifest.json` — user-scope Claude Code plugins/marketplaces + gstack snapshot, written/read by `setup-env`
- `docs/finance/{reports,valuations,backtests}/` — handoff docs and reports from the financial series (`market-account-report`, `valuation-model`, `strategy-backtest`), bridging into the `anthropics/financial-services` marketplace's `client-report`/`dcf-model` skills where applicable
- `.bridge/finance-config.json` (per target repo, gitignored — an `http` source may hold a plaintext token) — configured market/account data sources (MCP connections, direct HTTP APIs, or local Python packages), base currency, and watchlist; shared by `setup-finance-sources`, `market-account-report`, `valuation-model`, `strategy-backtest`, and `finnhub-query`. `finnhub-query` is the only skill that calls Finnhub's REST API directly — the other three invoke it rather than duplicating endpoint/auth/error-handling logic

<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
