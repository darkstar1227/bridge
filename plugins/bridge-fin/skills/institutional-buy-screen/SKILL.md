---
name: institutional-buy-screen
description: Screen TWSE-listed (上市) stocks for sustained 三大法人 (institutional) net buying over a recent trading-day window that hasn't already run up in price, using TWSE's public T86 and MI_INDEX open-data endpoints (no auth, no MCP source needed). Reports code, name, cumulative net-buy shares, and window price change.
triggers:
  - 三大法人買超
  - institutional buy screen
  - institutional net buy screen
  - 三大法人買超篩選
  - screen institutional buying
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Bridge: Institutional Buy Screen

**Announce at start:** "I'm using the bridge-fin:institutional-buy-screen skill to screen TWSE stocks for sustained institutional buying."

## Purpose

FinMind's `TaiwanStockInstitutionalInvestorsBuySell` dataset is per-stock (needs a `data_id`) — there's no way to ask it for "every stock institutions bought this week" without querying ~2,000 stocks one at a time. TWSE itself publishes the same data market-wide, per day, with no auth:

- `T86` (`https://www.twse.com.tw/rwd/zh/fund/T86?date=YYYYMMDD&selectType=ALL&response=json`) — every stock's 三大法人買賣超股數 for one day
- `MI_INDEX` (`https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALLBUT0999&response=json`) — every stock's daily closing price, for computing the window's price change

This skill pulls both across a trading-day window and screens for stocks institutions kept buying without the price already running away.

**Scope: TWSE (上市) only.** TPEX's (上櫃) open-data endpoint (`tpex_3insti_daily_trading`) ignores any date parameter and only ever returns the latest trading day — there's no historical-date query available, so 上櫃 stocks are not covered by this screen. Say so plainly in the report rather than silently omitting them.

## Step 1 — Get Parameters

Ask the user (or accept as arguments), with sensible defaults:
- `--days` — trading-day window size (default `3`)
- `--max-change` — max allowed close-to-close %% change over the window (default `5.0`)
- `--min-positive-days` — how many of the window's days must show net buying (default: all of them, i.e. equal to `--days`)
- `--end-date` — window's last trading day, `YYYYMMDD` (default: today)
- `--include-etf` — include `00`-prefixed ETF/fund codes (default: excluded, since "三大法人買超個股" usually means single stocks, not funds)

## Step 2 — Run the Screen (sandboxed)

The script does its own HTTP fetching and walks backward from `--end-date` to find actual trading dates (skips weekends/holidays by checking each day's `T86` response), so no separate calendar lookup step is needed. Only the reduced JSON result should enter the conversation — the per-stock raw daily rows stay inside the script:

```bash
uv run skills/institutional-buy-screen/scripts/screen.py \
  --end-date <YYYYMMDD> --days <n> --max-change <pct> --min-positive-days <n>
```

Output shape:
```json
{
  "market": "TWSE",
  "dates": ["20260814", "20260817", "20260818"],
  "baseline_date": "20260813",
  "results": [
    {"code": "2886", "name": "兆豐金", "net_buy_3d": 69393353,
     "net_buy_by_day": [...], "baseline_close": 45.85, "last_close": 46.90,
     "change_pct": 2.29}
  ]
}
```
`results` is sorted by `net_buy_3d` descending. An `{"error": "..."}` object means the script couldn't resolve enough trading dates (e.g. `--end-date` too far in the future, or TWSE's site unreachable) — report that plainly rather than presenting an empty screen as "0 matches."

## Step 3 — Report

Present the top 20-30 by `net_buy_3d` as a table (代號, 名稱, N日合計買超股數, 漲幅%). Flag any result where `change_pct` is notably negative (institutions buying into a falling stock — a different signal than "buying into strength") rather than folding it in silently. Mention the total match count and offer to list the rest if it's long.

If asked to persist the result, save to `docs/finance/screens/screen-YYYY-MM-DD-institutional-buy.md` with the parameters used (window dates, max-change, min-positive-days) and the full result table.

## Notes

- No `.bridge/finance-config.json` source is required — this skill talks to TWSE's own public endpoints directly, unlike `finnhub-query`/`market-account-report`/`valuation-model`.
- To extend coverage to 上櫃 (TPEX), a different data source with historical-date support would be needed (TPEX's own site search / a paid vendor) — don't fake it by silently reusing TPEX's "latest day only" endpoint across the whole window, that would misattribute other days' TPEX data to the wrong date.
- `net_buy_by_day` is kept in the output so a caller can distinguish "bought every single day" from "net positive over the window but sold one day" if `--min-positive-days` was relaxed below `--days`.
