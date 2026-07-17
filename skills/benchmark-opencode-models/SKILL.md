---
name: benchmark-opencode-models
description: Deep-benchmark which OpenCode models are actually viable for opencode-bridge — ping each candidate model, then run 5 canned superpowers-style task prompts per model (feature vs bugfix, short vs detailed, plus a dedicated TDD red-to-green prompt), independently verify every result by executing the generated code (never trust OpenCode's self-reported "done"), and score each run on time/quality/completeness/autonomy/discipline/red-green-accuracy/test-call-discipline. For a fast pass/fail availability check with no scoring, use check-opencode-models instead.
allowed-tools:
  - Bash
  - AskUserQuestion
triggers:
  - benchmark opencode models
  - deep test opencode models
  - which opencode models actually work
  - smoke test opencode-bridge models
  - tdd test opencode models
---

# Benchmark OpenCode Models

**Announce at start:** "I'm using the benchmark-opencode-models skill to deep-test which OpenCode models actually work."

This codifies the manual model-testing process (ping sweep, then a real fake-feature dispatch, then independent verification) into a repeatable skill, and extends it: instead of one throwaway "add fibonacci" prompt, every model gets 5 prompts that simulate the shape of a real `superpowers:subagent-driven-development` implementer task — full context/acceptance-criteria/constraints/definition-of-done, not just a one-liner — across a feature direction, a bugfix direction (each at both a short and a detailed prompt length), and a dedicated TDD red-to-green prompt.

This is the **deep, expensive** test — it dispatches a real OpenCode run per model per prompt (5 real dispatches per model). For a quick "is this model even reachable right now" check before committing to this, run `bridge:check-opencode-models` first.

## Step 1: Determine which models to test

Ask the user (via AskUserQuestion if not already stated) which models to test, or default to:
```bash
cat ~/.opencode-bridge/config.json   # default_model + fallback_models
opencode models                       # full catalog, to pick a provider/tier (litellm, openrouter free, opencode zen free, etc.)
```
Build a comma-separated model list. Keep the list to what's actually in question — this dispatches 5 real tasks per model, so testing 10 models means 50 real OpenCode runs (plus one ping each).

## Step 2: Run the benchmark script

```bash
uv run skills/benchmark-opencode-models/scripts/smoke_test.py \
  --models "model/a,model/b,model/c" \
  --repo-root /tmp/opencode-benchmark-repos \
  --per-attempt-timeout 240 \
  --ping-timeout 30 \
  --out docs/opencode-model-tests/<date>-benchmark-results.json
```

This runs, per model:
1. **Ping** (reuses `opencode-bridge`'s `dispatch.ping_model`) — a model that fails ping gets all 5 tests recorded as `PING_FAILED` with score 0 across the board, no real dispatch wasted on it.
2. **5 single-shot dispatches**, each in its own throwaway git repo (never shared — avoids the git-race issue `opencode-bridge` itself warns about):
   - `feature_short` — one-line "add `is_prime(n)`" prompt, bare `calc.py` stub.
   - `feature_detailed` — full spec-style prompt (Context/Task/Acceptance Criteria/Constraints/Definition of Done) for the same `is_prime(n)` function, repo pre-seeded with an unrelated `double(x)` function the model must not break.
   - `bugfix_short` — one-line "average(nums) has a bug, fix it" prompt, repo pre-seeded with a broken `average`.
   - `bugfix_detailed` — full spec-style bug report (repro steps, expected vs actual, constraints) for the same bug, repo also seeded with the unrelated `double(x)` function.
   - `tdd` — explicitly instructs red→green TDD: run a fixed verification command first to confirm `is_leap_year` doesn't exist yet (RED), implement it, then re-run the *same* verification command to confirm it now passes (GREEN). The prompt gives the exact command up front so matching tool calls in the event stream is unambiguous.
3. **Independent verification** — for every test that self-reports `DONE`, the script actually runs `python3 -c "import calc; assert ..."` for each acceptance-criteria check separately (so a missing function doesn't hide whether unrelated checks would've passed) — it never trusts OpenCode's own "done" claim.

`--per-attempt-timeout` here is deliberately a **single attempt, no retry/fallback** — this measures raw single-shot model capability, not opencode-bridge's production reliability (which does retry + fallback chains). Don't reuse this script's results as a substitute for opencode-bridge's own retry-aware dispatch behavior.

## Step 3: Scoring rubric (deterministic, computed by the script — do not re-score by feel)

`feature_short` / `feature_detailed` / `bugfix_short` / `bugfix_detailed` each get 5 scores, 0-5:

- **時間 (time)**: banded on wall-clock seconds for that single attempt — ≤20s→5, ≤45s→4, ≤90s→3, ≤180s→2, else→1. A non-`DONE` result is capped at 1 regardless of elapsed time.
- **品質 (quality)**: `5 × (independent checks passed / checks total)`, rounded. A non-`DONE` result scores 0 — self-reporting done and being wrong is not the same as never finishing, and both are visible in `terminal_state`/`issues`.
- **完整性 (completeness)**: same checklist as quality in this harness (every check maps to a specific acceptance-criteria line), reported as a separate field since a hand-written spec in real use would have criteria that don't all collapse to the same checklist as the "does it basically work" check.
- **自主性 (autonomy)**: starts at 5, -1 if it never reached `DONE`, -2 if it claimed `DONE` while changing zero files (`no_op` — the most dangerous failure mode found in the original manual test round: two `litellm` models did exactly this), -2 if its final text contains a clarifying-question marker instead of just doing the task.
- **紀律性 (discipline)**: starts at 5, -2 if it touched any file outside `calc.py` (`unexpected_files`, ignoring `__pycache__` noise), -2 if it broke the pre-seeded unrelated `double(x)` function in the detailed-prompt tests (only checked when that check exists).

`tdd` gets its own two dedicated scores, on top of the standard `time` score (`quality`/`completeness`/`autonomy`/`discipline` from the checklist above still apply too, using the same final-state verification):

- **紅綠準確度 (red_green_accuracy)**: parses the OpenCode event stream for `bash` tool calls whose command references the task's fixed verification command, in chronological order.
  - **5**: the *first* matching call failed (RED, exit code non-zero — proves it actually checked "not implemented yet" before writing code) and the *last* matching call passed with the expected output (GREEN) — genuine red→green discipline, and the final code independently verifies correct.
  - **4**: red→green order held, final code correct, but reaching green took more than one attempt after the first edit (legitimate debug loop, not penalized further here — see `test_call_discipline` for that).
  - **3**: final code independently verifies correct, but the model skipped the RED step (jumped straight to implementation then verified once) — it didn't actually do the TDD it was asked to do, even though the answer is right.
  - **1**: attempted the verification command at least once but the final code is wrong.
  - **0**: never ran the given verification command at all, or never touched `calc.py`.
- **測試呼叫紀律 (test_call_discipline)**: counts how many times the *same* fixed verification command was invoked across the whole run. Since the prompt hands over one command that covers every case in a single call, the ideal TDD loop is exactly 2 invocations (one RED, one GREEN) — every call beyond that is either a fumbled implementation needing another look, or aimless re-running without changing anything in between.
  - 2 calls → 5, 3 calls → 4, 4 calls → 3, 5-6 calls → 2, 7+ calls → 1, 0-1 calls → 0.

Report per-test scores in a table, plus a per-model average. Always call out any `no_op: true` result by name — a model that fakes completion is worse than one that visibly fails, since a caller trusting the handoff report alone would ship broken/absent code. For the `tdd` test specifically, call out any model that scores `red_green_accuracy <= 3` despite being explicitly told to do TDD — that's a model that will silently skip TDD discipline as a `subagent-driven-development`/`executing-plans` implementer even when the plan enforces it.

## Step 4: Compare short vs. detailed prompts

For each model, explicitly note whether the detailed prompt scored differently from the short prompt on the same direction (feature or bugfix) — a large gap either way is itself a finding:
- Detailed prompt scores much higher → the model needs full spec context to behave (relevant for whether it's safe as a `subagent-driven-development`/`executing-plans` implementer, which always sends full context).
- Detailed prompt scores lower or the same → extra spec detail isn't helping, or the model degrades under longer prompts (worth flagging — might indicate a small context window or weaker instruction-following at length).

## Known output paths

Reports from this skill go to `docs/opencode-model-tests/` (create the directory if missing) — matches this repo's convention of every skill declaring its own output path in `CLAUDE.md`.
