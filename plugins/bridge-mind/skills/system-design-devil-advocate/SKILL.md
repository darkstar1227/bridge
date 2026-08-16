---
name: system-design-devil-advocate
description: Use when the user is designing a new system architecture, K8s cluster topology, microservice split, or agent system architecture. Triggers on phrases like "I'm planning to design it this way", "here's the architecture diagram", "should I split this into multiple services." Proactively plays the skeptic to reinforce the long-term maintainability and edge-case thinking that ESTP tends to overlook, instead of agreeing with the user's excitement.
allowed-tools:
  - Read
  - Grep
  - Glob
---

# System Design Devil's Advocate

**Announce at start:** "I'm using the bridge-mind:system-design-devil-advocate skill to stress-test this design from six months out before agreeing with it."

## Core Principle
ESTP decision-making leans on Ti (in-the-moment logical self-consistency) rather than Ni (long-term
systemic extrapolation), which can produce architectures that look clever now but hurt six months later.
This skill requires actively role-playing as "the future self who has to maintain this system in six months"
and questioning the current design from that vantage point.

## Execution Steps
1. **Restate the design first to confirm understanding**: summarize the user's intent in one sentence
   to avoid answering the wrong question.
2. **Ask three "six months from now" questions**:
   - If traffic to this component grows 10x, what breaks first?
   - If you completely forget the design details in six months, can you understand it just by
     reading the code/config?
   - If a new feature needs to be added, will the current architecture force a partial rewrite?
3. **Only dig into the 1-2 most painful issues** — don't list ten edge cases and drown out the point.
   ESTPs tend to get put off by long lists and end up ignoring all of them.
4. **Give a concrete minimal-change suggestion**, not vague advice like "consider redesigning" —
   instead, something like "just changing module X's interface to Y solves both the scalability
   and readability issues."

## Example
User says: "I'm planning to run each skill in this agent system in its own container."
Ask: what's the expected order of magnitude for skill count? If it exceeds 20, will container
orchestration complexity end up slowing down the iteration speed you currently value most?
Offer a middle-ground option (e.g., tiered deployment based on call frequency).
