---
name: compound-learning-tracker
description: Use when the user is learning a new skill (music theory, Rust, quant trading, an instrument) and hits a plateau, feels like giving up, or asks "am I learning this the right way." Triggers on phrases like "I can't keep going with this", "feels like no progress", "should I switch methods", "is this exercise even useful", and on their Traditional Chinese equivalents 「卡住了」「沒進步」「練不下去」「學不下去」「要不要換方法」「這樣練有用嗎」「是不是白費工」. Counters the ESTP tendency to abandon long-horizon learning out of boredom, replacing abstract willpower with concrete milestones.
triggers:
  - I can't keep going with this
  - feels like no progress
  - should I switch methods
  - is this exercise even useful
  - 卡住了
  - 沒進步
  - 練不下去
  - 學不下去
  - 要不要換方法
  - 這樣練有用嗎
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Compound Learning Tracker

**Announce at start:** "I'm using the bridge-mind:compound-learning-tracker skill to check what actually happened this week before deciding whether to change course."

## Core Principle

ESTPs are prone to giving up on learning paths that require long-term accumulation before results show
(music theory, Rust's ownership system, and trading psychology training all fall into this category) —
usually because it feels "too repetitive, too boring." This skill isn't about telling the user to
"just push through"; it's about breaking long-term goals into short cycles with immediate feedback,
so the Se-driven need for in-the-moment payoff aligns with the long-term compounding goal.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)**. The
distinction between "you have not progressed" and "you have progressed but cannot feel it" is the entire
point of this skill, and compression collapses exactly that distinction into something that reads like a
verdict of failure. Say it in full sentences.

## Step 1 — Gather Evidence Before Asking Anything

Do not open by asking the user how it has been going. Their gut feeling is the thing under investigation,
so it cannot also be the evidence. Measure first:

```bash
git log --since="2 weeks ago" --oneline --author="$(git config user.name)" 2>/dev/null | wc -l
git log --since="2 weeks ago" --stat --oneline 2>/dev/null | tail -30
ls -lt docs/finance/backtests/ 2>/dev/null | head -10
```

Adapt the commands to the domain — commit counts and diff sizes for code, files in an output directory
for backtests, practice logs or recording files for an instrument. Look across the last 2 weeks, not the
last 2 days: a real plateau does not show up in a 48-hour window, and a bad day reads as one.

If no measurable trace exists at all, say so plainly. "There is no record of the last two weeks, so
neither of us can tell whether this is a plateau" is a genuine finding, and it points at the fix.

## Step 2 — Diagnose Real Plateau vs. Perceived Plateau

Compare the evidence from Step 1 against the user's stated feeling.

- **Output present, feeling absent** → this is a perceived plateau. Show the numbers. Most ESTP
  "I'm not improving" reports are really "I stopped getting a visible hit of progress," which is a
  feedback-loop problem, not a learning problem. Go to Step 3.
- **Output genuinely absent** → this is an attention problem, not a learning-method problem. Changing
  textbooks will not fix it. Ask what displaced the time.
- **Output present and quality flat** → a real plateau. This is the only case where changing method is
  the right call.

## Step 3 — Redesign the Feedback Loop

If the current learning method's feedback cycle takes longer than a week to show results, carve out a
sub-task that produces a visible result within 3 days. For example, for learning Rust ownership, don't say
"write more code" — assign "rewrite the simplest tool from your existing Python scripts in Rust, get it
running today."

## Step 4 — Allow Lateral Pivots, Not Abandonment

If the user is genuinely bored with the current path, don't lecture about "sticking with it" — find a more
varied task under the same goal (e.g., if music theory drills feel dry, switch to "analyze the chord
progression of a song you like" for a more hands-on feel).

## Step 5 — Track Milestones

Proactively help log progress with comparable concrete metrics (BPM, piece difficulty, number of passing
tests, strategy Sharpe ratio) instead of letting "how it feels" drive the judgment. A metric that was not
recorded last month cannot show progress this month, which is why Step 1 so often comes up empty.

## Example

User says: "Music theory feels stuck, thinking about switching methods."

Check what was actually analyzed or practiced recently, then ask: is the block in understanding the theory
or in applying it to actual arrangement? Then assign one task completable today, rather than recommending
an entirely new textbook.
