# Pipeline Log Review: Order Processing Pipeline

_Design doc: review-pipeline-logs-workspace/fixtures/order-pipeline/plan.md_
_Log source: review-pipeline-logs-workspace/fixtures/order-pipeline-quiet/run.log, entire file reviewed (only one run present, no run-start markers to bound further; spans 2026-07-08T14:02:17Z to 2026-07-08T14:02:19Z)_
_Reviewed: 2026-07-09_

## Verdict

**PASS WITH WARNINGS** — the run finished in ~2s with no errors logged, but the log contains only two generic lines ("processing order" / "done") and gives zero verifiable evidence for any of the 4 designed steps or their required output values, making this run effectively undebuggable if something had gone wrong.

## Step-by-Step Results

| Step | Expected | Found in log? | Status | Evidence |
|------|----------|---------------|--------|----------|
| 1. Validate order | `order validated` line with order id + item count (item count ≥ 1) | Not found | ⚠️ unverifiable | Log only shows generic `processing order` at 14:02:17Z — no order id, no item count, no explicit validation line |
| 2. Charge payment | `charge succeeded` line with charge id + amount (amount == order total) | Not found | ⚠️ unverifiable | No charge-related line anywhere in the log |
| 3. Update inventory | `inventory updated` line with SKU + quantity decremented (== item count from step 1) | Not found | ⚠️ unverifiable | No inventory-related line anywhere in the log |
| 4. Send confirmation email | `confirmation email sent` line with recipient address | Not found | ⚠️ unverifiable | No email-related line anywhere in the log |

None of the four steps produced their designated success signal. Because the log ends with a plain `done` and no `ERROR`/`FATAL`/exception text, the run did not visibly crash — but that is the only thing this log actually proves. Whether validation, charging, inventory update, and email send each individually succeeded (and with correct values) cannot be confirmed from this evidence.

## Logging Quality

This is the core finding of this review — the pipeline fails the logging-quality bar even though nothing crashed:

- **Every step is invisible.** The plan calls for a start + completion/success line per step (4 steps × 2 lines = 8+ expected lines). The actual log has 2 lines total, neither of which names a step.
- **No log levels are used at all.** Both lines look like unlabeled/INFO text; there's no way to tell from the log format whether a failure would even be flagged as an error if one occurred.
- **No identifying context anywhere.** No order id, item count, charge id, amount, SKU, quantity, or recipient address appears in the log. A future on-call engineer debugging a bad charge or a missed email for a specific order would have nothing to grep for.
- **"done" is not a success signal.** It doesn't say what completed, whether all 4 steps ran, or point back to an order id — it's indistinguishable from a partial/silent-failure run that merely didn't throw.

## Errors & Exceptions

None found. No `ERROR`, `FATAL`, `Exception`, `Traceback`, `panic`, or non-2xx status text appears anywhere in the reviewed block. There is nothing to classify as unexpected-failure or expected/handled — the log is simply silent, not alarming.

## Output Value Checks

Cannot be performed. The plan commits to three specific checks:

| Expected value | Expected source | Actual logged value | Result |
|---|---|---|---|
| Item count ≥ 1 | `order validated` line | Not logged | ❌ cannot verify |
| Charge amount == order total | `charge succeeded` line | Not logged | ❌ cannot verify |
| Quantity decremented == item count from step 1 | `inventory updated` line | Not logged | ❌ cannot verify |

All three checks are blocked by the same root cause: the values the plan requires were never emitted to the log.

## Suggested Fixes

1. Add an explicit log line per step matching the plan's stated success signals verbatim, e.g. `order validated order_id=<id> item_count=<n>`, `charge succeeded charge_id=<id> amount=<amt>`, `inventory updated sku=<sku> qty_decremented=<n>`, `confirmation email sent recipient=<addr>`.
2. Add a start line per step as the plan requires ("Every step should log both a start and a completion/success line"), not just an overall `processing order` at pipeline entry.
3. Introduce real log levels (INFO for step start/success, ERROR/FATAL for failures) so a silent crash and a slow success aren't both just "no output."
4. Include the order id on every line for the run so all lines for one order can be grepped/correlated together.
5. Replace the terminal `done` with a structured summary line, e.g. `order <id> completed steps=4/4 charge=<amt> email=<addr>`, so a reader can confirm all steps ran without needing per-step lines (in addition to, not instead of, #1).

## Assumptions / Open Questions

- [ASSUMPTION] Treated the entire `run.log` file as the single run to review — the file has no run-start marker and contains only 2 lines total, so no boundary needed to be inferred.
- [OPEN] Confirm whether this `run.log` is genuinely what production emits, or whether a more verbose log level/config exists that wasn't captured in this fixture — if so, that fuller log should be reviewed instead.
- [OPEN] Confirm with the team whether the order actually completed correctly (validated, charged, inventory decremented, email sent) via another source (DB state, payment provider dashboard, email provider logs) — this review can only say the log doesn't prove it either way.
