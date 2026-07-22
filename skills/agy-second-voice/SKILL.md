---
name: agy-second-voice
description: Get an independent, read-only second opinion from Antigravity CLI (`agy`, Google's coding agent) — review the current diff, adversarially challenge it, or consult it on a question/plan — as a cross-model check alongside Claude's own analysis. Use when asked to "agy review", "agy challenge", "ask agy", "second opinion", "antigravity review", or "second voice".
allowed-tools:
  - Bash
  - AskUserQuestion
  - Read
triggers:
  - agy review
  - agy challenge
  - ask agy
  - antigravity review
  - second voice
  - second opinion
---

# Agy Second Voice

**Announce at start:** "I'm using the agy-second-voice skill to get an independent opinion from Antigravity CLI."

This skill is **read-only by design**: it never passes `--dangerously-skip-permissions` to `agy`, so any tool call `agy` makes that would write/delete/execute is auto-denied by its headless mode (see "Read-only guarantee" below). It only reviews, challenges, or consults — it never fixes anything itself. For a write-capable delegate, use `bridge:opencode-bridge` instead.

## Step 0: Check the binary exists

```bash
command -v agy >/dev/null 2>&1 && echo FOUND || echo NOT_FOUND
```

If `NOT_FOUND`, stop and tell the user: "Antigravity CLI (`agy`) not found. Install it and re-run this skill."

## Step 1: One-time authorization to shell out to agy

This skill runs `agy` (Google's Antigravity CLI, a third-party agent) via `Bash`. Some permission configurations prompt on every such call since it looks like handing code to an external tool. Check once per project:

```bash
grep -r "agy" .claude/settings.local.json .claude/settings.json 2>/dev/null
```

If no matching rule exists, ask via AskUserQuestion:
- **Question**: "This skill needs to run `agy` (Google's Antigravity CLI) without a permission prompt each time. All calls are read-only — no `--dangerously-skip-permissions` is ever passed. Add a Bash allow rule to `.claude/settings.local.json`?"
- If yes, merge into `.claude/settings.local.json` (creating `permissions.allow` if absent):
  ```json
  { "permissions": { "allow": ["Bash(agy --add-dir=* --print=*)"] } }
  ```
- If declined, proceed anyway — each call will just prompt for permission.

Do this only once per project.

## Flag contract (agy quirks — read before writing any Bash call)

`agy`'s flag parser only accepts `=`-joined long flags, not space-separated values, and it never defaults to the current directory — it needs an explicit workspace. Every invocation in this skill MUST use this shape:

```bash
agy --add-dir="$(git rev-parse --show-toplevel)" --print="<prompt text>"
```

- `--add-dir="<abs path>"` — required; without it agy operates on an empty scratch directory, not your repo.
- `--print="<prompt>"` (alias `--prompt=`) — runs one non-interactive prompt and prints the response. Do not use bare `--print "<prompt>"` (space-separated) — it is silently misparsed.
- Never pass `--dangerously-skip-permissions` from this skill (that's what keeps every mode read-only).
- `--effort=<low|medium|high>` — optional, leave unset unless the user asks for a specific level.
- `--model=<name>` — optional; run `agy models` to list choices. Leave unset by default (agy's own default is fine).
- `--continue` (bare flag, no `=`) — resume the most recent `agy` conversation, for follow-ups.
- `--conversation="<id>"` — resume a specific conversation by ID.

## Read-only guarantee

Without `--dangerously-skip-permissions`, any tool call agy makes that needs a permission (write, delete, execute) is **auto-denied** in headless/print mode — agy reports it explicitly (e.g. `a tool required the "write_file" permission ... auto-denied`) rather than silently succeeding or hanging. This is the actual safety boundary for this skill, not `--mode`: `--mode=plan` vs `--mode=accept-edits` makes no difference to what's allowed in `--print` mode. Leave `--mode` unset.

## Privacy — do not forward PII or secrets

The prompt text and any embedded diff/plan content is sent to a third-party service. Before embedding a diff, plan, or file content into a prompt, skim it for secrets (API keys, tokens, credentials) or personal data (emails, names tied to sensitive records, customer data) unrelated to the code itself, and strip or redact anything that isn't needed for the review. If the diff/plan is clean of that, proceed normally — don't over-redact code itself.

## Filesystem boundary

Prefix every prompt sent to `agy` with:

> IMPORTANT: Do not read or reference any files under `.claude/`, `~/.claude/`, or `skills/` — those are Claude Code skill definitions for a different AI system and are irrelevant to this review. Stay focused on the repository's actual source code.

## Step 2: Detect mode

Parse the user's input:

1. "agy review" / "review this diff with agy" (+ optional focus) → **Review mode** (Step 3A)
2. "agy challenge" / "challenge this with agy" (+ optional focus) → **Challenge mode** (Step 3B)
3. No clear review/challenge intent, or an explicit question → **Consult mode** (Step 3C), the rest of the text is the question/topic
4. Bare "agy" / "second opinion" with no other text:
   - Check for a diff: `git diff origin/<base>...HEAD --stat 2>/dev/null | tail -1` (detect base branch the same way as any git-aware skill: default branch via `git symbolic-ref refs/remotes/origin/HEAD` or fall back to `main`/`master`).
   - If a diff exists, ask via AskUserQuestion: "Review the diff (Recommended)" vs "Challenge the diff" vs "Something else — I'll ask a question".
   - If no diff, ask what to consult agy about.

## Step 3A: Review mode

```bash
_REPO_ROOT=$(git rev-parse --show-toplevel) || { echo "Not a git repo"; exit 1; }
_BASE="<detected base branch>"
_DIFF=$(cd "$_REPO_ROOT" && (git diff "origin/$_BASE...HEAD" 2>/dev/null || git diff "$_BASE...HEAD" 2>/dev/null))
agy --add-dir="$_REPO_ROOT" --print="IMPORTANT: Do not read or reference any files under .claude/, ~/.claude/, or skills/ — those are Claude Code skill definitions for a different AI system and are irrelevant to this review. Stay focused on the repository's actual source code.

Review the diff below against the base branch $_BASE. Flag findings as [P1] (critical — bugs, security, data loss) or [P2] (advisory — style, minor). Be direct and specific, cite file:line. No compliments, just problems (or say clearly if you found none).

DIFF_START
$_DIFF
DIFF_END" 2>&1
```

Determine gate: any `[P1]` in the output → **FAIL**; otherwise → **PASS**.

Present:
```
AGY SAYS (code review):
════════════════════════════════════════════════════════════
<full agy output, verbatim — do not truncate or summarize>
════════════════════════════════════════════════════════════
GATE: PASS|FAIL (N critical findings)
```

Then one recommendation line naming the most actionable finding (or confirming ship-as-is), e.g.:
`Recommendation: Fix the unvalidated redirect at auth.ts:88 first because it's the only P1; the two P2s are cosmetic.`

If Claude's own `/review` or `/code-review` already ran in this conversation, add a short cross-model comparison: what both found, what only agy found, what only Claude found.

## Step 3B: Challenge mode

Same diff-gathering as 3A, but the prompt instead reads:

> ...Your job is to find ways this code will fail in production. Think like an attacker and a chaos engineer: edge cases, race conditions, security holes, resource leaks, silent data corruption. Be adversarial and thorough. No compliments, just problems.

Append the user's focus area (e.g. "security", "concurrency") to the prompt if they gave one. Present the same way as 3A (no gate line — challenge mode has no pass/fail), followed by a recommendation line naming the most exploitable finding.

## Step 3C: Consult mode

For a question, a plan review, or anything else:

- If the topic is a plan file, **read it yourself and embed its full content** in the prompt — agy is scoped to `--add-dir` and won't know to go looking for a path outside the repo (e.g. `~/.claude/plans/`) that you tell it about; embedding avoids wasted tool calls.
- If the user said "continue"/"follow up"/"keep going" on a prior agy consult in this session, add bare `--continue` to resume it. Otherwise omit it (fresh conversation).

```bash
agy --add-dir="$_REPO_ROOT" --continue --print="<boundary prefix>

<user's question, or the embedded plan + review ask>" 2>&1
```

Present:
```
AGY SAYS (consult):
════════════════════════════════════════════════════════════
<full output, verbatim>
════════════════════════════════════════════════════════════
```

If Claude's own understanding disagrees with agy's answer, say so explicitly: "Note: Claude disagrees on X because Y." Close with one recommendation line naming the most actionable point from agy's answer and what to do with it.

## Error handling

- **Binary missing**: handled in Step 0.
- **Auto-denied write attempt**: agy's own stderr/stdout already explains this (`... auto-denied`). Surface it as-is; it means agy tried to do something outside this skill's read-only scope — not a bug.
- **Empty output / timeout**: agy's default print timeout is 5 minutes (`--print-timeout`); if the Bash call times out, tell the user the prompt may be too large and suggest narrowing scope (e.g. a smaller diff or a shorter question).

## Important rules

- Never pass `--dangerously-skip-permissions`. This skill only reads and reports.
- Present agy's output verbatim inside the `AGY SAYS` block — no truncation, no paraphrasing before it.
- Add Claude's synthesis/recommendation *after* the verbatim block, never instead of it.
- Never call `opencode-bridge` or any write-capable delegate from this skill — if the user wants agy (or anything else) to make edits, say so and point them elsewhere; that's out of scope here.
