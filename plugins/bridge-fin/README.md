# bridge-fin

Financial-workflow skills: configurable market/account data sources (MCP, direct HTTP, or local Python), portfolio/account reporting and DCF valuation bridged into [`anthropics/financial-services`](https://github.com/anthropics/financial-services), standalone strategy backtesting, and a shared Finnhub REST query skill.

## Skills

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

## Requirements

- At least one market/account data source, plus [`uv`](https://docs.astral.sh/uv/). Any combination works: an MCP connection (e.g. `okx-agent-trade-kit` for crypto accounts, [`FinMind-MCP`](https://github.com/FinMind/FinMind-MCP) with a `FINMIND_TOKEN` for TW equities) registered via `claude mcp add`/`/mcp`; a Finnhub API key for direct-HTTP US-equity quotes; or nothing extra at all for `yfinance`-based historical US-equity candles (`uv run --with yfinance ...`, no key needed)
- [`anthropics/financial-services`](https://github.com/anthropics/financial-services) marketplace, with the `financial-analysis` core plugin and the `wealth-management` vertical installed — for `market-account-report` and `valuation-model` to hand off to `/client-report`/`/dcf` (optional: both skills still produce a standalone handoff/report without it)
