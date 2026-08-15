---
name: strategy-backtest
description: Pull historical candles from a connected market-data source (.bridge/finance-config.json) and backtest a simple rule-based long/flat strategy (SMA crossover or RSI threshold) via a sandboxed script, producing a performance report. Simulation-only — never places live orders.
triggers:
  - strategy backtest
  - backtest my strategy
  - trading strategy performance
  - backtest sma
  - backtest rsi
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - ToolSearch
---

# Bridge: Strategy Backtest

**Announce at start:** "I'm using the bridge:strategy-backtest skill to backtest <strategy> on <asset>."

## Purpose

None of the `anthropics/financial-services` verticals ship a trading-strategy backtester — `private-equity`'s `returns-analysis` is IRR/MOIC for PE deals, not bar-by-bar simulation. This skill is standalone: it pulls historical price data from whatever `.bridge/finance-config.json` names, runs a rule-based long/flat simulation, and reports the results. It never places live orders, even when the underlying MCP connection also exposes trade-execution tools.

## Step 1 — Read Config

```bash
test -f .bridge/finance-config.json && cat .bridge/finance-config.json || echo "NO_CONFIG"
```

`NO_CONFIG` → stop, tell the user to run `/bridge:setup-finance-sources` first.

## Step 2 — Get Strategy and Asset Parameters

Ask the user (or accept as arguments):
- Asset/instrument (must match what the configured source expects, e.g. `BTC-USDT-SWAP`)
- Strategy: `sma_crossover` (needs `fast`/`slow` period ints) or `rsi` (needs `period`, `oversold`, `overbought`) — these are the two the backtest script supports today; if the user wants something else, say so rather than silently approximating it with one of these two
- Date range / lookback window
- Candle granularity (e.g. `1D`, `4H`)
- Optional: `initial_capital` (default 10000), `fee_rate` per trade (default 0), `bars_per_year` for annualizing Sharpe/CAGR (default 365 for daily crypto candles — use 252 for daily equities)

## Step 3 — Pull Candles

Branch on the chosen source's `kind` (from `.bridge/finance-config.json`):

**`kind: "mcp"`** — locate the tool, then call it:

```
ToolSearch query: "<mcpServerName> candles"
```

Call it for the requested asset/range/granularity (e.g. `market_get_candles` on an OKX-style connection, or FinMind-MCP's TW-equity candle tool).

**`kind: "http"`, `provider: "finnhub"`** — `GET {endpoint}/stock/candle?symbol=<TICKER>&resolution=<D|60|...>&from=<unix>&to=<unix>&token=<token>`. Finnhub's free tier has repeatedly restricted this endpoint for US equities (returns 403/"no access" for some symbols) — if the call fails this way, tell the user plainly (don't retry-loop against it) and suggest either upgrading their Finnhub plan or switching to a `local`/`yfinance` source for this asset instead.

**`kind: "local"`, `provider: "yfinance"`** — no HTTP call; fetch inline via `uv run` with `yfinance` as an ad-hoc dependency (no separate script file needed for a fetch this small):

```bash
uv run --with yfinance python3 -c "
import yfinance as yf, json, sys
df = yf.download(sys.argv[1], start=sys.argv[2], end=sys.argv[3], interval=sys.argv[4])
candles = [{'t': int(i.timestamp()), 'o': float(r.Open), 'h': float(r.High), 'l': float(r.Low), 'c': float(r.Close), 'v': float(r.Volume)} for i, r in df.iterrows()]
print(json.dumps(candles))
" "<TICKER>" "<start-date>" "<end-date>" "<interval, e.g. 1d>"
```

Normalize whichever source's result into `{t, o, h, l, c, v}` objects — the script only needs `c` (close) but pass the full OHLCV through for the report's own reference.

If the pull returns fewer candles than the strategy needs to warm up (e.g. fewer than `slow` periods for an SMA crossover), tell the user and ask for a longer lookback rather than running a backtest that's mostly warm-up.

## Step 4 — Run the Backtest (sandboxed)

The raw bar-by-bar simulation trace should never enter the conversation — only the derived metrics do, per this repo's context-mode convention. Write the gathered candles + params to a temp JSON file and run the script via `Bash` (its own output is already just the reduced metrics JSON, so this step doesn't need `ctx_execute` on top of it):

```bash
uv run skills/strategy-backtest/scripts/backtest.py --input <payload.json>
```

Payload shape:
```json
{
  "candles": [{"t": 1700000000, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}],
  "strategy": {"type": "sma_crossover", "fast": 10, "slow": 30},
  "initial_capital": 10000,
  "fee_rate": 0.0005,
  "bars_per_year": 365
}
```

Output: `{cagr, sharpe, max_drawdown, win_rate, trade_count, final_equity, total_return_pct}`. The simulation itself is long-only/no-leverage (flat position earns 0) — say so plainly in the report so the user doesn't mistake it for a full trading-system backtest.

## Step 5 — Write the Report

Save to: `docs/finance/backtests/backtest-YYYY-MM-DD-<strategy>-<asset>.md`.

```markdown
# Strategy Backtest: <strategy type + params> on <asset>

_Generated: <today's date>_
_Data source: <source id>_ · _Range: <dates>_ · _Granularity: <e.g. 1D>_
_Simulation: long-only, no leverage/shorting, flat position earns 0_

## Parameters
- Strategy: <type and params>
- Initial capital: <value>
- Fee rate per trade: <value>

## Results
| Metric | Value |
|---|---|
| CAGR | <%> |
| Sharpe | <value> |
| Max Drawdown | <%> |
| Win Rate | <%> |
| Trade Count | <n> |
| Final Equity | <value> |
| Total Return | <%> |

## Caveats
- No slippage model beyond the flat `fee_rate` per trade.
- Past performance on this data window is not predictive of future results.
- <any candle-count/warm-up caveat from Step 3, if relevant>
```

## Notes

- This skill only reads market data and never calls any order-placement tool, even when the same MCP connection exposes one (e.g. OKX's `spot_place_order`/`swap_place_order`). If the user asks this skill to also place trades, decline and point them to a dedicated trading workflow — that's out of scope here.
- To add a new strategy type, extend `scripts/backtest.py`'s `build_signals()` — this skill's own instructions don't implement strategy logic, the script does.
