---
name: finnhub-query
description: Query Finnhub's REST API directly (quote, company profile, basic financials, historical candles, company news) using the finnhub source recorded in .bridge/finance-config.json, returning normalized JSON. Owns every Finnhub endpoint shape, auth, and error handling in one place so market-account-report, valuation-model, and strategy-backtest invoke this skill instead of each embedding their own curl calls.
triggers:
  - query finnhub
  - finnhub quote
  - finnhub api
  - finnhub candles
allowed-tools:
  - Bash
  - Read
  - Grep
---

# Bridge: Finnhub Query

**Announce at start:** "I'm using the bridge-fin:finnhub-query skill to call Finnhub's REST API for <operation>."

## Purpose

There's no single official Finnhub MCP worth trusting (see `setup-finance-sources`'s Step 2b), so every skill that needs US-equity data hits Finnhub's REST API directly. Rather than three copies of the same curl calls drifting apart, this skill owns the endpoint shapes, auth, error handling, and response normalization in one place. Other `bridge-fin` skills invoke it (`bridge-fin:finnhub-query`) instead of calling Finnhub themselves.

## Step 1 — Resolve Endpoint and Token

```bash
test -f .bridge/finance-config.json && jq -c '.sources[] | select(.kind=="http" and .provider=="finnhub")' .bridge/finance-config.json || echo "NO_CONFIG"
```

- `NO_CONFIG` or no matching source → stop, tell the caller/user to run `/bridge-fin:setup-finance-sources` and add a `finnhub` source first. Do not fall back to a hardcoded token or guess one.
- Found → extract `endpoint` (default `https://finnhub.io/api/v1` if absent) and `token`. Never echo the token into the conversation, a commit message, or any report file.

## Step 2 — Determine the Operation

Accept from the caller (another skill invoking this one) or ask the user directly:

| Operation | Needs |
|---|---|
| `quote` | `symbol` |
| `profile` | `symbol` |
| `metric` | `symbol` (basic financials — for `valuation-model`) |
| `candle` | `symbol`, `resolution` (e.g. `D`, `60`), `from`, `to` (unix seconds) |
| `news` | `symbol`, `from`, `to` (dates, `YYYY-MM-DD`) |

If the caller wants something not in this table, say so rather than silently approximating — extend this table (and Step 3 below) when a real need shows up.

## Step 3 — Call and Normalize

Use `curl`, writing the URL with `jq -R` or a temp file if the token needs to stay out of shell history in a shared environment — for a single-user local run, direct `curl` args are fine since the token is never echoed to the conversation either way:

**`quote`** — `GET {endpoint}/quote?symbol=<SYMBOL>&token=<token>`
Raw response: `{c, d, dp, h, l, o, pc, t}`. Normalize to: `{price: c, change: d, changePercent: dp, high: h, low: l, open: o, previousClose: pc, asOf: t}`.

**`profile`** — `GET {endpoint}/stock/profile2?symbol=<SYMBOL>&token=<token>`
Raw response includes `marketCapitalization`, `shareOutstanding`, `name`, `currency`, `exchange`. Normalize to: `{name, exchange, currency, marketCap: marketCapitalization, sharesOutstanding: shareOutstanding}`.

**`metric`** — `GET {endpoint}/stock/metric?symbol=<SYMBOL>&metric=all&token=<token>`
Raw response is `{metric: {...many keys}, series: {...}}`. Pull only what the caller actually needs (e.g. for a DCF handoff: `peBasicExclExtraTTM`, `roeTTM`, `totalDebt/totalEquityQuarterly`, `netProfitMarginTTM`) — do not dump the entire `metric` blob into a report; it's large and mostly irrelevant per use.

**`candle`** — `GET {endpoint}/stock/candle?symbol=<SYMBOL>&resolution=<resolution>&from=<from>&to=<to>&token=<token>`
Raw response: `{c:[...], h:[...], l:[...], o:[...], t:[...], v:[...], s: "ok"|"no_data"}`. Normalize by zipping the parallel arrays into `[{t, o, h, l, c, v}, ...]` — the shape `strategy-backtest`'s script already expects.

**`news`** — `GET {endpoint}/company-news?symbol=<SYMBOL>&from=<from>&to=<to>&token=<token>`
Raw response is an array of `{datetime, headline, source, summary, url, ...}`. Normalize to just `{datetime, headline, source, url}` per item unless the caller wants summaries too.

## Step 4 — Error Handling

| Condition | Meaning | Handling |
|---|---|---|
| HTTP 401 | Bad/missing token | Stop, tell the user to check the `token` in `.bridge/finance-config.json` (re-run `/bridge-fin:setup-finance-sources` to fix it). |
| HTTP 403 on `candle` | Free-tier restriction on historical US-equity candles (a known, recurring Finnhub limitation, not a bug in this skill) | Do not retry. Tell the caller plainly and suggest a `local`/`yfinance` source instead for this asset (see `strategy-backtest`'s Step 3). |
| HTTP 429 | Rate limit (free tier: 60 req/min) | Stop issuing further calls in this batch; tell the user to wait or space out requests rather than looping retries. |
| `"s": "no_data"` on `candle` | Symbol/range has no data (e.g. wrong resolution for the exchange, or a non-trading period) | Report as "no data for this range," not an error — don't treat it as a failure requiring retry. |
| Empty/`null` fields on `quote`/`profile` | Symbol not found or delisted | Report to the caller; do not substitute a zero or guess. |

## Notes

- This skill only reads Finnhub data — it has no write/order-placement surface to worry about, unlike the exchange MCPs.
- If a caller needs a Finnhub operation not in Step 2's table, extend this skill rather than having the caller reimplement a one-off curl call — that's exactly the duplication this skill exists to avoid.
