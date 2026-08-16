---
name: compound-learning-tracker
description: Use when the user is learning a new skill (music theory, Rust, quant trading, an instrument) and hits a plateau, feels like giving up, or asks "am I learning this the right way." Triggers on phrases like "I can't keep going with this", "feels like no progress", "should I switch methods", "is this exercise even useful." Counters the ESTP tendency to abandon long-horizon learning out of boredom, replacing abstract willpower with concrete milestones.
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Compound Learning Tracker

**Announce at start:** "I'm using the bridge-mind:compound-learning-tracker skill to check what actually happened this week before deciding whether to change course."

## Core Principle
ESTPs are prone to giving up on learning paths that require long-term accumulation before results show
(music theory, Rust's ownership system, and trading psychology training all fall into this category) —
usually because it feels "too repetitive, too boring." This skill isn't about telling the user to
"just push through"; it's about breaking long-term goals into short cycles with immediate feedback,
so the Se-driven need for in-the-moment payoff aligns with the long-term compounding goal.

## Execution Steps
1. **Diagnose real plateau vs. perceived plateau**: ask what was actually practiced in the last week.
   Often it's "feels like no progress" rather than "actually no progress" — compare against concrete
   output (lines of code written, pieces practiced, backtests run) instead of relying on gut feeling.
2. **Redesign the feedback loop**: if the current learning method's feedback cycle takes longer than
   a week to show results, carve out a sub-task that produces a visible result within 3 days.
   For example, for learning Rust ownership, don't say "write more code" — assign "rewrite the simplest
   tool from your existing Python scripts in Rust, get it running today."
3. **Allow lateral pivots, not abandonment**: if the user is genuinely bored with the current path,
   don't lecture about "sticking with it" — find a more varied task under the same goal
   (e.g., if music theory drills feel dry, switch to "analyze the chord progression of a song you like"
   for a more hands-on feel).
4. **Track milestones**: proactively help log progress with comparable concrete metrics
   (BPM, piece difficulty, number of passing tests, strategy Sharpe ratio) instead of letting
   "how it feels" drive the judgment.

## Example
User says: "Music theory feels stuck, thinking about switching methods."
Ask: what specifically was analyzed/practiced recently? Is the block in understanding the theory
or in applying it to actual arrangement? Then assign one task completable today, rather than
recommending an entirely new textbook.
