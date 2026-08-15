---
name: setup-finance-sources
description: Create or edit the .bridge/finance-config.json that market-account-report, valuation-model, and strategy-backtest need — which market-data sources are connected (MCP connections or direct HTTP APIs), a base currency, and a watchlist. Always gitignores the config since an "http" source can hold a plaintext token.
triggers:
  - setup finance sources
  - configure finance data sources
  - init bridge finance config
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - ToolSearch
---

# Bridge: Setup Finance Sources

**Announce at start:** "I'm using the bridge:setup-finance-sources skill to configure market/account data sources for this repo."

## Purpose

`market-account-report`, `valuation-model`, and `strategy-backtest` all refuse to run against a repo that has no `.bridge/finance-config.json`. This skill is the only thing that creates or edits that file — which data sources are available, a base currency for reporting, and a default watchlist.

## Requirements

- For an `mcp` source: the MCP connection must already be registered on this machine (e.g. `okx-agent-trade-kit`). This skill does not register MCP connections itself — it only records the name and verifies it resolves.
- For an `http` source: an endpoint URL and (if the provider needs one) a bearer token, given to you by the user.
- `.bridge/finance-config.json` must never be committed to git — an `http` source can hold a plaintext token. This skill gitignores it as part of Step 3c, regardless of which sources are configured.

## Step 1 — Check Existing Config

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
test -f .bridge/finance-config.json && cat .bridge/finance-config.json || echo "NO_CONFIG"
```

- Not a git repo → stop, tell the user this skill must run from inside the target repo.
- `NO_CONFIG` → go to Step 2 (create).
- Prints JSON → go to Step 4 (edit).

## Step 2 — Create Config

Ask the user which data sources they want to configure. They can add more than one; a repo commonly starts with just the crypto MCP and adds an equities source later.

### Step 2a — `mcp` source (e.g. OKX)

Ask for the registered MCP connection name (default guess: `okx-agent-trade-kit`) and what market it covers (`crypto`, `tw-equity`, `us-equity`, ...). Verify it resolves before recording it:

```
ToolSearch query: "<mcpServerName> account balance"
```

- Matches → the connection is usable. Continue.
- No match → tell the user this MCP connection isn't registered on this machine (via `claude mcp add` or `/mcp`), and ask if they want to record it anyway for later, or skip it.

### Step 2b — `http` source (e.g. a TW/US equities API)

If the user doesn't already have one picked, offer this reference table (recommendations only — do not implement against any of these until the user actually has an account/key):

| Market | Option | Why |
|---|---|---|
| TW 台股 | [FinMind](https://finmind.github.io/) | Free tier, REST + Python SDK, documents its own LLM/Agent-Skill/MCP integration — easiest fit here |
| TW 台股 | [Fugle 富果](https://www.fugle.tw/) | Real-time quotes, good for live market data |
| TW 台股 | `shioaji` (永豐金) | Broker-linked, needed if the user wants actual account/order data, not just quotes |
| US | Alpha Vantage / Finnhub | Free-tier REST, simple API-key auth |
| US | `yfinance` | No key needed, quick historical pulls |
| US | Polygon.io | Paid, tick-level/pro-grade data |

For the chosen provider, ask for: endpoint base URL, auth token/key (if any), and what market it covers. Treat the token as a secret — never echo it back, never put it in a commit message.

### Step 2c — Base Currency and Watchlist

Ask for a base currency (default `USD` unless the user has a different home currency) and an optional default watchlist (tickers/pairs commonly reported on, e.g. `["BTC-USDT-SWAP", "2330.TW", "AAPL"]`). Both can be empty/edited later.

### Write the Config

```bash
mkdir -p .bridge
jq -n \
  --argjson sources '[{"id":"okx","kind":"mcp","mcpServerName":"okx-agent-trade-kit","market":"crypto"}]' \
  --arg currency "USD" \
  --argjson watchlist '["BTC-USDT-SWAP"]' \
  '{sources: $sources, baseCurrency: $currency, watchlist: $watchlist}' \
  > .bridge/finance-config.json
```

Replace `--argjson sources` with the actual sources gathered above. Each `mcp` source object is `{id, kind: "mcp", mcpServerName, market}`; each `http` source object is `{id, kind: "http", endpoint, token, market}` (omit `token` entirely if the provider needs none — never write it as an empty string). Replace `--arg currency` and `--argjson watchlist` with the user's answers from Step 2c.

Continue to Step 3.

## Step 3 — Gitignore the Config

```bash
grep -qxF '.bridge/finance-config.json' .gitignore 2>/dev/null || echo '.bridge/finance-config.json' >> .gitignore
```

If `.gitignore` didn't exist, this creates it with that one line. Then commit only the `.gitignore` change — never the config file itself:

```bash
git add .gitignore
git commit -m "chore: gitignore bridge finance config"
git push
```

If `git status` shows `.bridge/finance-config.json` as already tracked, warn the user explicitly and offer to run `git rm --cached .bridge/finance-config.json` (then commit that removal) — do not run the removal without the user's go-ahead.

## Step 4 — Edit Existing Config

Show the user the current `sources`, `baseCurrency`, and `watchlist` from the `cat` output in Step 1. Ask what to add/remove/change:

- Adding a source: repeat Step 2a or 2b for the new source, then append it.
- Removing a source: confirm the `id`, then drop it.
- Changing `baseCurrency`/`watchlist`: straightforward replace.

```bash
jq --argjson sources '[...]' --arg currency "USD" --argjson watchlist '[...]' \
  '.sources = $sources | .baseCurrency = $currency | .watchlist = $watchlist' \
  .bridge/finance-config.json > .bridge/finance-config.json.tmp
mv .bridge/finance-config.json.tmp .bridge/finance-config.json
```

`.bridge/finance-config.json` is gitignored (Step 3) — this write is local-only, no commit needed. If `.gitignore` somehow doesn't already have the entry, run Step 3's gitignore commands now.

## Notes

- This skill never places live orders and never needs trade-execution scopes — it only records how to *read* market/account data.
- `mcp` sources are resolved by name via `ToolSearch` at use-time by the skills that consume this config (never hardcoded), the same lazy-lookup pattern `send-update-email` uses for its Resend connection. Every machine that will run the finance report/model/backtest skills against a given repo needs that repo's `mcp` connections registered locally — this lives in Claude Code's local config, not in git, so it does not travel with `git clone`.
- `http` sources carry their secret in the config file itself, which is exactly why `.bridge/finance-config.json` must stay gitignored (Step 3) — copy it manually (out-of-band, not via git) to any other machine that needs it.
