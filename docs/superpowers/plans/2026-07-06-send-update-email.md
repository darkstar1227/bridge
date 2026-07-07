# Send Update Email Implementation Plan

> **⚠️ Superseded mechanism notice:** Tasks 1-8 below were executed as written and both skills shipped exactly as described here, using `RESEND_API_KEY` + raw `curl` against `https://api.resend.com/emails`. After implementation, the send mechanism in `skills/send-update-email/SKILL.md` was changed to call the Resend MCP server (`claude mcp add --transport http resend https://mcp.resend.com`) instead — no more API key, no more `curl`. That later change is **not** reflected in Task 5's or Task 9's text below (curl invocation, `RESEND_API_KEY` exports, etc.) — those sections are kept as an accurate historical record of how the feature was originally built and verified. **`skills/send-update-email/SKILL.md` is the current source of truth**; if you're resuming or re-planning this work, read that file, not the curl-based steps here.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two skills to the `bridge` plugin — `/bridge:setup-email-updates` (configure recipients per repo) and `/bridge:send-update-email` (send a version-grouped, bullet-point changelog email via Resend for everything committed since the last send) — usable on a single repo or in batch across a parent folder of repos.

**Architecture:** Both are pure skills — Markdown files that instruct Claude to run `git`/`jq`/`curl` at execution time. There is no application code and no `package.json` for this plugin itself (per this repo's "no build step, no runtime" convention), so there is no unit-test framework to drive in the usual red/green sense. Instead, every task's "test" is a concrete scratch-repo scenario: real `git`/`jq`/`curl` commands are run against a disposable fixture repo to prove the exact commands that will appear in the SKILL.md behave as described, before they're written into the file. Where behavior is semantic/judgment-based (grouping commits by root cause, writing a one-line theme), the task calls that out explicitly and substitutes a documented manual dry-run for an automated assertion — consistent with the spec's own Verification Plan, which states there is no automated test suite for this feature.

**Tech Stack:** Bash, git, `jq`, `curl`, Resend HTTP API (`POST https://api.resend.com/emails`, confirmed against current Resend docs: `Authorization: Bearer <key>` header, JSON body with `from`/`to`/`subject`/`html`/`text`).

## Global Constraints

- Pure skill implementation only — no new script files, no `package.json`, no runtime for the `bridge` plugin itself (`CLAUDE.md`).
- Frontmatter/skill conventions must match the existing `skills/gstack-to-plan/SKILL.md` pattern: `name`, `description`, `triggers`, `allowed-tools`.
- `.bridge/email-config.json` lives inside each *target* repo (not the `bridge` plugin repo) and is committed to git — schema is exactly `{ "recipients": [...], "lastSentSha": "...", "lastSentAt": "..." | null }`.
- Secrets (`RESEND_API_KEY`, `BRIDGE_EMAIL_FROM`) are environment variables only — never written to any JSON file.
- `send-update-email` never creates or edits `.bridge/email-config.json` — that is exclusively `setup-email-updates`'s job. `setup-email-updates` never edits `lastSentSha`.
- Mode detection for both skills: cwd is a git repo → single-repo mode; cwd is not a git repo (a parent folder) → batch mode, scanning immediate subdirectories only (not recursive).
- Batch/`/loop` mode must never prompt interactively and must never auto-invoke `/bridge:setup-email-updates` on a repo's behalf — unconfigured repos are silently skipped.
- Email content is Traditional Chinese, structured by version block (not cross-version feature category), matching the user-approved reference template. Timezone is fixed to `Asia/Taipei (UTC+8)`, not configurable.
- Resend request format: `curl -X POST 'https://api.resend.com/emails' -H "Authorization: Bearer $RESEND_API_KEY" -H 'Content-Type: application/json' -d @payload.json`, where `payload.json` has `from`, `to` (array), `subject`, `html`, `text`.
- Bump `.claude-plugin/plugin.json` version (semver) once both skills are complete, per `CLAUDE.md`.

---

## File Structure

```
skills/
  setup-email-updates/
    SKILL.md          — NEW: create/edit .bridge/email-config.json (single repo + batch)
  send-update-email/
    SKILL.md           — NEW: read config, gather commits, group, render, send, update state (single repo + batch)
.claude-plugin/
  plugin.json          — MODIFY: version bump
README.md              — MODIFY: document the two new skills
```

No other files change. Each SKILL.md is self-contained; there is no shared helper file because these are prompt documents, not importable code — the "DRY" concern here is about the two files not re-deriving different grouping/template logic, which the design addresses by keeping the send logic in exactly one file (`send-update-email/SKILL.md`) regardless of single/batch mode.

---

## Task 1: `setup-email-updates` — single-repo mode (create + edit)

**Files:**
- Create: `skills/setup-email-updates/SKILL.md`

**Interfaces:**
- Produces: the `.bridge/email-config.json` schema `{ "recipients": string[], "lastSentSha": string, "lastSentAt": string | null }` that Task 3 (`send-update-email`) reads.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Build a scratch fixture repo to validate the create-flow commands**

```bash
rm -rf /tmp/bridge-test-remote /tmp/bridge-test-repo
git init --bare /tmp/bridge-test-remote
git clone /tmp/bridge-test-remote /tmp/bridge-test-repo
cd /tmp/bridge-test-repo
git commit --allow-empty -m "initial commit"
git push origin main 2>&1 | tail -3 || git push origin master 2>&1 | tail -3
```

Expected: clone succeeds, one commit exists, push succeeds (branch name depends on local git default — either is fine, just note which one you get for the next step).

- [ ] **Step 2: Validate the "no config yet" detection command**

```bash
cd /tmp/bridge-test-repo
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
```

Expected output: `NO_CONFIG`

- [ ] **Step 3: Validate the create-config command**

```bash
cd /tmp/bridge-test-repo
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)
jq -n --argjson recipients '["alice@example.com","bob@example.com"]' --arg sha "$HEAD_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
cat .bridge/email-config.json
```

Expected: valid JSON printed with `recipients` equal to the two test addresses, `lastSentSha` equal to the current HEAD commit hash, `lastSentAt` equal to `null`.

- [ ] **Step 4: Validate the create-flow commit/push**

```bash
cd /tmp/bridge-test-repo
git add .bridge/email-config.json
git commit -m "chore: init bridge email config"
git push
git log --oneline -1
```

Expected: commit succeeds, push succeeds, `git log --oneline -1` shows the `chore: init bridge email config` commit.

- [ ] **Step 5: Validate the "existing config" detection and edit commands**

```bash
cd /tmp/bridge-test-repo
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
jq --argjson recipients '["alice@example.com","carol@example.com"]' \
  '.recipients = $recipients' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
cat .bridge/email-config.json
```

Expected: the first command prints the JSON from Step 3 (not `NO_CONFIG`); after the edit, `recipients` is now `["alice@example.com","carol@example.com"]` and `lastSentSha`/`lastSentAt` are **unchanged** from Step 3.

- [ ] **Step 6: Write `skills/setup-email-updates/SKILL.md` (single-repo mode content)**

```markdown
---
name: setup-email-updates
description: Create or edit the .bridge/email-config.json that send-update-email needs — recipients and last-sent tracking — for a single repo or in bulk across a parent folder.
triggers:
  - setup email updates
  - configure update email recipients
  - init bridge email config
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Bridge: Setup Email Updates

**Announce at start:** "I'm using the bridge:setup-email-updates skill to configure who receives update emails for this repo."

## Purpose

`send-update-email` refuses to run against a repo that has no `.bridge/email-config.json`. This skill is the only thing that creates or edits that file — recipients and the `lastSentSha` tracking marker.

## Step 1 — Detect Mode

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

- Prints `true` → **single-repo mode**: go to Step 2.
- Errors (not a git repo) → **batch mode**: go to Step 5.

## Step 2 — Single-repo: Check Existing Config

```bash
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
```

- Prints `NO_CONFIG` → go to Step 3 (create).
- Prints JSON → go to Step 4 (edit).

## Step 3 — Single-repo: Create Config

Ask the user for the recipient email addresses (they can list as many as they want). Then run:

```bash
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)
jq -n --argjson recipients '["alice@example.com", "bob@example.com"]' --arg sha "$HEAD_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
```

Replace the `--argjson recipients` value with the actual addresses the user gave you, as a JSON array literal (e.g. `'["alice@example.com","carol@example.com"]'`). Leave `lastSentAt` as `null` — `send-update-email` fills it in after the first real send.

Then commit and push:

```bash
git add .bridge/email-config.json
git commit -m "chore: init bridge email config"
git push
```

## Step 4 — Single-repo: Edit Existing Config

Show the user the `recipients` array from the `cat` output in Step 2. Ask whether to add, remove, or replace any addresses. Rewrite only `recipients` — `lastSentSha` and `lastSentAt` must be preserved exactly as they were, so a re-run of this skill can never cause a duplicate send or a gap:

```bash
jq --argjson recipients '["alice@example.com", "carol@example.com"]' \
  '.recipients = $recipients' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
```

Replace the `--argjson recipients` value with the user's final list. Then commit and push:

```bash
git add .bridge/email-config.json
git commit -m "chore: update bridge email config recipients"
git push
```
```

- [ ] **Step 7: Confirm the file was written correctly**

```bash
test -f /Users/ds-anxing/GitHub/bridge/skills/setup-email-updates/SKILL.md && echo "EXISTS"
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/setup-email-updates/SKILL.md
```

Expected: `EXISTS`, then `4` (Steps 1-4 present; Step 5/Notes come in Task 2).

- [ ] **Step 8: Clean up the scratch fixture and commit**

```bash
rm -rf /tmp/bridge-test-remote /tmp/bridge-test-repo
cd /Users/ds-anxing/GitHub/bridge
git add skills/setup-email-updates/SKILL.md
git commit -m "feat: add setup-email-updates skill (single-repo mode)"
```

---

## Task 2: `setup-email-updates` — batch mode + notes

**Files:**
- Modify: `skills/setup-email-updates/SKILL.md` (append after Step 4)

**Interfaces:**
- Consumes: Steps 1-4 from Task 1 (single-repo create/edit flow), reused per-directory.
- Produces: nothing new consumed elsewhere — this is the batch entry point for the same skill.

- [ ] **Step 1: Build a scratch parent folder with three test repos**

```bash
rm -rf /tmp/bridge-batch-test
mkdir -p /tmp/bridge-batch-test
cd /tmp/bridge-batch-test

for name in repo-a repo-b; do
  git init --bare "$name-remote.git" -q
  git clone "$name-remote.git" "$name" -q
  (cd "$name" && git commit --allow-empty -m "initial" -q && git push -q 2>&1 | tail -1)
done

mkdir plain-folder
echo "not a repo" > plain-folder/readme.txt
```

Expected: `repo-a` and `repo-b` are git repos with one commit each; `plain-folder` is a plain directory (not a git repo); the `-remote.git` bare repos exist as subdirectories too and must be excluded by the scan (see Step 2 — a naive exit-code check is not enough, since a bare repo still exits `0`).

- [ ] **Step 2: Validate the parent-folder scan command**

```bash
cd /tmp/bridge-batch-test
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    echo "$dir"
  fi
done
```

Expected output: exactly `repo-a` and `repo-b`, each on its own line — `plain-folder` and the two `*-remote.git` bare repos must NOT appear.

**Why not just check the exit code:** `git -C <bare-repo> rev-parse --is-inside-work-tree` prints `false` but still **exits `0`** — a bare repo is a valid git repository, just not a work tree. A check that only tests `$? -eq 0` (e.g. `if git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then`) incorrectly treats bare repos as work trees. Verify this yourself before moving on:

```bash
cd /tmp/bridge-batch-test
git -C repo-a-remote.git rev-parse --is-inside-work-tree; echo "exit:$?"
```

Expected: prints `false` then `exit:0` — confirming the exit code alone can't distinguish a bare repo from a work tree; the printed value must be checked.

- [ ] **Step 3: Append batch mode and notes to `skills/setup-email-updates/SKILL.md`**

Append this after the existing "Step 4 — Single-repo: Edit Existing Config" section:

```markdown

## Step 5 — Batch: Scan Parent Folder

```bash
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    echo "$dir"
  fi
done
```

For each repo name printed, `cd` into it and run Steps 2-4 for that repo only, one repo at a time — ask the user about recipients for repo #1, finish it (including commit+push), then move to repo #2. Do not front-load every question before touching any repo.

## Notes

- This skill never sets `lastSentSha` to anything other than the current `HEAD` at creation time — it never touches `lastSentSha` on an edit.
- This skill is interactive by design. Do not schedule it under `/loop`; that's `send-update-email`'s job.
```

- [ ] **Step 4: Confirm the appended section is present**

```bash
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/setup-email-updates/SKILL.md
grep -c '^## Notes' /Users/ds-anxing/GitHub/bridge/skills/setup-email-updates/SKILL.md
```

Expected: `5`, then `1`.

- [ ] **Step 5: Clean up the scratch fixture and commit**

```bash
rm -rf /tmp/bridge-batch-test
cd /Users/ds-anxing/GitHub/bridge
git add skills/setup-email-updates/SKILL.md
git commit -m "feat: add batch mode to setup-email-updates skill"
```

---

## Task 3: `send-update-email` — mode detect, pull, config read, new-commit check

**Files:**
- Create: `skills/send-update-email/SKILL.md`

**Interfaces:**
- Consumes: the `.bridge/email-config.json` schema produced by Task 1 (`recipients`, `lastSentSha`, `lastSentAt`).
- Produces: the `RECIPIENTS` and `LAST_SHA` shell variables that Task 4 (grouping) and Task 5 (send) use; the mode-detection convention (`git rev-parse --is-inside-work-tree`) that Task 7 (batch mode) branches on.

- [ ] **Step 1: Build a scratch fixture repo with an existing config and a pending commit**

```bash
rm -rf /tmp/bridge-send-test-remote /tmp/bridge-send-test
git init --bare /tmp/bridge-send-test-remote -q
git clone /tmp/bridge-send-test-remote /tmp/bridge-send-test -q
cd /tmp/bridge-send-test
git commit --allow-empty -m "initial commit" -q
git push -q 2>&1 | tail -1
FIRST_SHA=$(git rev-parse HEAD)

mkdir -p .bridge
jq -n --argjson recipients '["me@example.com"]' --arg sha "$FIRST_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
git add .bridge/email-config.json
git commit -m "chore: init bridge email config" -q
git push -q 2>&1 | tail -1

echo '{"version": "1.0.0"}' > package.json
git add package.json
git commit -m "feat: add package.json at 1.0.0" -q
git push -q 2>&1 | tail -1
```

Expected: repo has 3 commits total; `.bridge/email-config.json`'s `lastSentSha` points at the *first* commit, one commit behind HEAD.

- [ ] **Step 2: Validate the mode-detection command**

```bash
cd /tmp/bridge-send-test
git rev-parse --is-inside-work-tree 2>/dev/null
cd /tmp
git rev-parse --is-inside-work-tree 2>/dev/null; echo "exit: $?"
```

Expected: first command prints `true`; second command prints nothing and `exit: 128` (not a git repo — `/tmp` itself isn't one on a typical machine; if it errors as non-zero that confirms the "errors" branch used for batch-mode detection).

- [ ] **Step 3: Validate the pull command on a repo with a configured remote**

```bash
cd /tmp/bridge-send-test
git pull
echo "exit: $?"
```

Expected: `Already up to date.` (or equivalent), `exit: 0`.

- [ ] **Step 4: Validate the config-read commands**

```bash
cd /tmp/bridge-send-test
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
RECIPIENTS=$(jq -c '.recipients' .bridge/email-config.json)
LAST_SHA=$(jq -r '.lastSentSha' .bridge/email-config.json)
echo "RECIPIENTS=$RECIPIENTS"
echo "LAST_SHA=$LAST_SHA"
```

Expected: JSON printed (not `NO_CONFIG`); `RECIPIENTS=["me@example.com"]`; `LAST_SHA=<the first commit's hash>`.

- [ ] **Step 5: Validate the new-commit-check command, both for "has commits" and "no commits" cases**

```bash
cd /tmp/bridge-send-test
git log "$LAST_SHA"..HEAD --oneline
```

Expected: two lines — the `chore: init bridge email config` commit and the `feat: add package.json at 1.0.0` commit (both created after `$LAST_SHA`).

```bash
cd /tmp/bridge-send-test
HEAD_SHA=$(git rev-parse HEAD)
git log "$HEAD_SHA"..HEAD --oneline
echo "exit: $?"
```

Expected: no output, `exit: 0` — this is the "no new commits, skip" case.

- [ ] **Step 6: Write `skills/send-update-email/SKILL.md` (Steps 1-4 content)**

```markdown
---
name: send-update-email
description: Send a readable, version-grouped update email via Resend for accumulated commits since the last send, for a single repo or in batch across a parent folder.
triggers:
  - send update email
  - email changelog
  - notify team of updates
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Bridge: Send Update Email

**Announce at start:** "I'm using the bridge:send-update-email skill to send an update email for accumulated changes."

## Purpose

Sends colleagues a readable, bullet-point update email summarizing everything that changed in a repo since the last successful send, grouped by version and by root cause rather than listed commit-by-commit. Delivered via the Resend API.

## Required Environment Variables

- `RESEND_API_KEY` — Resend API key.
- `BRIDGE_EMAIL_FROM` — sender address in `"Display Name <email@domain>"` format; the domain must be verified in Resend.

If either is unset: in single-repo mode, stop and tell the user exactly which variable is missing and that it must be exported before this skill can send mail. In batch mode, log the error and skip sending for the current run (see Step 9) — never send silently without checking these first.

## Step 1 — Detect Mode

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

- Prints `true` → **single-repo mode**: go to Step 2, then stop after Step 8.
- Errors (not a git repo) → **batch mode**: skip straight to Step 9.

## Step 2 — Pull Latest

```bash
git pull
```

If this fails (conflict, network error, non-zero exit): stop, tell the user the pull failed and why. Do not proceed to Step 3. In batch mode this only skips the current repo — see Step 9.

## Step 3 — Read Config

```bash
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
```

- `NO_CONFIG` in single-repo mode: stop, tell the user to run `/bridge:setup-email-updates` first. Do not create the file yourself — that is not this skill's job.
- `NO_CONFIG` in batch mode: skip this repo silently (see Step 9), continue to the next.
- Otherwise, extract the fields you need:

```bash
RECIPIENTS=$(jq -c '.recipients' .bridge/email-config.json)
LAST_SHA=$(jq -r '.lastSentSha' .bridge/email-config.json)
```

## Step 4 — Check for New Commits

```bash
git log "$LAST_SHA"..HEAD --oneline
```

If this prints nothing: no new commits since the last send. Skip this repo — no email, `lastSentSha` unchanged. In batch mode, record this as a "skipped: no new commits" entry (see Step 9) and continue.

**Important:** this raw count can include commits that only touch `.bridge/email-config.json` — this skill's and `setup-email-updates`'s own bookkeeping (e.g. the `chore: init bridge email config` commit made when the repo was first set up). Those never count as real content. If, after Step 5's gathering and Step 6's grouping, every commit in range turns out to be bookkeeping-only and there is nothing left to report, treat it exactly like this step's "no new commits" case: skip, no email, `lastSentSha` unchanged (do not advance it — the next run will re-check from the same point once a real content commit lands).
```

*(Note added after Task 7's fixture testing surfaced this — see that task's Step 3/4 below. Written here directly so this file matches what actually ships in Steps 4-5 rather than leaving the plan out of sync with its own deliverable.)*

- [ ] **Step 7: Confirm the file was written correctly**

```bash
test -f /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md && echo "EXISTS"
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md
```

Expected: `EXISTS`, then `4`.

- [ ] **Step 8: Clean up the scratch fixture and commit**

```bash
rm -rf /tmp/bridge-send-test-remote /tmp/bridge-send-test
cd /Users/ds-anxing/GitHub/bridge
git add skills/send-update-email/SKILL.md
git commit -m "feat: add send-update-email skill (mode detect, pull, config read, commit check)"
```

---

## Task 4: `send-update-email` — commit gathering + two-level grouping logic

**Files:**
- Modify: `skills/send-update-email/SKILL.md` (append after Step 4)

**Interfaces:**
- Consumes: `LAST_SHA` from Task 3's Step 3.
- Produces: the version-block/bullet structure (block heading + 新增/已修正/已優化 subsections) that Task 5's template consumes.

This task's core behavior (judging "same theme" and "same root cause" from commit messages/diffs) is semantic, not mechanical — there is no assertion that can prove a grouping is "correct." The verification here is therefore a documented manual dry run: build a realistic scratch history, then manually apply the two-level grouping rule exactly as written and confirm the result matches the intended shape (this mirrors the design spec's own reference example). The *mechanical* extraction commands (log range, diff parsing) are still verified with real command output.

- [ ] **Step 1: Build a scratch repo with a realistic multi-version commit history**

```bash
rm -rf /tmp/bridge-group-test-remote /tmp/bridge-group-test
git init --bare /tmp/bridge-group-test-remote -q
git clone /tmp/bridge-group-test-remote /tmp/bridge-group-test -q
cd /tmp/bridge-group-test

echo '{"name": "flightpath", "version": "3.1.0"}' > package.json
git add package.json && git commit -q -m "chore: bootstrap at 3.1.0"
git push -q 2>&1 | tail -1
BASE_SHA=$(git rev-parse HEAD)

echo '{"name": "flightpath", "version": "3.1.1"}' > package.json
git add package.json && git commit -q -m "fix: revoke old keys more thoroughly on offboarding"

echo '{"name": "flightpath", "version": "3.1.2"}' > package.json
git add package.json && git commit -q -m "fix: prevent silent success on AI key save failure"

echo '{"name": "flightpath", "version": "3.2.0"}' > package.json
git add package.json && git commit -q -m "feat: allow project owner self-service handoff"
git push -q 2>&1 | tail -1
```

Expected: 4 commits total; `package.json` version goes `3.1.0 → 3.1.1 → 3.1.2 → 3.2.0`; the two `fix:` commits both relate to credential/security handling, the `feat:` commit is an unrelated new feature.

- [ ] **Step 2: Validate the commit-gathering command**

```bash
cd /tmp/bridge-group-test
git log "$BASE_SHA"..HEAD --reverse --format='%H%n%s%n%b%n---COMMIT-END---'
```

Expected: three commit blocks printed oldest-first, ending each with `---COMMIT-END---`, showing the two `fix:` subjects then the `feat:` subject.

- [ ] **Step 3: Validate the package.json version-diff command**

```bash
cd /tmp/bridge-group-test
git diff "$BASE_SHA"..HEAD -- package.json
```

Expected: a unified diff whose only content change is the `"version"` line, showing the final value `3.2.0` (a diff between two snapshots shows start vs. end, not every intermediate value — the ordered *intermediate* values `3.1.1` and `3.1.2` must instead be reconstructed by walking each commit individually, which Step 4 below covers).

- [ ] **Step 4: Validate walking every commit's package.json individually to get the full ordered version sequence**

```bash
cd /tmp/bridge-group-test
for sha in $(git log "$BASE_SHA"..HEAD --reverse --format='%H'); do
  git show "$sha:package.json" | jq -r '.version'
done
```

Expected output, in order: `3.1.1`, `3.1.2`, `3.2.0`.

- [ ] **Step 5: Manually apply the two-level grouping rule to this fixture and record the expected result**

Reading the three commits from Step 2 and the version sequence from Step 4:

- `3.1.1` and `3.1.2` are both `fix:` commits about credential/key handling on offboarding — same theme → **Level 1 merges them into one block**, titled with the latest version in that run: `v3.1.2 — 憑證與金鑰安全性修正`.
  - Both fixes are about ensuring failures are surfaced rather than silently succeeding / thoroughly revoking access → **Level 2 could still keep them as two bullets** if they describe genuinely different user-visible effects (revocation thoroughness vs. save-failure visibility), or one bullet if judged as the same root cause. Document whichever call you make and why — there is no single correct answer, only a defensible one.
- `3.2.0` is a `feat:` commit introducing an unrelated capability → **its own block**, titled `v3.2.0 — 專案負責人自助移交`.

This is the expected shape the rendered email (Task 5) must produce for this fixture. Keep this scratch repo around — Task 5 reuses it to validate the full render+send flow.

- [ ] **Step 6: Append the grouping logic to `skills/send-update-email/SKILL.md`**

Append this after the existing "Step 4 — Check for New Commits" section:

```markdown

## Step 5 — Gather Commit Detail

```bash
git log "$LAST_SHA"..HEAD --reverse --format='%H%n%s%n%b%n---COMMIT-END---'
```

Read the message and body of every commit in the range, oldest first, and check which files each one touched:

```bash
git show --stat <commit-sha>
```

Discard any commit whose changed files are *only* `.bridge/email-config.json` — that is this skill's own bookkeeping, never user-facing content, and must never be turned into a bullet (see Step 4's note above for what to do if this empties the whole range).

Then check whether `package.json` exists and, if so, walk every commit individually to get the ordered sequence of version values (a single `git diff` across the whole range only shows the start and end value, not the intermediate ones):

```bash
for sha in $(git log "$LAST_SHA"..HEAD --reverse --format='%H'); do
  git show "$sha:package.json" 2>/dev/null | jq -r '.version // empty'
done
```

If this prints nothing at all (no `package.json` in any commit in range), skip version extraction entirely — this repo uses the no-`package.json` fallback described in Step 6.

## Step 6 — Group Into Version Blocks and Bullets

Two levels of merging apply, in this order:

**Level 1 — consecutive small version bumps become one version block.** Walk the ordered version sequence from Step 5. When a run of consecutive versions is all fixes/optimizations for the same underlying theme, collapse that whole run into a single block. Label the block with the *last* version number in the run, plus a one-line theme you write yourself by reading the commits in that run (e.g. `v3.1.2 — 憑證與金鑰安全性修正`). A version that introduces an independent new feature — not a continuation of a fix/optimize run — gets its own block, titled after that feature (e.g. `v3.2.0 — 專案負責人自助移交`).

If there is no `package.json` (Step 5 fallback): use the commit date range as the block boundary instead of a version number, e.g. `2026-06-20 ~ 2026-07-06 — <theme>`.

**Level 2 — same-root-cause commits become one bullet.** Within a block, read each commit's message and diff and judge whether it shares a root cause / class of issue with any other commit in that block (no reliance on any commit message convention — pure semantic judgment). Commits sharing a root cause become a single bullet describing the user/system-visible effect, not a list of the individual commits. Sort each block's bullets under whichever of these subsections actually apply — omit a subsection entirely if this block has nothing for it, never show it empty:

- `新增` (Added / new feature)
- `已修正` (Fixed)
- `已優化` (Optimized)
```

- [ ] **Step 7: Confirm the appended sections are present**

```bash
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md
```

Expected: `6`.

- [ ] **Step 8: Commit (keep the scratch repo for Task 5)**

```bash
cd /Users/ds-anxing/GitHub/bridge
git add skills/send-update-email/SKILL.md
git commit -m "feat: add commit gathering and version-grouping logic to send-update-email"
```

---

## Task 5: `send-update-email` — email template rendering + Resend send

**Files:**
- Modify: `skills/send-update-email/SKILL.md` (append after Step 6)

**Interfaces:**
- Consumes: the version-block/bullet structure produced by Task 4; `RECIPIENTS` from Task 3.
- Produces: the HTTP status-code check (`200` vs. other) that Task 6 branches on for state update vs. failure handling.

- [ ] **Step 1: Reuse the `/tmp/bridge-group-test` fixture from Task 4 and gather the render inputs**

```bash
cd /tmp/bridge-group-test
git log -1 --format=%cI HEAD
git remote get-url origin
```

Expected: an ISO-8601 timestamp (e.g. `2026-07-06T14:13:00+08:00` or similar, depending on your local clock/timezone at commit time) and the file-path remote URL from Step 1 of Task 4 (e.g. `/tmp/bridge-group-test-remote`).

- [ ] **Step 2: Validate building the Resend JSON payload safely with `jq -n` (no manual string interpolation)**

```bash
cd /tmp/bridge-group-test
FROM_HEADER="Bridge Bot (flightpath) <noreply@example.com>"
RECIPIENTS='["me@example.com"]'
SUBJECT="flightpath 已更新到 v3.2.0"
HTML_BODY='<div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;line-height:1.6;"><p>大家好,</p><p><b>v3.1.2 — 憑證與金鑰安全性修正</b></p><p><b>已修正</b></p><ul><li>xxx</li></ul></div>'
TEXT_BODY=$'大家好,\n\nv3.1.2 — 憑證與金鑰安全性修正\n已修正\n- xxx\n'

jq -n \
  --arg from "$FROM_HEADER" \
  --argjson to "$RECIPIENTS" \
  --arg subject "$SUBJECT" \
  --arg html "$HTML_BODY" \
  --arg text "$TEXT_BODY" \
  '{from: $from, to: $to, subject: $subject, html: $html, text: $text}' \
  > /tmp/bridge-resend-payload.json

jq . /tmp/bridge-resend-payload.json
```

Expected: `jq .` prints back valid, correctly-escaped JSON (proves the payload is well-formed even with embedded quotes, Chinese characters, and newlines) with all five keys present and matching the inputs.

- [ ] **Step 3: Validate the curl invocation shape against a deliberately invalid key (confirms request format without needing a real account yet)**

```bash
curl -s -w '\n%{http_code}' -X POST 'https://api.resend.com/emails' \
  -H "Authorization: Bearer re_invalid_test_key" \
  -H 'Content-Type: application/json' \
  -d @/tmp/bridge-resend-payload.json
```

Expected: a JSON error body from Resend (e.g. an authentication error) followed by a non-`200` status code on the last line — this confirms the request reaches Resend and is parsed as a well-formed send attempt (rejected only for the invalid key), not rejected for malformed JSON or a wrong endpoint/header.

- [ ] **Step 4: Append the template + send logic to `skills/send-update-email/SKILL.md`**

Append this after the existing "Step 6 — Group Into Version Blocks and Bullets" section:

```markdown

## Step 7 — Render Email and Send via Resend

Build the subject and body in this structure (Traditional Chinese, matching the reference template):

```
主旨: <repo 名稱> 已更新到 <最新版本號>

大家好,

<repo 名稱> 發布了 <最新版本號>（本封合併 <N> 版更新，含 <最早版本號> ~ <最新版本號>）。

發布時間: <HEAD commit 的 committer 時間，轉換為 Asia/Taipei UTC+8> (Asia/Taipei, UTC+8)

<版本區塊 1 標題>
新增
• xxx
已修正
• xxx

<版本區塊 2 標題>
已修正
• xxx
已優化
• xxx

—
查看完整 commit 記錄: <git remote get-url origin 的輸出，轉成瀏覽器可開啟的 URL>
— Bridge 自動通知
```

Get the HEAD commit time and repo remote URL for the template:

```bash
git log -1 --format=%cI HEAD
git remote get-url origin
```

Wrap that structure in a light HTML shell (bold, larger text for version block headings; bold small labels for 新增/已修正/已優化; standard `<ul><li>` bullet lists; generous `line-height`; `font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`; `max-width: 600px; margin: 0 auto;` wrapper). Produce a plain-text version with the same structure (no HTML tags) for the `text` field. Do not use a colored card/box background — this is a plain, document-style layout.

Build the `from` header by inserting the repo name between the display name and the email address of `BRIDGE_EMAIL_FROM`. For example, if `BRIDGE_EMAIL_FROM="Bridge Bot <noreply@example.com>"` and the repo is named `FlightPath`, the `from` value is `"Bridge Bot (FlightPath) <noreply@example.com>"`.

Send it using `jq` to build the JSON payload safely (avoids shell-escaping bugs with HTML/Chinese content) and `curl` to POST it:

```bash
jq -n \
  --arg from "$FROM_HEADER" \
  --argjson to "$RECIPIENTS" \
  --arg subject "$SUBJECT" \
  --arg html "$HTML_BODY" \
  --arg text "$TEXT_BODY" \
  '{from: $from, to: $to, subject: $subject, html: $html, text: $text}' \
  > /tmp/bridge-resend-payload.json

curl -s -w '\n%{http_code}' -X POST 'https://api.resend.com/emails' \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H 'Content-Type: application/json' \
  -d @/tmp/bridge-resend-payload.json
```

Check the trailing HTTP status code that `-w '\n%{http_code}'` appends. `200` means success — go to Step 8. Anything else (4xx/5xx) means failure: do not update state, do not commit (Step 8). Report the error body and status code to the user (single-repo mode) or record it for the batch summary (Step 9), including the repo name.
```

- [ ] **Step 5: Confirm the appended section is present**

```bash
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md
```

Expected: `7`.

- [ ] **Step 6: Clean up scratch fixtures and commit**

```bash
rm -rf /tmp/bridge-group-test-remote /tmp/bridge-group-test /tmp/bridge-resend-payload.json
cd /Users/ds-anxing/GitHub/bridge
git add skills/send-update-email/SKILL.md
git commit -m "feat: add email template rendering and Resend send to send-update-email"
```

---

## Task 6: `send-update-email` — state update on success + partial-failure handling

**Files:**
- Modify: `skills/send-update-email/SKILL.md` (append after Step 7)

**Interfaces:**
- Consumes: the `200`-status success signal from Task 5's Step 7.
- Produces: the updated `.bridge/email-config.json` (`lastSentSha`, `lastSentAt`) that the next `send-update-email` run's Task 3 logic reads.

- [ ] **Step 1: Build a scratch fixture repo simulating a successful send that needs its state updated**

```bash
rm -rf /tmp/bridge-state-test-remote /tmp/bridge-state-test
git init --bare /tmp/bridge-state-test-remote -q
git clone /tmp/bridge-state-test-remote /tmp/bridge-state-test -q
cd /tmp/bridge-state-test
git commit --allow-empty -m "initial" -q
FIRST_SHA=$(git rev-parse HEAD)
mkdir -p .bridge
jq -n --argjson recipients '["me@example.com"]' --arg sha "$FIRST_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
git add .bridge/email-config.json && git commit -q -m "chore: init bridge email config"
git push -q 2>&1 | tail -1
git commit --allow-empty -m "feat: something shipped" -q
git push -q 2>&1 | tail -1
```

Expected: repo has 3 commits, `.bridge/email-config.json`'s `lastSentSha` is one commit behind HEAD.

- [ ] **Step 2: Validate the state-update-and-push command**

```bash
cd /tmp/bridge-state-test
HEAD_SHA=$(git rev-parse HEAD)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
jq --arg sha "$HEAD_SHA" --arg now "$NOW" \
  '.lastSentSha = $sha | .lastSentAt = $now' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json

git add .bridge/email-config.json
git commit -m "chore: update bridge email state"
git push

cat .bridge/email-config.json
git log --oneline -1
```

Expected: `.bridge/email-config.json` now shows `lastSentSha` equal to `$HEAD_SHA` and `lastSentAt` equal to `$NOW`; `git log --oneline -1` shows the `chore: update bridge email state` commit; push succeeds.

- [ ] **Step 3: Validate the partial-failure case (push fails after commit)**

```bash
cd /tmp/bridge-state-test
git remote set-url origin /tmp/bridge-state-test-remote-does-not-exist
git commit --allow-empty -m "another change" -q
HEAD_SHA=$(git rev-parse HEAD)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
jq --arg sha "$HEAD_SHA" --arg now "$NOW" \
  '.lastSentSha = $sha | .lastSentAt = $now' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
git add .bridge/email-config.json
git commit -m "chore: update bridge email state" -q
git push
echo "push exit: $?"
```

Expected: the commit succeeds locally, but `git push` fails (non-zero exit) because the remote path no longer exists — this is exactly the "email sent but state not persisted" scenario the SKILL.md must warn about explicitly.

- [ ] **Step 4: Append the state-update logic to `skills/send-update-email/SKILL.md`**

Append this after the existing "Step 7 — Render Email and Send via Resend" section:

```markdown

## Step 8 — Update State on Success

```bash
HEAD_SHA=$(git rev-parse HEAD)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
jq --arg sha "$HEAD_SHA" --arg now "$NOW" \
  '.lastSentSha = $sha | .lastSentAt = $now' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json

git add .bridge/email-config.json
git commit -m "chore: update bridge email state"
git push
```

If this `commit`/`push` fails after the email already sent successfully: explicitly warn the user that the email went out but the state file wasn't persisted, and that the next run may re-send this same commit range. Do not silently swallow this — it's the one case where the email and the repo's tracked state can disagree.
```

- [ ] **Step 5: Confirm the appended section is present**

```bash
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md
```

Expected: `8`.

- [ ] **Step 6: Clean up the scratch fixture and commit**

```bash
rm -rf /tmp/bridge-state-test-remote /tmp/bridge-state-test
cd /Users/ds-anxing/GitHub/bridge
git add skills/send-update-email/SKILL.md
git commit -m "feat: add state-update-on-success logic to send-update-email"
```

---

## Task 7: `send-update-email` — batch mode + summary + error-handling reference

**Files:**
- Modify: `skills/send-update-email/SKILL.md` (append after Step 8)

**Interfaces:**
- Consumes: Steps 1-8 (the full single-repo flow), run once per discovered subdirectory.
- Produces: nothing consumed by other tasks — this is the final section of the file.

- [ ] **Step 1: Build a scratch parent folder mixing configured, unconfigured, and no-new-commit repos**

```bash
rm -rf /tmp/bridge-batch-send-test
mkdir -p /tmp/bridge-batch-send-test
cd /tmp/bridge-batch-send-test

# repo-configured: has config, has a genuine new commit (real file change) since lastSentSha
git init --bare configured-remote.git -q
git clone configured-remote.git repo-configured -q
cd repo-configured
git commit --allow-empty -m "initial" -q
FIRST_SHA=$(git rev-parse HEAD)
mkdir -p .bridge
jq -n --argjson recipients '["me@example.com"]' --arg sha "$FIRST_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' > .bridge/email-config.json
git add .bridge/email-config.json && git commit -q -m "chore: init bridge email config"
echo "new feature code" > feature.txt
git add feature.txt && git commit -q -m "feat: new thing"
git push -q 2>&1 | tail -1
cd ..

# repo-no-config: valid git repo, no .bridge/email-config.json
git init --bare no-config-remote.git -q
git clone no-config-remote.git repo-no-config -q
cd repo-no-config
git commit --allow-empty -m "initial" -q
git push -q 2>&1 | tail -1
cd ..

# repo-up-to-date: has config, only its own bookkeeping commit since lastSentSha (no real changes)
git init --bare up-to-date-remote.git -q
git clone up-to-date-remote.git repo-up-to-date -q
cd repo-up-to-date
git commit --allow-empty -m "initial" -q
CURRENT_SHA=$(git rev-parse HEAD)
mkdir -p .bridge
jq -n --argjson recipients '["me@example.com"]' --arg sha "$CURRENT_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' > .bridge/email-config.json
git add .bridge/email-config.json && git commit -q -m "chore: init bridge email config"
git push -q 2>&1 | tail -1
cd ..

ls -d */
```

Expected: three subdirectories — `repo-configured`, `repo-no-config`, `repo-up-to-date` — plus the three `*-remote.git` bare repos. Note that `repo-up-to-date`'s config was written with `lastSentSha` captured *before* its own `chore: init bridge email config` commit landed — the same sequence `setup-email-updates` always follows — so its raw commit range is not actually empty; that's the point of this fixture (see Step 2).

- [ ] **Step 2: Validate the full scan + per-repo classification**

```bash
cd /tmp/bridge-batch-send-test
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    if [ -f "$dir/.bridge/email-config.json" ]; then
      LAST_SHA=$(jq -r '.lastSentSha' "$dir/.bridge/email-config.json")
      COUNT=$(git -C "$dir" log "$LAST_SHA"..HEAD --oneline -- . ':(exclude).bridge' | wc -l | tr -d ' ')
      if [ "$COUNT" -gt 0 ]; then
        echo "$dir: WOULD_SEND ($COUNT new commits)"
      else
        echo "$dir: SKIP (no new commits)"
      fi
    else
      echo "$dir: SKIP (no config)"
    fi
  fi
done
```

This mirrors the real skill's Step 4/5 bookkeeping-exclusion rule (the `-- . ':(exclude).bridge'` pathspec is a mechanical proxy for "discard commits that only touch `.bridge/email-config.json`" — Claude applies that same rule semantically when reading full commit diffs, per Step 5's note).

Expected output (order may vary):
```
repo-configured: WOULD_SEND (1 new commits)
repo-no-config: SKIP (no config)
repo-up-to-date: SKIP (no new commits)
```

**Why `repo-up-to-date` is not a trivial case:** its raw `git log "$LAST_SHA"..HEAD --oneline` (no pathspec) actually shows 1 commit — its own `chore: init bridge email config` — because `lastSentSha` was captured before that commit was made. Verify this yourself to see the distinction the exclusion rule is making:

```bash
cd /tmp/bridge-batch-send-test/repo-up-to-date
LAST_SHA=$(jq -r '.lastSentSha' .bridge/email-config.json)
git log "$LAST_SHA"..HEAD --oneline
```

Expected: prints the one `chore: init bridge email config` commit — confirming that without the exclusion rule, this repo would be wrongly classified as `WOULD_SEND`.

- [ ] **Step 3: Append batch mode, summary, and the error-handling reference to `skills/send-update-email/SKILL.md`**

Append this after the existing "Step 8 — Update State on Success" section:

```markdown

## Step 9 — Batch Mode

```bash
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    echo "$dir"
  fi
done
```

For each repo name printed, `cd` into it and run Steps 2-8 for that repo. Never invoke `/bridge:setup-email-updates` on a repo's behalf — a repo with no config is simply skipped (recorded as "skipped: no config"). A single repo's pull failure, send failure, or state-persist failure must not stop processing of the remaining repos — record the outcome and move to the next directory.

After every subdirectory has been processed, print a summary:

```
Sent: <repo>, <repo>, ...
Skipped (no config): <repo>, ...
Skipped (no new commits): <repo>, ...
Failed: <repo> — <reason>, ...
```

## Error Handling Reference

| Situation | Handling |
|---|---|
| `git pull` fails | Skip repo — no email, no state change. Batch mode continues to next repo. |
| `.bridge/email-config.json` missing | Single mode: stop, tell user to run `/bridge:setup-email-updates`. Batch mode: skip silently, never auto-invoke setup. |
| No new commits since `lastSentSha` | Skip — no email, state unchanged. |
| `RESEND_API_KEY` / `BRIDGE_EMAIL_FROM` unset | Single mode: stop, name the missing variable. Batch mode: log error, skip sending. |
| Resend API returns non-`200` | Do not update state, do not commit. Report error (with repo name). |
| `package.json` absent | Use commit-date-range block titles; keep root-cause bullet merging. |
| State commit/push fails after a successful send | Warn user explicitly: email sent, state not persisted. |
```

- [ ] **Step 4: Confirm the full file structure is complete**

```bash
grep -c '^## Step' /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md
grep -c '^## Error Handling Reference' /Users/ds-anxing/GitHub/bridge/skills/send-update-email/SKILL.md
```

Expected: `9`, then `1`.

- [ ] **Step 5: Clean up the scratch fixture and commit**

```bash
rm -rf /tmp/bridge-batch-send-test
cd /Users/ds-anxing/GitHub/bridge
git add skills/send-update-email/SKILL.md
git commit -m "feat: add batch mode and error-handling reference to send-update-email"
```

---

## Task 8: Plugin metadata — version bump + README update

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing — pure documentation/metadata task.
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Read the current plugin.json to confirm the version to bump**

```bash
cat /Users/ds-anxing/GitHub/bridge/.claude-plugin/plugin.json
```

Expected: `"version": "1.0.0"`.

- [ ] **Step 2: Bump the version to 1.1.0**

Change `.claude-plugin/plugin.json`:

```json
{
  "name": "bridge",
  "version": "1.1.0",
  "description": "Bridge gstack reviewed plans into Superpowers writing-plans format. Reads a gstack-approved plan, transforms it into a Superpowers-compatible implementation spec, then invokes superpowers:writing-plans.",
  "author": {
    "name": "ds-anxing"
  },
  "license": "MIT",
  "keywords": [
    "gstack",
    "superpowers",
    "planning",
    "bridge",
    "workflow"
  ]
}
```

- [ ] **Step 3: Verify the version bump**

```bash
jq -r '.version' /Users/ds-anxing/GitHub/bridge/.claude-plugin/plugin.json
```

Expected: `1.1.0`

- [ ] **Step 4: Add the two new skills to `README.md`**

Insert this after the existing `### \`/bridge:gstack-to-plan\`` section (before `## Requirements`):

```markdown
### `/bridge:setup-email-updates`

Creates or edits the `.bridge/email-config.json` a repo needs before `/bridge:send-update-email` will work — who gets notified. Works on a single repo, or in bulk when run from a parent folder containing multiple repos (asks one repo at a time). Interactive by design — not meant to run under `/loop`.

**Triggers:**
- `/bridge:setup-email-updates`
- "setup email updates"
- "configure update email recipients"
- "init bridge email config"

### `/bridge:send-update-email`

Sends a readable, bullet-point update email via [Resend](https://resend.com) summarizing everything a repo shipped since the last send — grouped by version and by root cause, not listed commit-by-commit. Works on a single repo (run manually near the end of a session) or in batch across a parent folder of repos (run on a schedule via `/loop`). Requires `RESEND_API_KEY` and `BRIDGE_EMAIL_FROM` environment variables, and a `.bridge/email-config.json` created via `/bridge:setup-email-updates`.

**Triggers:**
- `/bridge:send-update-email`
- "send update email"
- "email changelog"
- "notify team of updates"
```

- [ ] **Step 5: Verify the README changes render sensibly**

```bash
grep -c '^### `/bridge:' /Users/ds-anxing/GitHub/bridge/README.md
```

Expected: `3` (the existing `gstack-to-plan` section plus the two new ones).

- [ ] **Step 6: Commit**

```bash
cd /Users/ds-anxing/GitHub/bridge
git add .claude-plugin/plugin.json README.md
git commit -m "docs: document setup-email-updates and send-update-email, bump plugin to 1.1.0"
```

---

## Task 9: End-to-end manual verification with real Resend credentials

**Files:** none — this task changes no files, it exercises the finished skills as a human would.

**Interfaces:**
- Consumes: both finished skills from Tasks 1-7, the metadata from Task 8.
- Produces: nothing — this is the final sign-off gate before the branch is considered done.

This task requires a real `RESEND_API_KEY`, a `BRIDGE_EMAIL_FROM` address on a domain verified in Resend, and cannot be run by an autonomous agent without those secrets being made available to it. A human (or an agent that has been handed real credentials for this purpose) must run it directly — it cannot be faked with the scratch bare-repo fixtures used in Tasks 1-7, because the point is to confirm a real email is actually delivered.

- [ ] **Step 1: Export real credentials**

```bash
export RESEND_API_KEY="<your real Resend API key>"
export BRIDGE_EMAIL_FROM="Bridge Bot <your-verified-sender@yourdomain.com>"
```

- [ ] **Step 2: Single-repo flow — setup then send**

```bash
mkdir -p /tmp/bridge-e2e-test && cd /tmp/bridge-e2e-test
git init -q
git commit --allow-empty -m "initial" -q
echo '{"name": "e2e-test", "version": "0.1.0"}' > package.json
git add package.json && git commit -q -m "chore: bootstrap at 0.1.0"
```

In a Claude Code session with cwd `/tmp/bridge-e2e-test`, invoke `/bridge:setup-email-updates` and give your own email address as the sole recipient when asked. Confirm `.bridge/email-config.json` now exists with your email in `recipients` and `lastSentSha` equal to the current HEAD.

```bash
echo '{"name": "e2e-test", "version": "0.1.1"}' > package.json
git add package.json && git commit -q -m "fix: correct an off-by-one in the widget counter"
```

Invoke `/bridge:send-update-email` in the same directory. Confirm:
- an email arrives at your inbox with subject `e2e-test 已更新到 v0.1.1`, a `v0.1.1` block, and a `已修正` bullet describing the fix
- `.bridge/email-config.json`'s `lastSentSha` now equals the latest commit, and `lastSentAt` is set
- Invoking `/bridge:send-update-email` again immediately afterward results in "no new commits, skipping" with no second email sent

- [ ] **Step 3: Batch flow — parent folder with a mix of repos**

```bash
mkdir -p /tmp/bridge-e2e-batch/repo-x /tmp/bridge-e2e-batch/repo-y
cd /tmp/bridge-e2e-batch/repo-x && git init -q && git commit --allow-empty -m "initial" -q
cd /tmp/bridge-e2e-batch/repo-y && git init -q && git commit --allow-empty -m "initial" -q
```

In a Claude Code session with cwd `/tmp/bridge-e2e-batch`, invoke `/bridge:setup-email-updates` and configure only `repo-x` with your email when prompted, declining (or leaving unconfigured) `repo-y`.

```bash
cd /tmp/bridge-e2e-batch/repo-x
git commit --allow-empty -m "feat: something new in repo-x" -q
```

Invoke `/bridge:send-update-email` from `/tmp/bridge-e2e-batch`. Confirm:
- exactly one email arrives, for `repo-x`
- the end-of-run summary lists `repo-x` as sent and `repo-y` as skipped (no config)
- `repo-y` was never prompted or modified

- [ ] **Step 4: Clean up**

```bash
rm -rf /tmp/bridge-e2e-test /tmp/bridge-e2e-batch
```

No commit for this task — it produces no file changes, only a pass/fail sign-off that the finished skills behave correctly against a real Resend account.

---

## Self-Review

**1. Spec coverage:**
- Two skills, pure-skill implementation, no runtime → Tasks 1-7 (skill content), no code files added. ✓
- Mode auto-detection (single repo vs. parent folder) for both skills → Task 1/2 Step 1/5, Task 3 Step 1/2, Task 7 Step 1/2. ✓
- `git pull` before reading log/diff → Task 3 Step 2-3. ✓
- Config schema (`recipients`, `lastSentSha`, `lastSentAt`), committed to git → Task 1 Steps 3-4. ✓
- Secrets via env vars, never in config → Task 3's "Required Environment Variables" section (Step 6 of Task 3). ✓
- Two-level grouping (version-block merge + root-cause bullet merge) → Task 4. ✓
- Email template matching the reference (version-block structure, Traditional Chinese, plain document style, fixed Asia/Taipei timezone) → Task 5. ✓
- Resend send via `curl`, confirmed against current API docs → Task 5 Steps 3-4. ✓
- State update + commit/push on success, partial-failure warning → Task 6. ✓
- Batch mode, per-repo isolation of failures, end-of-run summary → Task 7. ✓
- `send-update-email` never auto-invokes setup in batch mode → Task 3 Step 6 (Step 3 of the SKILL.md content) and Task 7's Step 9 content. ✓
- Setup skill: single-repo create/edit, batch mode, never touches `lastSentSha` on edit → Tasks 1-2. ✓
- Plugin version bump + README → Task 8. ✓
- Manual verification plan from the spec → Task 9 (real-credential E2E) plus the scratch-repo checks embedded in every earlier task. ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"add error handling" phrasing appears; every step shows the literal commands or file content to write. The one spot that could look like a placeholder — the "either bullet is defensible" note in Task 4 Step 5 — is deliberate: it documents that this specific behavior is a judgment call by design (per the spec itself), not an unresolved gap, and gives the concrete reasoning either way so the implementer isn't guessing blind.

**3. Type/name consistency:** `RECIPIENTS` / `LAST_SHA` / `HEAD_SHA` / `NOW` variable names are used identically in Task 3, 4, 5, 6. The `.bridge/email-config.json` field names (`recipients`, `lastSentSha`, `lastSentAt`) are identical everywhere they appear (Tasks 1, 2, 3, 6). Skill file paths (`skills/send-update-email/SKILL.md`, `skills/setup-email-updates/SKILL.md`) match the plugin's existing `skills/<name>/SKILL.md` convention used by `gstack-to-plan`. Frontmatter fields (`name`, `description`, `triggers`, `allowed-tools`) match the existing skill's shape exactly.
