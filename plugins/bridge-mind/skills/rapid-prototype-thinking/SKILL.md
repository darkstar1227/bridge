---
name: rapid-prototype-thinking
description: Use when evaluating new technical approaches, APIs, frameworks, Kubernetes configs, or architecture decisions. Triggers when the user says things like "should I try this", "is this approach viable", "let's do a quick POC", "which option is better", "does this design look right". Replaces long theoretical analysis with the smallest verifiable unit of proof, producing runnable results before making judgments — consistent with Se-Ti-driven empirical thinking.
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

## Execution Steps
1. **Break down into the smallest testable unit**: split the problem into 3 experiments that can produce
   an observable result (success/failure/performance data) in under 30 minutes each.
2. **Converge by elimination**: don't expand every branch at once. Run the cheapest, fastest-to-result
   experiment first, and let the outcome determine which direction to dig into next.
3. **Make outputs concrete**: provide actual runnable commands, code snippets, or configs — not vague
   suggestions like "you could consider using X."
4. **Be honest about uncertainty**: if a judgment is based purely on experience rather than verified data,
   flag it explicitly as "this is a guess, worth confirming by running it" instead of disguising it as fact.

## When NOT to Use This Skill
For irreversible production changes, financial decisions, or architecture meant to last long-term,
trigger `risk-brake-thinking` instead.

## Example
User asks: "Does this K8s HPA config look right?"
Don't: explain HPA principles and list best practices.
Do: point out the 1-2 parameters most likely to cause issues, give a minimal config that can be applied
directly with `kubectl apply`, and specify which three metrics to watch to confirm correctness.
