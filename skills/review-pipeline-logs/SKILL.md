---
name: review-pipeline-logs
description: Query a project's local log files and review whether a just-developed application pipeline actually ran the way it was designed to. Reads the project's design/plan doc for the expected steps, parses the relevant log file(s), then checks the run against the plan step-by-step, flags errors/exceptions, judges whether logging is detailed and leveled clearly enough to debug from, and confirms output values matched expectations. Produces a detailed report (step-by-step results, error detail, suggested fixes) — not just a pass/fail line. Trigger this whenever the user asks to "review the logs," "check if the pipeline ran correctly," "查logs" "review pipeline log對不對", wants to confirm a feature just shipped is actually working end-to-end, or pastes/points at a log file and asks whether something looks right, even if they don't say the word "skill."
triggers:
  - review pipeline logs
  - check pipeline logs
  - review the logs
  - is the pipeline correct
  - 查詢 logs
  - review log
  - log 有沒有跑對
  - pipeline log review
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Review Pipeline Logs

**Announce at start:** "I'm using the bridge:review-pipeline-logs skill to check the pipeline's logs against the designed flow."

## Purpose

Code that compiles and a pipeline that ran are two different claims. This skill closes that gap: it takes the design doc that says what the pipeline is *supposed* to do, takes the log output from an actual run, and checks one against the other — step by step, not just "did it crash." A pipeline that finishes with no errors can still have skipped a step silently or written a wrong output value; a pipeline that logs nothing useful will bite the next person who has to debug it in production. Both are failures this skill should catch.

## Step 1 — Locate the Design/Plan Doc

This is the source of truth for what "correct" means. Search in this priority order:

1. A file path given in the user's request (if they named one)
2. `docs/plan.md`, `docs/spec.md`, `plan.md`, `spec.md`
3. Most recently modified `.md` under `docs/superpowers/input/` (gstack-to-plan handoffs live here)
4. Most recently modified `.md` under `docs/` (`ls -t docs/**/*.md 2>/dev/null | head -1`)
5. Most recently modified `.md` under `.gstack/`

Read the located file in full. If nothing is found, ask the user which doc describes the pipeline's intended steps — do not guess a design from the log alone, since that would just be checking the log against itself.

## Step 2 — Extract the Expected Steps

From the design doc, build an ordered list of pipeline steps. For each step, capture:

| Field | What it is |
|-------|-----------|
| **Step name** | Short label for the stage (e.g. "fetch source rows", "send Resend email") |
| **Expected trigger** | What kicks this step off — previous step's success, an event, a schedule |
| **Success signal** | What "this step worked" looks like — a return value, a status code, a downstream side effect |
| **Expected output values** | Any specific counts, thresholds, formats, or ranges the doc commits to |

If the doc lists steps explicitly, use its wording and order. If it only describes architecture or verification expectations, derive the step list from those sections and mark each derived step `[ASSUMPTION: derived from <section>]`. Don't silently invent steps the doc gives no basis for.

## Step 3 — Locate and Read the Logs

Ask the user for the log file/path if they already gave one; otherwise look for, in order:

1. A path named in the user's request
2. `logs/*.log` or `*.log` in the project root
3. Recent stdout/stderr capture files the user or a run command wrote (e.g. `*.out`, `nohup.out`)
4. If several candidates exist, or the log spans multiple runs, ask the user which run to review rather than guessing — reviewing the wrong run produces a confident, wrong report

Once you have the right file, isolate the specific run to review (not the whole file's history):

- If the log has a recognizable "run started" marker, take the block from the **last** such marker to EOF (or to the next marker, if the user pointed at an older run)
- Otherwise, use the tail of the file bounded by an obvious timestamp gap, or ask the user to help narrow it down

For a large log file, do this isolation pass with context-mode (`ctx_execute_file`/`ctx_batch_execute`) instead of reading the whole file into the conversation — only the isolated run block (or the specific lines you'll quote in the report) should actually enter context. Use `Read` directly once the file is already small enough, or once you know exactly which lines you'll quote verbatim.

## Step 4 — Check the Run Against the Design

Walk the expected steps from Step 2 in order. For each one, search the isolated log block for evidence of it and build a matrix:

| Step | Expected | Found in log? | Status | Evidence |
|------|----------|---------------|--------|----------|
| <name> | <success signal> | line ref or "not found" | ✅ ran & succeeded / ⚠️ ran but signal unclear / ❌ missing or failed | quote the relevant line(s) |

A step with no log evidence at all is not automatically a failure — it may have run silently — but it IS a logging gap (see Step 5) and should be called out as unverifiable rather than marked ✅ by assumption.

## Step 5 — Judge Logging Quality

Separately from whether the pipeline worked, judge whether the log would actually help someone debug this pipeline without re-running it:

- Does every step from Step 2 emit at least one line, or are some steps invisible?
- Are log levels used meaningfully (errors as ERROR/FATAL, not buried in INFO; routine progress not screaming as WARN)?
- Do lines carry enough context to act on (identifiers, counts, durations, which record/request failed) or just a bare "done"?
- Are failures logged with enough detail to diagnose (stack trace, input that caused it) or swallowed/logged as a one-word failure?

This becomes its own section in the report — a pipeline can pass every functional check and still get flagged here.

## Step 6 — Collect Errors and Exceptions

Scan the isolated log block for error signals (`ERROR`, `FATAL`, `Exception`, `Traceback`, `panic`, non-2xx status codes, etc.). For each hit:

- Quote the line(s) with surrounding context
- Classify it: **unexpected failure** (breaks a Step 2 expectation) vs **expected/handled** (e.g. a logged retry that then succeeded) — state which and why

If an error or stack trace points at source code in the project being reviewed, use codegraph (`codegraph_explore`/`codegraph_node`, or the `codegraph explore`/`codegraph node` CLI) to see what that code actually does, rather than `grep`/whole-file `Read`:

- No `.codegraph/` directory in that project yet → run `codegraph init <path>` first (it builds the initial index as part of init), then query it.
- `.codegraph/` already exists → run `codegraph sync <path>` first (or `codegraph index <path>` for a full rebuild if sync looks insufficient) so the index reflects the code as of this run, not a stale prior state — then query it.

## Step 7 — Check Output Values

Where Step 2 captured specific expected output values (counts, thresholds, status codes, formats), find the actual logged values and compare. Flag any mismatch explicitly — don't just note the value existed.

## Step 8 — Write the Report

Save to `docs/pipeline-reviews/pipeline-review-YYYY-MM-DD-<pipeline-slug>.md` (today's date, slug derived from the pipeline/feature name). Also summarize the verdict and top issues directly in chat — don't make the user open the file to learn whether it passed.

The report MUST follow this template:

```markdown
# Pipeline Log Review: <Pipeline Name>

_Design doc: <path>_
_Log source: <path, and which run/time-range was reviewed>_
_Reviewed: <today's date>_

## Verdict

<One of: PASS / PASS WITH WARNINGS / FAIL — one sentence why>

## Step-by-Step Results

<The matrix from Step 4>

## Logging Quality

<Findings from Step 5 — gaps, level misuse, missing context>

## Errors & Exceptions

<Findings from Step 6, each classified unexpected vs expected/handled>

## Output Value Checks

<Findings from Step 7 — expected vs actual, mismatches called out>

## Suggested Fixes

<Concrete, prioritized list — code/logging changes to make, not vague advice>

## Assumptions / Open Questions

- [ASSUMPTION] <where Step 2 or Step 3 had to guess> — <why>
- [OPEN] <anything the user should resolve or clarify>
```

## Notes

- This skill reviews evidence that already exists in the log. It does not run the pipeline itself — if no log exists yet, tell the user to run the pipeline first (or point out how) rather than fabricating findings.
- A step marked ❌ or ⚠️ is a finding, not an accusation — report it plainly with evidence and let the user decide whether it's actually a bug or an intentional behavior the design doc failed to mention.
