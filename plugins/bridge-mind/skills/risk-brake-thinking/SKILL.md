---
name: risk-brake-thinking
description: Use for irreversible production changes, going live with a quant trading strategy, financial decisions, database migrations, or any scenario where a mistake is hard to roll back. Triggers on phrases like "about to deploy", "about to place the order", "about to delete", "about to migrate", "taking this strategy live". Forces the downside-risk assessment that ESTP naturally tends to skip, asking "what's the worst case, and can it be undone?" before acting.
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Risk Brake Thinking

**Announce at start:** "I'm using the bridge-mind:risk-brake-thinking skill to check reversibility and worst-case before this action."

## Core Principle
The user is an ESTP — naturally strong at improvising in the moment, but prone to underestimating
long-term or systemic risk, especially when excited. This skill isn't about being a killjoy; it's about
trading 30 seconds of checklist time for avoiding an irreversible loss.

## Execution Steps (mandatory, do not skip)
1. **Reversibility check**: can this action be undone within 5 minutes? If not, explicitly flag
   "⚠️ Irreversible action."
2. **Quantify worst case**: don't ask "could this go wrong" — ask "if it does go wrong, what's the maximum
   loss (money, data, downtime)?" Give concrete numbers, not vague statements like "there's some risk."
3. **Rollback plan comes first**: provide the rollback plan before the execution plan. If no rollback plan
   can be found, that itself is a red flag worth calling out explicitly.
4. **Delayed-gratification check**: if the user shows urgency to act "right now," proactively ask
   "does this need to happen now, or can it be validated in a test environment / paper trading /
   small position overnight first?"

## Trading-Specific Checks
For quant trading strategies, additionally verify:
- Whether position size exceeds the user's usual risk exposure habits
- Whether the strategy has out-of-sample validation beyond backtesting
- Whether the stop-loss logic is hardcoded, rather than "I'll watch and decide manually"

## Example
User says: "This strategy backtested at 30% annualized, I'm taking it live with real money."
Ask first: how large is the position? What's the max acceptable drawdown? Is the stop-loss hardcoded
in the code or dependent on manually watching the screen? If any answer is "haven't thought about it,"
recommend running a minimal position for a week before scaling up.
