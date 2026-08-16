---
name: risk-brake-thinking
description: Use for irreversible production changes, going live with a quant trading strategy, financial decisions, database migrations, force-pushes, or any scenario where a mistake is hard to roll back. Triggers on phrases like "about to deploy", "about to place the order", "about to delete", "about to migrate", "taking this strategy live", "ship it", "just push it", and on their Traditional Chinese equivalents 「要部署了」「要上線了」「要下單」「要刪掉」「要跑 migration」「這個策略要進實盤」「直接推上去」「可以上了嗎」. Forces the downside-risk assessment that ESTP naturally tends to skip, asking "what's the worst case, and can it be undone?" before acting.
triggers:
  - about to deploy
  - about to place the order
  - about to delete
  - about to migrate
  - taking this strategy live
  - ship it
  - 要部署了
  - 要上線了
  - 要下單
  - 要刪掉
  - 要跑 migration
  - 這個策略要進實盤
  - 直接推上去
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Bash
---

# Risk Brake Thinking

**Announce at start:** "I'm using the bridge-mind:risk-brake-thinking skill to check reversibility and worst-case before this action."

## Core Principle

The user is an ESTP — naturally strong at improvising in the moment, but prone to underestimating
long-term or systemic risk, especially when excited. This skill isn't about being a killjoy; it's about
trading 30 seconds of checklist time for avoiding an irreversible loss.

## Hard Constraint on Tool Use

`Bash` is available for **read-only inspection only** — `git status`, `git log`, `git diff`,
`kubectl get`, `terraform plan`, `ls`, `cat`. **Never execute the action under review from inside this
skill**: no `apply`, `push`, `destroy`, `drop`, `rm`, `publish`, or any live-order call. This skill
assesses; the user decides; the main thread executes afterwards if they choose to.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)**. Write
the verdict block's text fields in full, normal sentences — articles and connecting words intact.

The block below is *structurally* compact (fixed fields, scannable in seconds). That is not the same as
grammatical compression. Keep the structure tight and the wording complete. An ambiguous risk warning is
worse than no warning at all, and this is exactly the case that terseness modes carve out for safety.

## Step 1 — Check the Decision Journal First

Before warning, read the track record:

```bash
test -f .bridge/decisions.jsonl && cat .bridge/decisions.jsonl || echo "NO_JOURNAL"
```

Calibrate against it:

- **No journal / no comparable entry** → give the full checklist below.
- **Same action class overridden 3+ times with no bad outcome recorded** → you are crying wolf. Compress
  to a single line ("You have done this 4 times without incident; the only untested part here is X") and
  do not re-run the full checklist.
- **Any entry for this action class with a bad outcome** → lead with that entry, quoted. For an ESTP, a
  record of what actually happened is the only argument that reliably lands. Abstract risk reasoning is not.

## Step 2 — The Checklist (mandatory unless Step 1 said to compress)

1. **Reversibility check**: can this action be undone within 5 minutes? If not, explicitly flag
   "⚠️ Irreversible action."
2. **Quantify worst case**: don't ask "could this go wrong" — ask "if it does go wrong, what's the maximum
   loss (money, data, downtime)?" Give concrete numbers, not vague statements like "there's some risk."
3. **Rollback plan comes first**: provide the rollback plan before the execution plan. If no rollback plan
   can be found, that itself is a red flag worth calling out explicitly.
4. **Delayed-gratification check**: if the user shows urgency to act "right now," proactively ask
   "does this need to happen now, or can it be validated in a test environment / paper trading /
   small position overnight first?"

## Step 3 — Emit the Verdict Block

Always this shape, nothing longer:

```
⚠️ IRREVERSIBLE          (or: ✅ REVERSIBLE — undo takes <n> min)
Worst case:   <concrete number: dollars, rows, minutes of downtime>
Rollback:     <exact command, or NONE ← red flag>
Cheaper test: <staging / paper trade / small position / dry-run flag>
Past record:  <from journal, or "first time">
```

Prose commentary after the block: at most two sentences. If it needs more than that, the risk is
genuinely complex — say so explicitly and ask whether the user wants the long version, rather than
producing it unprompted.

## Step 4 — When the User Pushes Back

They will say 「直接做」 / "just do it" / "I know, ship it". This is expected, not a failure.

**Rule: state the worst case once, then comply.**

- Do **not** repeat a warning already given in this session for the same action. One warning is a signal;
  two is noise, and an ESTP who has learned to tune this skill out has lost its protection permanently.
- Do not moralize, do not add a disappointed closing line, do not re-litigate.
- Record the override (Step 5), then get out of the way.

The single exception: if the user's stated reasoning contains a **factual error** about reversibility
(they believe a rollback exists that does not), correct that specific fact once. That is new information,
not a repeated warning.

## Step 5 — Record the Decision

Append one line to `.bridge/decisions.jsonl` (read the file first, then write it back with the new line
appended — this is an append-only log):

```json
{"date":"YYYY-MM-DD","action":"deploy api to prod","class":"deploy","irreversible":true,"worst_case":"~30min downtime","warned":true,"overridden":true,"outcome":null}
```

Field notes:

- `class` — coarse bucket for Step 1 lookup: `deploy`, `migration`, `delete`, `trade`, `force-push`, `publish`.
- `outcome` — leave `null` now. When the user later mentions how it went, update that entry to `"ok"` or a
  short description of what broke. This is what makes the journal worth keeping.
- Never write credentials, tokens, account numbers, or position sizes in dollar terms into this file.

If `.bridge/` does not exist, create the file anyway and mention that `.bridge/decisions.jsonl` should be
gitignored (it is personal decision history, not shared repo state).

## Unattended and Batch Contexts

When running under `/loop`, a batch pipeline, or any autonomous context where no one is present to answer:

**Do not block.** Emit the verdict block, record the decision with `"overridden":true` and
`"context":"unattended"`, and surface the warning in the run's final report. A skill that stalls an
unattended loop waiting for an answer nobody will give is worse than one that documents and continues.

The sole exception: an action in the `trade` class with real money. Halt there and report, regardless of
context.

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
