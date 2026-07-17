---
name: check-opencode-models
description: Fast two-stage check for a list of OpenCode models — ping (reachability/auth) followed by one real, minimal single-shot prompt test to catch models that ping fine but are actually slow or wrong under real dispatch. Reports which models are usable right now vs. reachable-but-slow vs. reachable-but-wrong vs. unreachable. Lighter than a full benchmark. For a deep quality/discipline benchmark across multiple task shapes, use benchmark-opencode-models instead.
allowed-tools:
  - Bash
  - AskUserQuestion
triggers:
  - check opencode models
  - is this opencode model available
  - is this opencode model too slow
  - ping opencode models
  - which opencode models are up right now
---

# Check OpenCode Models

**Announce at start:** "I'm using the check-opencode-models skill to quickly check which OpenCode models are usable right now."

This is the **cheap, fast** check — still far lighter than `bridge:benchmark-opencode-models` (which dispatches 5 real tasks per model across feature/bugfix/TDD prompts and scores 7 dimensions), but it does more than a bare ping. Two stages, run per model:

1. **Ping** (reuses `opencode-bridge`'s `dispatch.ping_model`) — reachability/auth only, no repo touched. A model that fails ping skips stage 2 entirely and is reported unreachable.
2. **Prompt test** — one real, minimal single-shot dispatch (`add_one(x)` on a throwaway `calc.py`), independently verified by executing the result. This exists because ping's own prompt ("reply with the word OK") is too trivial to reveal latency under an actual coding task — a model can ping back in 2 seconds and still take 90+ seconds to do anything real. Elapsed time here is compared against `--slow-threshold` and flagged if it's too slow.

Use this before a benchmark run to filter out dead-or-sluggish models cheaply, or any time the question is "can I actually use model X right now, and will it respond fast enough."

## Step 1: Determine which models to check

Ask the user which models (or default to `~/.opencode-bridge/config.json`'s `default_model` + `fallback_models`, or a provider tier from `opencode models`).

## Step 2: Run the check

```bash
uv run skills/check-opencode-models/scripts/check.py \
  --models "model/a,model/b,model/c" \
  --ping-timeout 30 \
  --prompt-timeout 150 \
  --slow-threshold 45 \
  --out docs/opencode-model-tests/<date>-availability.json
```

`--out` is optional — omit it for a one-off terminal check with no file left behind. `--slow-threshold` is the elapsed-seconds cutoff for the prompt test above which a model is flagged `slow` even though it completed correctly — tune it to how much latency is actually tolerable for the caller's use case (an interactive check tolerates less than a background batch job would).

**Where the 45s default came from**: calibrated by running this same `add_one()` prompt test against 11 models `benchmark-opencode-models` had already confirmed produce correct output (the fibonacci PASS set from an earlier manual round). Real elapsed times split into two clean clusters: 17.6-26.5s for `opencode`-zen and most `openrouter` free models, and 83.7-119.6s for `litellm`-routed models (structurally slower, not broken). 45s sits near the geometric mean of those two clusters — comfortable margin above the fast cluster's max, comfortable margin below the slow cluster's min. `--prompt-timeout` defaults to 150s specifically so the slow-but-correct 119.6s case doesn't get cut off as a false `TIMED_OUT`. If re-calibrating for a different task shape or model set, rerun this same process (known-good models → real elapsed times → look for the natural cluster gap) rather than guessing a round number.

**Caveat observed during calibration**: 4 of the 11 models timed out at 180s when 6 were dispatched concurrently against `openrouter` at once. The initial hypothesis was transient rate-limiting from the concurrent load — but a follow-up retry of one of them (`openrouter/cohere/north-mini-code:free`) run completely serially, no concurrency, **also timed out at 180s**. That rules out concurrency as the sole explanation; at minimum this specific model's `openrouter` free-tier availability was genuinely unreliable at the time of testing, not just contended. Treat a `TIMED_OUT` result as "unusable right now" rather than assuming it's a measurement artifact — if it matters, retest that model alone at a different time before concluding it's permanently broken, but don't wave away a repeat timeout as "just rate limiting" without actually re-confirming serially, the way this note almost did.

## Step 3: Report

Present four buckets, not just pass/fail:
- **Usable now** — reachable, prompt test `DONE`, output verified correct, and under the slow threshold.
- **Slow** — everything above held except elapsed time exceeded `--slow-threshold`. Report the actual elapsed seconds so the caller can judge for themselves.
- **Reachable but wrong** — ping passed and the dispatch completed, but the independently-verified output was incorrect (or, per the earlier ad-hoc test round, `DONE` with zero files changed — a fake completion).
- **Unreachable** — ping itself failed, with the failure reason opencode-bridge surfaces (auth error, unknown model, timeout, etc.) so it's directly actionable (e.g. "needs `GOOGLE_GENERATIVE_AI_API_KEY` set" vs. "genuinely down, try again later").

## Known output paths

Reports from this skill go to `docs/opencode-model-tests/` (same directory as `benchmark-opencode-models`, create if missing) when `--out` is passed.
