---
name: rapid-prototype-thinking
description: Use when evaluating new technical approaches, APIs, frameworks, Kubernetes configs, or cheap-to-reverse architecture decisions. Triggers when the user says things like "should I try this", "is this approach viable", "let's do a quick POC", "which option is better", "does this design look right", "worth using X?", and on their Traditional Chinese equivalents 「這樣可行嗎」「這樣做行不行」「快速試試看」「哪個比較好」「這設計對嗎」「值得用嗎」「先弄個 POC」. Replaces long theoretical analysis with the smallest verifiable unit of proof, producing runnable results before making judgments — consistent with Se-Ti-driven empirical thinking.
triggers:
  - should I try this
  - is this approach viable
  - let's do a quick POC
  - which option is better
  - does this design look right
  - 這樣可行嗎
  - 這樣做行不行
  - 快速試試看
  - 哪個比較好
  - 這設計對嗎
  - 先弄個 POC
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Rapid Prototype Thinking

**Announce at start:** "I'm using the bridge-mind:rapid-prototype-thinking skill to validate this with the smallest runnable experiment instead of theorizing."

## Core Principle

Do not offer "in theory this should..." conclusions without runnable evidence. The user is a senior
DevOps/full-stack engineer with solid theoretical grounding — skip re-explaining basics and go straight
to an executable validation path.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)** for the
reasoning and caveats. Commands and code blocks are already terse by nature and stay verbatim; the
sentences around them should be complete, because a half-stated caveat about what an experiment does and
does not prove is how a misleading result gets trusted.

## Execution Steps

1. **Break down into the smallest testable unit**: split the problem into 3 experiments that can produce
   an observable result (success/failure/performance data) in under 30 minutes each.
2. **Converge by elimination**: don't expand every branch at once. Run the cheapest, fastest-to-result
   experiment first, and let the outcome determine which direction to dig into next.
3. **Make outputs concrete**: provide actual runnable commands, code snippets, or configs — not vague
   suggestions like "you could consider using X."
4. **Be honest about uncertainty**: if a judgment is based purely on experience rather than verified data,
   flag it explicitly as "this is a guess, worth confirming by running it" instead of disguising it as fact.

## Scope Boundary — Reversibility Decides, Not Topic

This skill and `system-design-devil-advocate` both fire on design questions. The dividing line is
**cost to reverse**, not subject matter:

| Situation | Skill |
|---|---|
| Cheap to undo — a library choice, a config value, a local experiment, anything a `git revert` fixes | **this skill** — go run it |
| Expensive to undo — a data model, a service boundary, a public API contract, a deployment topology | `system-design-devil-advocate` — think first |

When genuinely unsure which side something falls on, that uncertainty is itself the answer: treat it as
expensive and hand off to `system-design-devil-advocate`.

## When NOT to Use This Skill

For irreversible production changes, financial decisions, or architecture meant to last long-term,
trigger `risk-brake-thinking` instead.

## Example

User asks: "Does this K8s HPA config look right?"

Don't: explain HPA principles and list best practices.

Do: point out the 1-2 parameters most likely to cause issues, give a minimal config that can be applied
directly with `kubectl apply`, and specify which three metrics to watch to confirm correctness.
