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
  - ToolSearch
---

# Bridge: Send Update Email

**Announce at start:** "I'm using the bridge:send-update-email skill to send an update email for accumulated changes."

## Purpose

Sends colleagues a readable, bullet-point update email summarizing everything that changed in a repo since the last successful send, grouped by version and by root cause rather than listed commit-by-commit. Delivered via the Resend MCP server (not a raw API key + `curl`).

## Requirements

- **A dedicated Resend MCP connection for this repo.** This skill never holds a Resend API key or a sender address itself — both live inside a per-repo MCP server (named `resend-<repo-slug>`) that `/bridge:setup-email-updates` registers once, with a fixed `SENDER_EMAIL_ADDRESS` for that repo. `.bridge/email-config.json`'s `mcpServerName` field (read in Step 3) names the exact connection to use. If it's missing on the current machine, that's a setup problem, not something this skill can fix — see Step 3 and Step 7.

At the start of Step 7 (not before — no need to check this until you're actually about to send), locate the tool on the connection named by `mcpServerName`:

```
ToolSearch query: "<mcpServerName> send email"
```

If nothing matches: in single-repo mode, stop and tell the user that the `<mcpServerName>` MCP connection isn't registered on this machine, and that re-running `/bridge:setup-email-updates` will register it. In batch mode, log the error and skip sending for the current run (see Step 9) — never send silently without this check.

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
MCP_SERVER_NAME=$(jq -r '.mcpServerName' .bridge/email-config.json)
```

## Step 4 — Check for New Commits

```bash
git log "$LAST_SHA"..HEAD --oneline
```

If this prints nothing: no new commits since the last send. Skip this repo — no email, `lastSentSha` unchanged. In batch mode, record this as a "skipped: no new commits" entry (see Step 9) and continue.

**Important:** this raw count can include commits that only touch `.bridge/email-config.json` — this skill's and `setup-email-updates`'s own bookkeeping (e.g. the `chore: init bridge email config` commit made when the repo was first set up). Those never count as real content. If, after Step 5's gathering and Step 6's grouping, every commit in range turns out to be bookkeeping-only and there is nothing left to report, treat it exactly like this step's "no new commits" case: skip, no email, `lastSentSha` unchanged (do not advance it — the next run will re-check from the same point once a real content commit lands).

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

There is no `from` to build here — the repo's dedicated `resend-<repo-slug>` MCP server (registered by `/bridge:setup-email-updates`) already has a fixed `SENDER_EMAIL_ADDRESS` for this repo, so the tool sends under that sender automatically. The repo's identity still comes through clearly in the subject line and email body above.

Locate the tool on this repo's own connection (see "Requirements" above):

```
ToolSearch query: "<MCP_SERVER_NAME> send email"
```

If nothing matches: stop and report the missing `<MCP_SERVER_NAME>` MCP connection (single-repo mode) or log it and skip sending for this repo (batch mode) — see the "Requirements" section above and Step 9.

Call the resolved tool directly with:
- `to`: the `recipients` array from Step 3
- `subject`: the subject line built above
- `html`: the rendered HTML body
- `text`: the rendered plain-text body

Do not pass a `from` argument — the connection's fixed sender applies automatically, and the tool's own schema will refuse or ignore an override attempt depending on how the server was configured. Do not build a raw HTTP payload or call `curl` — the MCP tool call *is* the send. Check its result: a successful send returns the sent email's id with no error. Anything else (an `error` field, a thrown tool error, etc.) means failure: do not update state, do not commit (Step 8). Report the error to the user (single-repo mode) or record it for the batch summary (Step 9), including the repo name.

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
| No new commits since `lastSentSha` (including ranges that are bookkeeping-only, see Step 4) | Skip — no email, state unchanged. |
| This repo's `resend-<repo-slug>` MCP tool not found | Single mode: stop, tell the user to re-run `/bridge:setup-email-updates` to register it on this machine. Batch mode: log error, skip sending. |
| Resend MCP tool call returns an error | Do not update state, do not commit. Report error (with repo name). |
| `package.json` absent | Use commit-date-range block titles; keep root-cause bullet merging. |
| State commit/push fails after a successful send | Warn user explicitly: email sent, state not persisted. |
