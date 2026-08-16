---
name: distraction-capture
description: Use the moment a new idea, bug, or tangent surfaces mid-task and threatens to pull the user off what they were doing. Triggers on phrases like "I'll just quickly", "wait, what about", "oh I should also", "while I'm in here", "that reminds me", "hold on, first let me", and on their Traditional Chinese equivalents 「順便」「我先弄一下」「突然想到」「岔題一下」「等等,那個」「反正都開了」. Parks the new thing in a reviewable inbox in one action with zero questions asked, so the fear of forgetting it stops being a reason to chase it — while triaging first for the case where it actually blocks the current work.
triggers:
  - I'll just quickly
  - wait, what about
  - oh I should also
  - while I'm in here
  - that reminds me
  - 順便
  - 我先弄一下
  - 突然想到
  - 岔題一下
  - 反正都開了
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
---

# Distraction Capture

**Announce at start:** "I'm using the bridge-mind:distraction-capture skill to park that without losing it."

## Core Principle

The reason a tangent gets chased is rarely that it is more important. It is that **it will be forgotten if not acted on now**, and that fear is well-founded — for someone whose working memory drops things reliably, "I'll remember to come back to it" has been false often enough to be untrustworthy.

So the intervention is not discipline. It is a trustworthy place to put things. Once the idea is demonstrably safe, the pressure to act on it immediately disappears, because that pressure was never really about the idea's urgency.

**Two properties make this work, and losing either one breaks it completely:**

1. **Capture is instant.** If parking something costs thirty seconds of dialogue, the user chases it instead — the tangent is faster than the tool meant to defer it.
2. **The inbox is genuinely reviewed.** An inbox that becomes a graveyard teaches, correctly, that parking equals discarding. After that the user stops parking, and the skill is worse than useless because it also consumed the trust.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)** — but this skill's response should be one or two lines regardless. Not because of compression: because a long response to an interruption *is* the interruption.

## Step 1 — Triage in Five Seconds

Before parking anything, one question — answered by you, not asked of the user:

**Does this block the current task?**

- **Yes, it blocks** → this is not a distraction. It is a discovered dependency, and deferring it means the current task cannot finish. Say so in one line and handle it now.
- **No** → park it. Everything below.

Genuine blockers are much rarer than they feel in the moment. "While I'm in here I should also rename this" does not block anything. "This function I need does not exist yet" does. When it is truly ambiguous, park it — a wrongly parked item costs one review cycle, while a wrongly chased one costs the session.

## Step 2 — Capture in One Action, Asking Nothing

Append one line to `.bridge/inbox.md`. Create the file with a `# Inbox` header if it does not exist.

```markdown
- [ ] 2026-08-16 14:32 — Retry wrapper should probably use exponential backoff, currently fixed 200ms. Seen in `src/auth/retry.ts:34` while fixing the 429 test. (from: auth retry work)
```

Each entry carries: date and time, the idea in the user's own framing, the file and line if there is one, and what was being worked on when it surfaced. That last part is what makes it resumable later — an idea without its originating context frequently becomes unreadable within a week.

**Ask nothing.** Not for a priority, not for a category, not for clarification. Infer what is needed from the conversation and write it. Every question asked here is a chance to get pulled into discussing the tangent, which is exactly the outcome being prevented.

Markdown, not JSONL — the user has to be able to read and edit this by hand.

## Step 3 — Return to the Original Work Immediately

Close by naming what was being done before, so the thread is handed back rather than left for the user to re-find:

> "Parked. You were on the 429 timeout assertion in `auth.test.ts:47`."

That single sentence is the most valuable part of this skill. The interruption's real cost is the lost thread, not the lost seconds, and restating it is what keeps the cost near zero.

## Step 4 — Keep the Inbox Alive

The inbox is only trustworthy if things leave it. Two mechanisms:

- `unfinished-work-audit` reads `.bridge/inbox.md` and includes its items in the ship / kill / park pass. That is the scheduled review, and it is where most items should be resolved.
- When the inbox passes **15 open items**, mention it once — not as a backlog warning, but as an offer: "The inbox is at 16. Want to run `unfinished-work-audit` and clear it?" Most entries at that point will be killed in seconds, which is a good outcome and should be framed as one.

**Killing an inbox item is a success.** Say so when it happens. If the inbox only ever accumulates, it becomes a record of unmet obligations, and a record of unmet obligations is something people stop opening.

## What This Skill Must Never Do

- **Never discuss the merits of the parked idea.** Not one sentence of evaluation. Discussing it is chasing it, more slowly.
- **Never suggest doing it now** unless Step 1 found it genuinely blocking.
- **Never comment on the frequency of interruptions.** Not a count, not a pattern observation, not a gentle note.
- **Never ask the user to categorize or prioritize it.** That is work, and it is being asked at the exact moment their attention is already split.

## Boundary vs Other Skills

| Situation | Skill |
|---|---|
| New thing surfaced right now, park it | **this skill** |
| Review everything parked and decide | `unfinished-work-audit` |
| Thread already lost | `resume-interrupted-work` |
| The new thing is genuinely irreversible/risky | `risk-brake-thinking` |

## Example

User says: 「等等,我順便把那個 retry 改成 exponential backoff 好了」

Don't: discuss backoff strategies, ask whether it is urgent, or start editing.

Do: append it to `.bridge/inbox.md` with the file, line, and originating task, then —

> "Parked with the file reference. You were on the 429 timeout assertion at `auth.test.ts:47`."
