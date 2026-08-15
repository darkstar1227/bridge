---
name: market-account-report
description: Bridge connected market/account data (via .bridge/finance-config.json's sources) into a periodic portfolio/account report shaped like the anthropics/financial-services wealth-management client-report skill's input contract, then invoke /client-report if it's installed.
triggers:
  - market account report
  - financial account report
  - portfolio report
  - generate client report
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - ToolSearch
---

# Bridge: Market/Account Report

**Announce at start:** "I'm using the bridge:market-account-report skill to build a portfolio/account report from your connected data sources."

## Purpose

Anthropic's `wealth-management` vertical (`claude-for-financial-services` marketplace) ships `client-report` (`/client-report`), which turns structured client/account/performance/activity data into a polished report — but it has no way to reach into a connected exchange or brokerage MCP itself. This skill does that part: pull balances, positions, and activity from whatever sources `.bridge/finance-config.json` names, shape them into `client-report`'s documented input contract, and hand off.

## Step 1 — Read Config

```bash
test -f .bridge/finance-config.json && cat .bridge/finance-config.json || echo "NO_CONFIG"
```

`NO_CONFIG` → stop, tell the user to run `/bridge:setup-finance-sources` first. Do not create the file yourself.

## Step 2 — Pick the Reporting Period

Ask the user (or accept it as an argument): QTD, YTD, a specific date range, or "since inception." Default to YTD if they don't care. This is a point-in-time snapshot report, not an incremental diff — there is no "since last report" state to track, unlike `send-update-email`'s commit-range model.

## Step 3 — Gather Data Per Source

For each entry in `.bridge/finance-config.json`'s `sources`:

**`kind: "mcp"`** (e.g. OKX): locate the tools once per source before calling any of them:

```
ToolSearch query: "<mcpServerName> account balance positions bills"
```

Then call the resolved tools to collect, per source:
- Current balances (all assets/currencies held)
- Open positions (instrument, size, entry price, mark price, unrealized PnL)
- Bills/fills covering the reporting period (for realized PnL, fees, deposits/withdrawals — this is the closest equivalent to `client-report`'s "trade execution records" and "contributions/withdrawals")
- Current market prices for every held instrument (to value everything in `baseCurrency`)

**`kind: "http"`**: call the configured `endpoint` with the stored `token` (never echo the token into the conversation) for the equivalent data. If the source hasn't actually been wired up yet (recorded during setup but no real integration written), skip it and note the gap — do not fabricate data for it.

If a source's tools/endpoint fail or return nothing, note that specific source as unavailable in the report rather than silently omitting it.

## Step 4 — Compute Performance Data

From the gathered balances/positions/bills, derive:
- Starting vs. current total value (in `baseCurrency`) for the period
- Realized PnL (from closed positions/fills) + unrealized PnL (from open positions) = total return for the period
- Return % = total return / starting value (flag as `[ASSUMPTION: starting value estimated from earliest available balance snapshot]` if the source has no true period-start balance)
- Per-source breakdown, plus a combined total across all sources

There is no natural "benchmark" for a mixed crypto/equity account unless the user names one — if they haven't, mark benchmark comparison as `[ASSUMPTION: no benchmark configured — omitted]` rather than inventing one.

## Step 5 — Write the Handoff Document

Save to: `docs/finance/reports/account-report-YYYY-MM-DD.md` (today's date).

Map gathered data onto `client-report`'s documented input contract. Where a field doesn't apply to a personal/algo trading account (firm branding assets, Investment Policy Statement benchmark, household composition), mark it `[ASSUMPTION: not applicable — personal account]` rather than leaving it silently blank:

```markdown
# Account Report Handoff: <account/repo name>

_Sources: <list of source ids from config>_
_Period: <QTD/YTD/range>_
_Generated: <today's date>_

## Client & Account Data
- Account identifiers: <per-source account/market>
- Reporting period: <dates>
- Benchmark: [ASSUMPTION: ...] or the named benchmark

## Performance Data
- Period return: <%, and absolute, per source and combined>
- Starting value / current value (in <baseCurrency>)
- Realized PnL / Unrealized PnL breakdown

## Activity Data
- Trade/fill records in period (source, instrument, date, side, size, price)
- Deposits/withdrawals in period
- Fees paid in period

## Holdings
- <instrument, size, current price, market value, % of portfolio>

## Open Questions / Explicit Assumptions
- [ASSUMPTION] ... — <why>
```

## Step 6 — Invoke or Render

Check whether the `wealth-management` vertical's `client-report` skill is available:

```
ToolSearch query: "client-report"
```

(or check for the `/client-report` slash command in context). 

- **Available** → invoke it: "Use `docs/finance/reports/<handoff-filename>` as the source data for `/client-report`." Let it produce the polished report — do not build the final deliverable yourself.
- **Not available** → tell the user the `wealth-management` plugin isn't installed (`claude plugin install wealth-management@claude-for-financial-services`), then render the same handoff content directly as a readable Markdown report in the same file, so the user still gets a usable deliverable today.

Do not implement `client-report`'s formatting/branding job yourself when it *is* available — this skill's job ends at producing a correct, complete handoff.
