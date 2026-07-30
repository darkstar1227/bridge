---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
---

# Verification Before Completion

**Core principle:** Evidence before claims, always. Violating the letter of
this rule is violating the spirit of it — paraphrases, synonyms, and
implications of success are all covered, not just the exact phrases below.

## The Iron Law

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.** If you haven't
run the verification command in this message, you cannot claim it passes.

## The Gate Function

Before claiming any status or expressing satisfaction: identify what command
proves the claim → run the full command, fresh and complete → read the full
output, exit code, failure count → does it confirm the claim? If no, state
the actual status with evidence; if yes, state the claim with the evidence.
Only then make the claim. Skipping a step is lying, not verifying.

## Common Failures

| Claim | Requires | Not sufficient |
|-------|----------|----------------|
| Tests pass | Test output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Original symptom retested: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags — Stop

Using "should"/"probably"/"seems to"; expressing satisfaction ("Great!",
"Done!") before verifying; about to commit/push/PR without verification;
trusting an agent's own success report; relying on a partial check; thinking
"just this once" or being tired and wanting it over — none of these are
exceptions. Confidence is not evidence.

## Patterns

Tests: run the command, see e.g. `34/34 pass`, then claim "all tests pass" —
never "should pass now" or "looks correct". Regression tests need the full
red-green cycle: write → run (pass) → revert fix → run (must fail) → restore
→ run (pass) — not just "I've written a regression test". Build success
needs the build command's exit code, not the linter's. Requirements checks
need a re-read of the plan turned into a checklist, verified line by line —
not "tests pass, phase complete". Agent delegation needs the VCS diff
checked yourself, not the agent's self-report trusted as-is.
