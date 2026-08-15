---
name: valuation-model
description: Bridge a ticker/asset plus any locally-known market data (via .bridge/finance-config.json's sources) into the anthropics/financial-services financial-analysis dcf-model skill's input contract, then invoke /dcf.
triggers:
  - valuation model
  - build a dcf
  - dcf valuation
  - financial model for
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - ToolSearch
---

# Bridge: Valuation Model

**Announce at start:** "I'm using the bridge:valuation-model skill to prepare a DCF input handoff for <ticker/asset>."

## Purpose

`financial-analysis`'s `dcf-model` (`/dcf`) already fetches most of what it needs itself (Daloopa MCP, SEC EDGAR, web search) — it does not need a bridge for that. What it can't reach on its own is data sitting behind *this session's* already-connected sources (e.g. a live mark price from a configured exchange MCP), and it has no way to know up front whether the target is even DCF-shaped (a cash-flow-generating business) versus a pure token/commodity where DCF doesn't apply. This skill covers that gap, then hands off.

## Step 1 — Identify the Target

Get the ticker or asset identifier from the user (argument or ask). If ambiguous (e.g. a token that trades both as a coin and has a "stock token" wrapper), ask which one they mean.

## Step 2 — Applicability Check

DCF requires a business with projectable cash flows. Before gathering anything else, decide:

- **Equity / company** (has revenue, EBIT, cash flow statements) → DCF applies. Continue to Step 3.
- **Pure cryptocurrency / commodity / index** (no underlying cash-flow-generating business) → DCF does not apply. Stop here and tell the user explicitly why, rather than inventing financials to force a model. Suggest an alternative if one fits (e.g. relative valuation via `comps-analysis`/`/comps` against similar assets, or an on-chain valuation metric) but do not build one yourself unless asked.

## Step 3 — Gather What's Locally Known

Read `.bridge/finance-config.json` if it exists (optional for this skill — proceed without it if absent, since `/dcf` can source everything itself). For each configured source that's relevant to this asset:

```
ToolSearch query: "<mcpServerName> ticker price"
```

Pull whatever's directly available: current price, market cap, shares/units outstanding. This is a light touch — do not attempt to reconstruct a full income statement from a market-data MCP; that's `/dcf`'s own job via its documented data sources.

Then ask the user for the inputs only they can supply:
- Growth assumptions (specific rates for projection years, or "use consensus")
- Any historical financials they already have as files (point to the file path — pass it through, don't retype it)
- Optional: projection period, scenario framework, custom WACC inputs

## Step 4 — Readiness Check

Verify before writing the handoff:
- [ ] A clear target identifier (ticker or company name)
- [ ] Confirmed DCF applicability (Step 2)
- [ ] Either explicit growth assumptions or an explicit "use consensus" instruction

If growth assumptions are missing and the user hasn't said "use consensus," ask once more before proceeding — don't silently default.

## Step 5 — Write the Handoff Document

Save to: `docs/finance/valuations/dcf-input-YYYY-MM-DD-<ticker>.md`.

Distinguish clearly between what's known now and what `/dcf` should fetch itself — do not fabricate figures in the "known" section that weren't actually gathered:

```markdown
# DCF Input Handoff: <Ticker/Company>

_Bridged: <today's date>_

## Company Identifier
<ticker or name>

## Growth Assumptions
<user-supplied rates, or "use consensus estimates">

## Known Market Data (from connected sources)
- Current price: <value, source, as-of time> or "not available locally — let /dcf fetch"
- Market cap / shares outstanding: <value or "not available locally">

## User-Supplied Historical Financials
<file path(s) if provided, or "none — let /dcf source from SEC EDGAR/Daloopa">

## Optional Parameters
- Projection period: <default 5yr unless specified>
- Scenario framework: <Bear/Base/Bull if requested>
- Custom WACC inputs: <if provided>

## Open Questions / Explicit Assumptions
- [ASSUMPTION] ... — <why>
```

## Step 6 — Invoke financial-analysis dcf-model

```
ToolSearch query: "dcf-model"
```

- **Available** → invoke `/dcf`: "Use `docs/finance/valuations/<handoff-filename>` for the known inputs below; source everything else marked 'not available locally' yourself." Do not build the model yourself.
- **Not available** → tell the user the core `financial-analysis` plugin isn't installed (`claude plugin install financial-analysis@claude-for-financial-services`), and that the handoff document is saved for when it is.
