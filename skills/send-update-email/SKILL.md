---
name: send-update-email
description: Send a readable, version-grouped update email via Resend for a single repo's accumulated commits since the last send — shows the rendered content and waits for confirmation before actually sending.
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

Sends colleagues a readable, bullet-point update email summarizing everything that changed in this repo since the last successful send, grouped by version and by root cause rather than listed commit-by-commit. Delivered via the Resend MCP server. Always shows you the rendered subject/recipients/body and waits for explicit confirmation before sending anything.

This skill only works inside a single repo. For unattended sending across a parent folder of repos (e.g. scheduled via `/loop`), use `/bridge:send-update-email-batch` instead — it shares this skill's core logic (Steps 2-7, 9, 10 below) but skips the confirmation step, since there's no one to ask when it's running unattended. **When editing the core logic here (commit gathering, content filtering, grouping, the email template, or the send/state-update mechanics), make the same edit in `skills/send-update-email-batch/SKILL.md`** — the two are meant to stay behaviorally identical apart from the confirmation gate and the parent-folder loop.

## Requirements

- **A dedicated Resend MCP connection for this repo.** This skill never holds a Resend API key or a sender address itself — both live inside a per-repo MCP server (named `resend-<repo-slug>`) that `/bridge:setup-email-updates` registers once, with a fixed `SENDER_EMAIL_ADDRESS` for that repo. `.bridge/email-config.json`'s `mcpServerName` field (read in Step 3) names the exact connection to use. If it's missing on the current machine, that's a setup problem, not something this skill can fix — see Step 3 and Step 9.

At the start of Step 9 (not before — no need to check this until you're actually about to send), locate the tool on the connection named by `mcpServerName`:

```
ToolSearch query: "<mcpServerName> send email"
```

If nothing matches: stop and tell the user that the `<mcpServerName>` MCP connection isn't registered on this machine, and that re-running `/bridge:setup-email-updates` will register it.

## Step 1 — Require Single-Repo Context

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

- Prints `true` → continue to Step 2.
- Errors (not a git repo): stop. This skill only works `cd`'d into a single repo — tell the user to run it from inside the target repo, or to use `/bridge:send-update-email-batch` if they want to process a whole parent folder of repos.

## Step 2 — Pull Latest

```bash
git pull
```

If this fails (conflict, network error, non-zero exit): stop, tell the user the pull failed and why. Do not proceed to Step 3.

## Step 3 — Read Config

```bash
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
```

- `NO_CONFIG`: stop, tell the user to run `/bridge:setup-email-updates` first. Do not create the file yourself — that is not this skill's job.
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

If this prints nothing: no new commits since the last send. Stop — no email, `lastSentSha` unchanged.

**Important:** this raw count can include commits that only touch `.bridge/email-config.json` — this skill's and `setup-email-updates`'s own bookkeeping (e.g. the `chore: init bridge email config` commit made when the repo was first set up) — as well as routine deployment/infra/doc commits that Step 5 also discards (see below). Neither ever counts as real content. If, after Step 5's gathering and Step 6's grouping, every commit in range turns out to be excluded and there is nothing left to report, treat it exactly like this step's "no new commits" case: stop, no email, `lastSentSha` unchanged (do not advance it — the next run will re-check from the same point once a real content commit lands).

## Step 5 — Gather Commit Detail

```bash
git log "$LAST_SHA"..HEAD --reverse --format='%H%n%s%n%b%n---COMMIT-END---'
```

Read the message and body of every commit in the range, oldest first, and check which files each one touched:

```bash
git show --stat <commit-sha>
```

Discard any commit whose changed files are *only* `.bridge/email-config.json` — that is this skill's own bookkeeping, never user-facing content, and must never be turned into a bullet (see Step 4's note above for what to do if this empties the whole range).

**The email is themed around features — routine housekeeping doesn't belong in it.** Also discard commits that are purely:
- deployment/infrastructure/CI changes with no user-facing effect (deploy scripts, pipeline config, environment/env-var wiring, build tooling)
- routine informational or documentation edits unrelated to functionality (wording tweaks, typo fixes, comment-only changes, changelog housekeeping)

**Exception:** a genuinely significant documentation update — e.g. a new architecture/design doc, or a substantial rewrite of an existing core doc (a README overhaul, a major spec revision) — is still worth telling colleagues about even though it isn't a code feature. Include it as its own bullet (or its own version block, if nothing else in the range shares its theme) rather than silently dropping it. Use judgment on "significant": a one-line doc fix is routine and excluded; a doc a reader would actually want to know exists is included.

Then check whether `package.json` exists and, if so, walk every commit individually to get the ordered sequence of version values (a single `git diff` across the whole range only shows the start and end value, not the intermediate ones):

```bash
for sha in $(git log "$LAST_SHA"..HEAD --reverse --format='%H'); do
  git show "$sha:package.json" 2>/dev/null | jq -r '.version // empty'
done
```

If this prints nothing at all (no `package.json` in any commit in range), skip version extraction entirely — this repo uses the no-`package.json` fallback described in Step 6.

## Step 6 — Group Into Feature/Fix Blocks and Bullets

The email is organized entirely around what changed — features and fixes are the structure. Version numbers never appear on block headings; they only show up once, woven naturally into the opening paragraph in Step 7. Two levels of merging apply, in this order:

**Level 1 — cluster commits by real-world topic, not by version.** Read every commit surviving Step 5's filter and group them by the thing a person would actually call it — "AI Providers self-service key," "database health monitoring," "subdomain-change reliability" — regardless of which version(s) touched it or whether those versions were consecutive. Title each block with that short, concrete, natural-language name. Never put a version number, "v3.1.2", or any version-range in a block heading — that information belongs only in the opening paragraph (Step 7).

Small, unrelated fixes that don't cluster into any single named feature/topic can be grouped into a catch-all block instead of forcing them into an artificial theme — title it `修正` if everything in it is a bug fix, or `其他` if it's a genuine mix. This matches real usage: a batch of unrelated small fixes doesn't need a manufactured feature name.

If there is no `package.json`: this rule doesn't change — cluster by topic exactly the same way, using commit content and dates only to help you read the timeline, never as part of any heading.

**Level 2 — write bullets in natural prose; use 新增/已修正/已優化 labels only when they add clarity, not by default.** Within a block, commits sharing a root cause (judged from message + diff, no commit-convention requirement) become a single bullet describing the user/system-visible effect. Real examples mostly skip subsection labels entirely — write the bullet as a short mini-label plus explanation, in one flowing line (e.g. `每個專案獨立的刷新按鈕：資料庫健康頁每張卡片可單獨刷新該專案，不必整頁重抓。`), the same way a person would describe it in chat. Only add `新增` / `已修正` / `已優化` subsection labels (or a combined one like `新增 / 強化`) when a single block genuinely mixes distinct categories of change and separating them reads more clearly than one flat list — never add empty subsections, and never force labels on a block that's naturally one flat list.

**Calibration — study these real examples before writing bullets** (this is the actual tone/structure to match, not a template to fill in mechanically):

```
自助申請個人 LLM API Key
到側欄「AI Providers」→「LiteLLM 自助金鑰」按「申請新的 key」，即可拿到個人 API key，直接使用公司中央 LLM（相容 OpenAI／Anthropic API，Claude、GPT、Gemini 等多種模型）。
key 只顯示一次，請立即複製保存；同頁可列出、撤銷自己的 key。
每把 key：rpm 120、tpm 300k、90 天到期（到期回同頁再申請）。

資料庫健康監控強化
新增 / 強化
每個專案獨立的刷新按鈕：資料庫健康頁每張卡片可單獨刷新該專案，不必整頁重抓。
點進單一資料庫看詳情：新增專案詳情頁，顯示目前健康狀態，以及記憶體／磁碟的歷史趨勢圖（近 7 天，系統會定時自動存檔）。

修正
戰績儀表板篩選：切換時間範圍時，人員／專案的篩選不再殘留舊選擇而把新範圍的資料藏起來。
「失敗卻顯示成功」修正：AI 服務設定的儲存、以及管理後台的離職等操作，失敗時會正確顯示錯誤，不再誤報成功。

其他
平台資料庫結構已納入版本控制，日後除錯與稽核更透明。
系統通知文字已支援多語系架構（目前顯示繁體中文，未來可依個人語言顯示）。
```

## Step 7 — Render Email

Subject: `<repo 名稱> 已更新到 <最新版本號>` — if this batch spans multiple versions, use the range instead, e.g. `<repo 名稱> 更新 v2.9.5–v2.9.9`.

Body opens with a greeting, then **one to two natural sentences** that mention the version(s) once — compactly, not as a rigid leading slot — and headline whatever is actually most worth knowing about this release. Do not mechanically write "本封合併 N 版更新，含 vX ~ vY" every time; that's exactly the version-first framing this template is moving away from. Match the tone and structure of these real examples (each is a complete, valid opening — notice the version placement varies naturally sentence to sentence):

```
FlightPath 發布了 v3.4.6。這批更新的主角是「AI Providers」頁全面升級——每個人都能自助申請自己的 LLM API key。

FlightPath 這次更新針對管理員後台的「資料庫健康」頁做了幾項強化（v3.3.1–v3.3.2）。

FlightPath 發布了 v3.3.0，本封整理自上次公告（v3.2.0）之後的更新。

FlightPath 發布了 v3.0.0，兩個頁面有大更新：

FlightPath 發布了 v2.9.5–v2.9.9 一系列穩定性更新，重點如下：
```

Pick whichever pattern fits what actually happened: a single standout feature gets "這批更新的主角是..."; a focused set of related changes gets "這次更新針對...做了幾項強化"; a routine accumulation gets "整理自上次公告之後的更新" or "重點如下" with no single headline claimed.

After the opening, add the release time line, then the feature/fix blocks from Step 6, each just their bare topic heading followed directly by bullets (no version anywhere in the block):

```
發布時間: <HEAD commit 的 committer 時間，轉換為 Asia/Taipei UTC+8> (Asia/Taipei, UTC+8)

<功能/主題區塊 1 標題>
• xxx
• xxx

<功能/主題區塊 2 標題>
新增 / 強化
• xxx
已修正
• xxx

修正
• xxx
```

Get the HEAD commit time and repo remote URL for the template:

```bash
git log -1 --format=%cI HEAD
git remote get-url origin
```

Wrap that structure in a light HTML shell (bold, larger text for block headings; bold small labels for any subsections you did use; standard `<ul><li>` bullet lists; generous `line-height`; `font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`; `max-width: 600px; margin: 0 auto;` wrapper). Produce a plain-text version with the same structure (no HTML tags) for the `text` field. Do not use a colored card/box background — this is a plain, document-style layout.

**Optional live-URL line:** if you know this repo's deployed/production URL (not something this skill currently reads from config — only include it if the user has told you the URL some other way), add a `🔗 <url>` line directly after the release-time line. Otherwise omit it entirely; don't guess a URL.

In the sign-off line, make "Bridge" a hyperlink to this plugin's own GitHub repo (`https://github.com/darkstar1227/bridge`) — not the repo being reported on. Style it to blend into the surrounding text rather than looking like a typical blue underlined link:

```html
<a href="https://github.com/darkstar1227/bridge" style="color: inherit; text-decoration: none;">Bridge</a> 自動通知
```

In the plain-text version, links can't be styled or hidden inline, so spell out the URL instead: `— Bridge (https://github.com/darkstar1227/bridge) 自動通知`.

There is no `from` to build here — the repo's dedicated `resend-<repo-slug>` MCP server (registered by `/bridge:setup-email-updates`) already has a fixed `SENDER_EMAIL_ADDRESS` for this repo, so the tool sends under that sender automatically. The repo's identity still comes through clearly in the subject line and email body above.

## Step 8 — Confirm With User Before Sending

Before calling any send tool, show the user exactly what's about to go out:
- The subject line
- The recipient list (`RECIPIENTS` from Step 3)
- The rendered plain-text body from Step 7 (easiest to read in chat — mention that an equivalent HTML version will also be sent, but don't dump raw HTML into the conversation)

Ask directly: does this look right to send? If the user wants changes — wording, a bullet added/removed/reworded, a different grouping — revise the content and show it again. Repeat until they approve or explicitly cancel.

If they cancel: stop. No email, `lastSentSha` unchanged, nothing else touched.

Do not proceed to Step 9 without an explicit approval.

## Step 9 — Send via Resend

Locate the tool on this repo's own connection (see "Requirements" above):

```
ToolSearch query: "<MCP_SERVER_NAME> send email"
```

If nothing matches: stop and report the missing `<MCP_SERVER_NAME>` MCP connection — see the "Requirements" section above.

Call the resolved tool directly with:
- `to`: the `recipients` array from Step 3
- `subject`: the subject line from Step 7
- `html`: the rendered HTML body from Step 7
- `text`: the rendered plain-text body from Step 7 (the one the user approved in Step 8)

Do not pass a `from` argument — the connection's fixed sender applies automatically, and the tool's own schema will refuse or ignore an override attempt depending on how the server was configured. Do not build a raw HTTP payload or call `curl` — the MCP tool call *is* the send. Check its result: a successful send returns the sent email's id with no error. Anything else (an `error` field, a thrown tool error, etc.) means failure: do not update state, do not commit (Step 10). Report the error to the user.

## Step 10 — Update State on Success

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

## Error Handling Reference

| Situation | Handling |
|---|---|
| `git pull` fails | Stop — no email, no state change. |
| `.bridge/email-config.json` missing | Stop, tell the user to run `/bridge:setup-email-updates`. |
| No new commits since `lastSentSha` (including ranges that are bookkeeping/routine-only, see Step 4) | Stop — no email, state unchanged. |
| This repo's `resend-<repo-slug>` MCP tool not found | Stop, tell the user to re-run `/bridge:setup-email-updates` to register it on this machine. |
| User declines to send at the Step 8 confirmation | Stop — no email, state unchanged. |
| Resend MCP tool call returns an error | Do not update state, do not commit. Report the error to the user. |
| `package.json` absent | Use commit-date-range block titles; keep root-cause bullet merging. |
| State commit/push fails after a successful send | Warn the user explicitly: email sent, state not persisted. |
