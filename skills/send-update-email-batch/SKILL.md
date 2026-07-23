---
name: send-update-email-batch
description: Scan a parent folder of repos and send each configured repo's accumulated update email via Resend — unattended, no confirmation, meant for /loop.
triggers:
  - send update email batch
  - loop send update emails
  - batch email changelog
  - send updates for all repos
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - ToolSearch
---

# Bridge: Send Update Email (Batch)

**Announce at start:** "I'm using the bridge:send-update-email-batch skill to send accumulated update emails across this folder's repos."

## Purpose

Runs unattended across a parent folder of repos (e.g. scheduled via `/loop`), sending each configured repo's version-grouped, bullet-point update email via its own dedicated Resend MCP connection. This skill shares its core per-repo logic (commit gathering, content filtering, grouping, the email template, the send/state-update mechanics) with `/bridge:send-update-email` — the only real difference is this one never asks for confirmation before sending, since there's no one to ask when it's running unattended, and it processes every repo in the folder instead of just the current one. **When editing the core per-repo logic here, make the same edit in `skills/send-update-email/SKILL.md`** — the two are meant to stay behaviorally identical apart from the confirmation gate and the parent-folder loop.

For interactive, single-repo sending with a confirmation step, use `/bridge:send-update-email` instead.

## Requirements

- **A dedicated Resend MCP connection per repo**, registered by `/bridge:setup-email-updates`. Each repo's `.bridge/email-config.json` names its own connection via `mcpServerName`. A repo whose connection isn't registered on this machine is skipped (see Step 3's Error Handling below) — this skill never registers connections itself.

## Step 1 — Require Parent-Folder Context

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

- Errors (not a git repo) → this is a parent folder: continue to Step 2.
- Prints `true` → this is a single repo, not a parent folder. Stop and tell the user to use `/bridge:send-update-email` instead — that skill also shows the content for confirmation before sending, which this one deliberately does not do.

## Step 2 — Scan Parent Folder

```bash
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    echo "$dir"
  fi
done
```

This lists immediate subdirectories that are git work trees (a bare repo prints `false` here but still exits `0`, so checking the printed value — not just the exit code — is required to exclude it correctly).

## Step 3 — Process Each Repo

For each repo name printed in Step 2, `cd` into it and run the following per-repo sequence. A single repo's failure at any point (pull, missing config, no MCP connection, send error, state-persist failure) must not stop processing of the remaining repos — record the outcome (see Step 4) and move on to the next directory. Never invoke `/bridge:setup-email-updates` on a repo's behalf.

1. **Pull latest.**
   ```bash
   git pull
   ```
   Fails → record `Failed: <repo> — git pull failed`, continue to the next repo.

2. **Read config.**
   ```bash
   test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
   ```
   `NO_CONFIG` → record `Skipped (no config): <repo>`, continue silently — do not prompt, do not invoke `/bridge:setup-email-updates`. Otherwise extract:
   ```bash
   RECIPIENTS=$(jq -c '.recipients' .bridge/email-config.json)
   LAST_SHA=$(jq -r '.lastSentSha' .bridge/email-config.json)
   MCP_SERVER_NAME=$(jq -r '.mcpServerName' .bridge/email-config.json)
   SENDER_NAME=$(jq -r '.senderName // empty' .bridge/email-config.json)
   ```
   `SENDER_NAME` can be empty for a config predating this field — if so, skip the sender-name sign-off line in step 6 (just the "Bridge 自動通知" line).

3. **Check for new commits.**
   ```bash
   git log "$LAST_SHA"..HEAD --oneline
   ```
   Empty → record `Skipped (no new commits): <repo>`, continue.

4. **Gather commit detail and filter (via context-mode sandbox).** A busy range's per-commit `git show --stat` output (and the per-commit `package.json` version walk) can be large, and none of those raw lines need to survive into the conversation. Do this whole gather-and-mechanically-filter pass with `ctx_execute` (language: `"shell"`) instead of raw `Bash`:
   ```bash
   git log "$LAST_SHA"..HEAD --reverse --format='%H' | while read -r sha; do
     subject=$(git show -s --format='%s' "$sha")
     body=$(git show -s --format='%b' "$sha")
     files=$(git show --stat --format='' "$sha" | sed '$d' | awk '{print $1}' | grep -v '^$')
     ver=$(git show "$sha:package.json" 2>/dev/null | jq -r '.version // empty')
     jq -n --arg sha "$sha" --arg subject "$subject" --arg body "$body" \
           --argjson files "$(printf '%s\n' "$files" | jq -R . | jq -s .)" \
           --arg ver "$ver" \
           '{sha:$sha, subject:$subject, body:$body, files:$files, version:$ver}'
   done | jq -s '{
     commits: [.[] | select(.files != [".bridge/email-config.json"])],
     versions: [.[].version | select(. != "")]
   }'
   ```
   This mechanically drops commits whose changed files are *only* `.bridge/email-config.json` (this skill's own bookkeeping) and collects the ordered version sequence — only the resulting `{commits, versions}` JSON enters the conversation, never the raw diffstat/version-walk output.

   Reading each surviving commit's `subject`/`body`/`files` from that JSON, apply judgment to also discard commits that are purely deployment/infrastructure/CI changes with no user-facing effect, or routine documentation/informational edits (wording tweaks, typos, comment-only changes, changelog housekeeping) — **except** a genuinely significant documentation update (a new architecture/design doc, a substantial rewrite of a core doc), which still gets included as its own bullet or block. If every commit in range ends up excluded (mechanically or by judgment), treat it exactly like "no new commits" (step 3 above): record `Skipped (no new commits): <repo>`, continue — do not advance `lastSentSha`.

   `versions` empty → no `package.json` in range, use the commit date range as the block boundary instead (see step 5).

5. **Group into feature/fix blocks and bullets — organized around what changed, never by version.** Version numbers never appear on block headings; they only show up once, in the opening paragraph (step 6).
   - **Level 1:** cluster commits by real-world topic ("AI Providers self-service key," "database health monitoring") regardless of which version(s) touched it — never title a block with a version number or range. Small unrelated fixes that don't cluster into a named theme go in a catch-all block titled `修正` (all bug fixes) or `其他` (genuine mix), instead of forcing an artificial theme name.
   - **Level 2:** commits sharing a root cause (judged from message + diff, no commit-convention requirement) collapse into a single bullet, written as natural prose (short mini-label + explanation in one flowing line) — most blocks should be a flat bullet list with no subsection labels. Only add `新增` / `已修正` / `已優化` (or a combined label like `新增 / 強化`) when a block genuinely mixes distinct categories and separating them reads more clearly than one flat list.
   - Calibration (the real tone/structure to match — every content line is a bullet; bullets are never optional):
     ```
     自助申請個人 LLM API Key
     • 到側欄「AI Providers」→「LiteLLM 自助金鑰」按「申請新的 key」，即可拿到個人 API key，直接使用公司中央 LLM。
     • key 只顯示一次，請立即複製保存；同頁可列出、撤銷自己的 key。

     資料庫健康監控強化
     新增 / 強化
     • 每個專案獨立的刷新按鈕：資料庫健康頁每張卡片可單獨刷新該專案，不必整頁重抓。

     修正
     • 戰績儀表板篩選：切換時間範圍時，人員／專案的篩選不再殘留舊選擇而把新範圍的資料藏起來。
     ```

6. **Render the email.** Subject: `<repo 名稱> 已更新到 <最新版本號>` (or a range, e.g. `<repo 名稱> 更新 v2.9.5–v2.9.9`, if this batch spans multiple versions). Body opens with a greeting, then one to two natural sentences mentioning the version(s) once — compactly, not as a rigid leading slot — and headlining whatever is most worth knowing. Do not mechanically write "本封合併 N 版更新，含 vX ~ vY" every time. Match these real openings (version placement varies naturally):
   ```
   FlightPath 發布了 v3.4.6。這批更新的主角是「AI Providers」頁全面升級——每個人都能自助申請自己的 LLM API key。
   FlightPath 這次更新針對管理員後台的「資料庫健康」頁做了幾項強化（v3.3.1–v3.3.2）。
   FlightPath 發布了 v3.3.0，本封整理自上次公告（v3.2.0）之後的更新。
   FlightPath 發布了 v2.9.5–v2.9.9 一系列穩定性更新，重點如下：
   ```
   Then the release-time line, then the feature/fix blocks from step 5, each just their bare topic heading followed by bullets — no version anywhere in a block:
   ```
   發布時間: <HEAD commit 的 committer 時間，轉換為 Asia/Taipei UTC+8> (Asia/Taipei, UTC+8)

   <功能/主題區塊 1 標題>
   • xxx

   —
   查看完整 commit 記錄: <git remote get-url origin 的輸出，轉成瀏覽器可開啟的 URL>
   — <SENDER_NAME>
   — Bridge 自動通知
   ```
   Get the values needed:
   ```bash
   git log -1 --format=%cI HEAD
   git remote get-url origin
   ```
   Wrap in a light HTML shell (bold larger text for block headings; bold small labels for any subsections actually used; `<ul><li>` bullets; generous line-height; system font stack; `max-width: 600px; margin: 0 auto;`). Produce a matching plain-text version for the `text` field. No colored card/box background. Optional: a `🔗 <url>` line after the release-time line if you already know this repo's deployed URL from elsewhere — never guess one.

   The sign-off has two lines: `SENDER_NAME` (skip this line entirely if empty — see step 2), then the automated-tool line with "Bridge" linked to this plugin's own GitHub repo (`https://github.com/darkstar1227/bridge`), styled to blend into surrounding text:
   ```html
   — <SENDER_NAME 值><br>
   — <a href="https://github.com/darkstar1227/bridge" style="color: inherit; text-decoration: none;">Bridge</a> 自動通知
   ```
   Plain-text version spells out the URL instead:
   ```
   — <SENDER_NAME 值>
   — Bridge (https://github.com/darkstar1227/bridge) 自動通知
   ```

   There is no `from` to build — the repo's `resend-<repo-slug>` MCP server already has a fixed `SENDER_EMAIL_ADDRESS`.

7. **Send immediately — no confirmation.** Locate the tool on this repo's connection:
   ```
   ToolSearch query: "<MCP_SERVER_NAME> send email"
   ```
   Not found → record `Failed: <repo> — resend-<repo-slug> MCP connection not registered`, continue to the next repo.

   Otherwise call the resolved tool with `to` (recipients), `subject`, `html`, `text` — no `from` argument. A successful send returns the sent email's id with no error; anything else (an `error` field, a thrown tool error) → record `Failed: <repo> — <error>`, do not update state, continue to the next repo.

8. **Update state on success.**
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
   Commit/push fails after a successful send → record `Sent (state not persisted — re-check next run): <repo>` and surface this prominently in the final summary; this is the one case where the email and the repo's tracked state can disagree, so don't bury it.

   Otherwise record `Sent: <repo>`.

## Step 4 — Print Summary

After every subdirectory from Step 2 has been processed, print:

```
Sent: <repo>, <repo>, ...
Skipped (no config): <repo>, ...
Skipped (no new commits): <repo>, ...
Failed: <repo> — <reason>, ...
```

## Error Handling Reference

| Situation | Handling |
|---|---|
| Not run from a parent folder (cwd is itself a git repo) | Stop, tell the user to use `/bridge:send-update-email` instead. |
| A repo's `git pull` fails | Record as failed, continue to the next repo. |
| A repo has no `.bridge/email-config.json` | Skip silently — never prompt, never auto-invoke `/bridge:setup-email-updates`. |
| A repo has no new (or only excluded) commits since `lastSentSha` | Skip — no email, state unchanged. |
| A repo's `resend-<repo-slug>` MCP tool not found | Record as failed, continue. |
| Resend MCP tool call returns an error for a repo | Do not update that repo's state. Record as failed, continue. |
| A repo's state commit/push fails after a successful send | Record prominently — email sent but state not persisted, may re-send next run. |
