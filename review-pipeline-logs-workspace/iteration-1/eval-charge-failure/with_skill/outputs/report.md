# Pipeline Log Review: Order Processing Pipeline

_Design doc: review-pipeline-logs-workspace/fixtures/order-pipeline/plan.md_
_Log source: review-pipeline-logs-workspace/fixtures/order-pipeline-failure/run.log — single run, order_id=ORD-1042, from the "run started" marker (line 1) to EOF (line 12)_
_Reviewed: 2026-07-09_

## Verdict

**FAIL** — the pipeline correctly halted after the payment charge was declined, but the order (ORD-1042) was never completed: inventory was never decremented and no confirmation email was sent.

## Step-by-Step Results

| Step | Expected | Found in log? | Status | Evidence |
|------|----------|---------------|--------|----------|
| 1. Validate order | Logs `order validated` with order id and item count; item count >= 1 | Line 2 (start), line 3 (success) | ✅ ran & succeeded | `validating order order_id=ORD-1042` / `order validated order_id=ORD-1042 item_count=3` |
| 2. Charge payment | Logs `charge succeeded` with charge id and amount; amount matches order total | Line 4 (start), line 5 (failure, not success) | ❌ failed | `charging payment order_id=ORD-1042 amount=142.50` → `ERROR charge failed order_id=ORD-1042 reason=card_declined` + traceback: `payments.gateway.CardDeclinedError: do_not_honor` |
| 3. Update inventory | Logs `inventory updated` with SKU and quantity decremented == item count | No lines found | ❌ missing (expected — never reached) | not present after line 12 |
| 4. Send confirmation email | Logs `confirmation email sent` with recipient address | No lines found | ❌ missing (expected — never reached) | not present after line 12 |

Steps 3 and 4 are marked missing rather than unverifiable-by-silence: line 12 (`run aborted ... stage=charge_payment`) is explicit evidence the pipeline stopped at step 2 and intentionally never invoked steps 3/4, so this is a correct halt, not a silent skip.

## Logging Quality

- Steps 1 and 2 each log both a start line and a completion/failure line, matching the plan's verification expectation ("every step should log both a start and a completion/success line").
- Log levels are used meaningfully: routine progress is INFO, the decline and the abort are both ERROR — nothing is buried.
- The failure carries strong debugging context: `reason=card_declined`, a full Python traceback with file/line numbers, and the concrete exception type/code (`CardDeclinedError: code="do_not_honor"`). This is enough to diagnose the failure without re-running the pipeline.
- The final `run aborted` line explicitly names `stage=charge_payment`, which makes it unambiguous where the pipeline stopped and prevents mistaking steps 3/4 as silently skipped.
- Minor gap: the log never surfaces an independent "order total" value at validation time, so the expected-output check for step 2 (charge amount == order total) can't be cross-verified from the log alone (see Output Value Checks).
- No gap otherwise — this is one of the better-instrumented failure traces of this shape.

## Errors & Exceptions

1. **Line 5 + traceback (lines 6–11): `ERROR charge failed order_id=ORD-1042 reason=card_declined`, `CardDeclinedError: code="do_not_honor"`.**
   Classification: **unexpected failure** — this breaks step 2's success signal (`charge succeeded`) directly; the payment gateway declined the card.
2. **Line 12: `ERROR run aborted order_id=ORD-1042 stage=charge_payment`.**
   Classification: **expected/handled** — this is the pipeline's own controlled shutdown in response to the charge failure (not a second, independent bug). Aborting rather than proceeding to decrement inventory or send a confirmation for an uncharged order is the correct fail-safe behavior.

## Output Value Checks

| Step | Expected | Actual | Result |
|------|----------|--------|--------|
| 1. Validate order | item_count >= 1 | item_count=3 | ✅ matches |
| 2. Charge payment | charge amount == order total | amount=142.50 attempted, but charge did not succeed (declined) | ⚠️ not verifiable — no independent "order total" value appears anywhere in the log to compare against, and the charge never completed, so there is no successful amount to check |
| 3. Update inventory | quantity decremented == item_count (3) | n/a — step never ran | ❌ not applicable, step didn't execute |
| 4. Send confirmation email | recipient address logged | n/a — step never ran | ❌ not applicable, step didn't execute |

## Suggested Fixes

1. **Business-level (priority 1):** ORD-1042 is currently an orphaned validated-but-unpaid order. Confirm there's a downstream process (retry, customer notification, or order cancellation) that picks this up — the plan doesn't specify what happens to an order after a declined charge, and nothing in this log shows the customer being informed.
2. **Logging (priority 2):** Emit the order total as its own field at the "order validated" step (e.g. `order validated order_id=... item_count=3 order_total=142.50`). This lets future reviews verify "charge amount == order total" independently instead of inferring the total from the charge-attempt line.
3. **Logging (priority 3):** Consider a `payment retry` or `payment declined — no retry configured` line distinguishing single-attempt-and-abort from a retry policy, so it's clear from the log alone whether a retry was even attempted.

## Assumptions / Open Questions

- [ASSUMPTION] Treated `amount=142.50` on the charge-attempt line as the intended order total, since no separate order-total field exists in the log to cross-check step 2's expected output ("charge amount must match order total").
- [OPEN] Does the system retry a declined card or notify the customer/ops for ORD-1042? Not covered by this log or the plan.
- [OPEN] Is "abort the whole run on charge failure" the intended design, or should validation/charge failures be isolated per-order in a batch context? The plan doesn't state pipeline scope (single order vs batch), so this can't be assessed from the doc alone.
