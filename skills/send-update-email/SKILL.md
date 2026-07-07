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

## Step 5 — Gather Commit Detail

```bash
git log "$LAST_SHA"..HEAD --reverse --format='%H%n%s%n%b%n---COMMIT-END---'
```

Read the message and body of every commit in the range, oldest first. Then check whether `package.json` exists and, if so, walk every commit individually to get the ordered sequence of version values (a single `git diff` across the whole range only shows the start and end value, not the intermediate ones):

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
