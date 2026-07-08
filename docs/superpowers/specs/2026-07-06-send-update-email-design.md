# Design: `/bridge:send-update-email` + `/bridge:send-update-email-batch` + `/bridge:setup-email-updates`

_Date: 2026-07-06_
_Status: Approved by user, pending final review before implementation planning_

> **Revised post-implementation (split into two send skills):** originally `send-update-email` auto-detected single-repo vs. parent-folder mode from `cwd` and ran the same flow either way. It's since been split at the user's request into `send-update-email` (single repo, interactive, shows the rendered email and waits for confirmation before sending) and `send-update-email-batch` (parent-folder scan, unattended, no confirmation, for `/loop`). The two skill files duplicate the shared per-repo logic (commit gathering/filtering/grouping/template/send/state-update) rather than one calling into the other, since Claude Code has no mechanism to invoke "a subset of another skill's steps" — `skills/send-update-email/SKILL.md` and `skills/send-update-email-batch/SKILL.md` both carry an explicit "keep these in sync" note for future edits. Those files are the source of truth; this doc is updated to match.

## Overview

Three new skills in the `bridge` plugin:

- `/bridge:send-update-email` — for a single repo (run manually, e.g. near the end of a session). Sends a readable, well-formatted update email once there are new commits since the last send, and shows the rendered content for confirmation before actually sending.
- `/bridge:send-update-email-batch` — the unattended counterpart, for a parent folder of repos (run on a schedule via `/loop`). Same per-repo logic as `send-update-email`, minus the confirmation gate, with per-repo failure isolation and an end-of-run summary.
- `/bridge:setup-email-updates` — the companion setup skill that creates/edits the `.bridge/email-config.json` (and registers the per-repo Resend MCP connection) that both send skills need, for one repo or in bulk across a parent folder.

Both send skills use the Resend MCP server (see "Sending Mechanism and Secrets" below) and track per-repo send state inside the repo itself (committed to git) so state travels with the repo across machines and clones. All three are pure skills (Markdown instructions for Claude to follow at execution time via Bash/Read/Write/ToolSearch) — consistent with this repo's "no build step, no runtime" convention. No new script files or package.json are introduced.

## Goals

- One command, usable two ways:
  - Manually, inside a single repo, near the end of a session
  - Via `/loop`, pointed at a parent folder containing multiple repos, to periodically send accumulated updates for each
- Always `git pull` before reading `git log`/`git diff`, so the email reflects the latest remote state
- Merge multiple version bumps / commits that represent the same underlying feature fix or optimization into a single explanation, rather than listing every commit
- Per-repo configurable recipient list
- High-readability HTML email template using bullet points
- A companion setup skill to create/edit that per-repo recipient config, for one repo or in bulk across a parent folder, without needing to hand-edit JSON

## Non-Goals

- Not building a general-purpose changelog generator for arbitrary CI pipelines
- Not adding any persistent runtime/server component — this is invoked interactively or via `/loop`, not a standing service
- Not handling non-git-based repos or non-npm ecosystems beyond graceful fallback (see Error Handling)
- Not supporting per-recipient personalized content — all recipients on a repo receive the same email body

## Architecture

Two skills, each requiring a specific context rather than auto-detecting:

- `skills/send-update-email/SKILL.md`, invoked as `/bridge:send-update-email` — requires `cwd` to be a single git repo; errors out (pointing to the batch skill) if `cwd` is a parent folder instead.
- `skills/send-update-email-batch/SKILL.md`, invoked as `/bridge:send-update-email-batch` — requires `cwd` to be a parent folder (not itself a git repo); errors out (pointing to the interactive skill) if `cwd` is a single repo instead. Scans immediate subdirectories; for each one that is a git repo AND has `.bridge/email-config.json`, runs the shared core workflow.

```
/bridge:send-update-email          — cwd must be a single repo → process it, confirm, send
/bridge:send-update-email-batch    — cwd must be a parent folder → scan subdirectories,
                                       run the same core workflow per repo, no confirmation
```

The two skill files intentionally duplicate the shared per-repo logic (Core Workflow below) rather than one dynamically invoking a subset of the other's steps — Claude Code's skill-invocation model runs a whole skill, not an arbitrary slice of one, so cross-referencing wasn't practical. Both files carry an explicit note to edit the other whenever the shared logic changes.

## Core Workflow (runs once per repo, shared by both send skills)

1. `git pull` to bring the repo to the latest remote state.
   - On failure: log the error, skip this repo (no email, no state change). In `send-update-email-batch`, continue to the next repo.
2. Read `.bridge/email-config.json` for `recipients`, `lastSentSha`, and `mcpServerName`.
   - If missing, in `send-update-email`: stop and tell the user to run `/bridge:setup-email-updates` first — this skill does not create config itself (that's the setup skill's job).
   - If missing, in `send-update-email-batch`: skip this subdirectory silently — no prompt, and never invoke `/bridge:setup-email-updates` on the repo's behalf. Batch/`/loop` runs are unattended; a repo only starts receiving emails once someone has explicitly run the setup skill on it.
3. Run `git log <lastSentSha>..HEAD` to get the accumulated commits.
   - If no new commits (or every commit in range is excluded by the content filter — see "Commit / Version Grouping Logic" below): skip — no email sent, `lastSentSha` unchanged.
4. For each remaining commit, read the commit message and diff, paying particular attention to `version` changes in `package.json`.
5. Apply the two-level grouping logic (see below) to build the email body.
6. Render the HTML (+ plain-text fallback) template.
7. **`send-update-email` only:** show the rendered subject, recipients, and plain-text body to the user and wait for explicit confirmation. If they want changes, revise and re-show; if they decline, stop — no email, state unchanged. `send-update-email-batch` skips this step entirely and proceeds straight from render to send, since it runs unattended.
8. Locate this repo's dedicated Resend MCP tool (via `mcpServerName`, see "Sending Mechanism and Secrets" below) and call it to send to `recipients`.
   - On error: do not update state, do not commit. Report the error (with repo name) to the user / to the batch-run summary.
9. On successful send: update `lastSentSha` to current HEAD and `lastSentAt` to now, then `git add`, `commit` (fixed message, e.g. `chore: update bridge email state`), and `push` `.bridge/email-config.json` back to the repo.
   - If this commit/push step fails after the email was already sent: explicitly warn the user that the email went out but the state wasn't persisted, so the next run may re-send the same range.

## Batch Run Summary (`send-update-email-batch` only)

After processing all subdirectories, print a summary: repos successfully emailed, repos skipped (with reason: no config / no new commits), repos that failed (with error message). A single repo's failure does not stop processing of the others.

## Config Schema

Location: `.bridge/email-config.json` inside each target repo, committed to git.

```json
{
  "recipients": [
    "alice@example.com",
    "bob@example.com"
  ],
  "lastSentSha": "a1b2c3d4e5f6...",
  "lastSentAt": "2026-07-01T09:00:00Z",
  "mcpServerName": "resend-flightpath",
  "senderName": "Justin Lee"
}
```

- `recipients`: flat array of email addresses; all are `to` recipients of one shared email (no per-recipient personalization, no BCC split).
- `lastSentSha`: HEAD commit at the time of the last successful send; the anchor for the next `git log` range.
- `lastSentAt`: informational only, for human debugging — not used in any logic branch.
- `mcpServerName`: the name of this repo's dedicated Resend MCP connection (see "Sending Mechanism and Secrets" below), set once at creation and never edited afterward — changing a repo's sender requires re-registering the connection, not editing this field directly.
- `senderName`: the human name shown in the email sign-off, alongside the "Bridge 自動通知" line. Asked at setup time, defaulting to `git config user.name` if set; editable later (unlike `mcpServerName`, this is a display-only value with no state-integrity concerns). Configs created before this field existed read back as empty — the sign-off falls back to just the "Bridge 自動通知" line in that case.

### Sending Mechanism and Secrets

> **Revised post-implementation (twice):** originally this section specified a `RESEND_API_KEY` environment variable + raw `curl` against `https://api.resend.com/emails`. That was built, tested, and shipped, then replaced at the user's request — first with a single shared Resend MCP connection (`BRIDGE_EMAIL_FROM` + generic `ToolSearch`), then again after inspecting `resend-mcp`'s actual tool schema on GitHub revealed that a shared connection can't express a per-repo sender display name (the tool's `from` parameter, when present, is typed as a bare email and its description explicitly instructs any calling agent to always ask a human for it — incompatible with unattended batch/`/loop` sends). The mechanism below — one dedicated MCP connection per repo — is what's actually shipped in `skills/setup-email-updates/SKILL.md` and `skills/send-update-email/SKILL.md`; those files are the source of truth.

- **One Resend MCP connection per repo**, named `resend-<repo-slug>` (slug derived from the repo's directory name). `/bridge:setup-email-updates` registers it once per repo, at first setup, via:
  ```bash
  claude mcp add resend-<repo-slug> -e RESEND_API_KEY=$RESEND_API_KEY -e SENDER_EMAIL_ADDRESS="<per-repo sender string>" -- npx -y resend-mcp
  ```
  Because `SENDER_EMAIL_ADDRESS` is passed straight through to the real Resend SDK call unvalidated, it can be a full `"Display Name <email@domain>"` string (e.g. `Bridge Bot (FlightPath) <noreply@example.com>`) even though the tool's own live `from` argument (used only when no `SENDER_EMAIL_ADDRESS` is configured) is restricted to a bare email address. Configuring the sender this way also removes `from` from the tool's input schema entirely, avoiding the tool's built-in "must ask a human" requirement — necessary for unattended batch/`/loop` sends.
- `.bridge/email-config.json` gains a `mcpServerName` field (e.g. `"resend-flightpath"`) recording which connection belongs to this repo. `send-update-email` reads it and locates that specific tool via `ToolSearch query: "<mcpServerName> send email"` — it never passes a `from` argument itself, and never holds `RESEND_API_KEY` (that only needs to exist in the environment at `setup-email-updates` time, to register the connection).
- Trade-off accepted: the per-repo MCP connection registration lives in the local Claude Code config, not in git — unlike `.bridge/email-config.json`, it does not travel with `git clone` and must be re-established (by re-running `/bridge:setup-email-updates`) on every machine that will run `send-update-email` for that repo, including any machine running `/loop`.

If this repo's `resend-<repo-slug>` connection isn't found: `send-update-email` stops and tells the user to re-run `/bridge:setup-email-updates`; `send-update-email-batch` logs the error for that run and skips sending for that repo (never silently drops it).

## Commit / Version Grouping Logic

> **Revised post-implementation:** the original version below put version numbers on block headings (`v3.1.5 — <theme>`). After the user shared six real reference emails, that turned out to be backwards — every real example clusters purely by feature/fix topic, with the version number appearing only once, in the opening paragraph, never on a block heading. `新增`/`已修正`/`已優化` subsection labels also turned out to be used inconsistently in practice (often skipped entirely, sometimes combined, sometimes `修正`/`其他` stand alone as a top-level block for unrelated small fixes). The rule below reflects what's actually shipped in `skills/send-update-email/SKILL.md` and `skills/send-update-email-batch/SKILL.md`.

Two levels of merging, followed by a content filter applied before either:

**Level 1 — cluster by real-world topic, never by version.**
Read every commit surviving the content filter (below) and group by what a person would actually call the change — "AI Providers self-service key," "database health monitoring" — regardless of which version(s) touched it or whether those versions were consecutive. Title each block with that short, concrete name. No version number, "vX.X.X", or version range ever appears in a block heading — that information belongs only in the opening paragraph. Small unrelated fixes that don't cluster into a named theme go in a catch-all block titled `修正` (all bug fixes) or `其他` (genuine mix) rather than forcing an artificial theme name.

**Level 2 — write bullets as natural prose; subsection labels are the exception, not the default.**
Within a block, commits sharing a root cause (judged from message + diff, no commit-convention requirement) collapse into a single bullet — a short mini-label plus explanation in one flowing line, the way a person would describe it in chat. Real examples mostly have zero subsection structure. Only add `新增` / `已修正` / `已優化` (or a combined label like `新增 / 強化`) when a block genuinely mixes distinct categories of change and separating them reads more clearly than a flat list.

If `package.json` does not exist (non-npm repo): the clustering rule is unchanged — cluster by topic, use commit dates only to help read the timeline, never in a heading.

**Content filter (applied before Level 1/2 grouping):** the email is themed around features, not housekeeping. Beyond discarding `.bridge/email-config.json`-only bookkeeping commits (see Config Schema / Sending Mechanism above), also discard commits that are purely deployment/infrastructure/CI changes with no user-facing effect, or routine documentation/informational edits (wording tweaks, typo fixes, changelog housekeeping). Exception: a genuinely significant documentation update (a new architecture/design doc, or a substantial rewrite of a core doc) is still included as its own bullet or block — judgment call on "significant," but a one-line doc fix never qualifies. If every commit in range is excluded this way, treat it the same as no new commits at all: skip, no email, state unchanged.

## Email Template

> **Revised post-implementation:** the opening paragraph below ("本封合併 N 版更新，含 vX ~ vY") is no longer the pattern — it named versions too mechanically. The user's six real reference emails show a natural one-to-two sentence opening that mentions the version(s) once, in whatever position reads best, and headlines the most notable thing about the release. See `skills/send-update-email/SKILL.md` Step 7 for the calibration examples now in use.

Modeled on the user-provided reference emails — a clean, document-style layout (not a colored card/box design), organized entirely around features/fixes:

```
Subject: <repo 名稱> 已更新到 <最新版本號>（或版本範圍，如 v2.9.5–v2.9.9）
From: (fixed per-repo sender from the repo's own resend-<repo-slug> MCP connection — see Sending Mechanism above)
To: <recipients>

大家好,

<一到兩句自然語句，帶出版本號（位置依語句而定，不是固定開頭欄位）與這批更新最值得一提的重點>

發布時間: <最新 commit 時間> (Asia/Taipei, UTC+8)

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

—
查看完整 commit 記錄: <repo remote URL>
— <senderName>
— Bridge 自動通知
```

Styling: light inline CSS only — bold larger text for block headings, bold small labels for any subsections actually used, standard bullet lists, generous line spacing, system font stack, `max-width` for readability. No colored box/card chrome. A plain-text version with equivalent structure is sent alongside the HTML body (Resend supports both `html` and `text` in one send). Timezone is fixed to `Asia/Taipei (UTC+8)` — not configurable, since all current recipients are in the same timezone.

Optional: a `🔗 <live app URL>` line right after the release-time line — seen in one of the six reference emails. Not implemented as a required field (this skill has no data source for a repo's deployed URL today); only include it if the user has supplied the URL some other way, never guess one.

The sign-off has two lines: `senderName` (the human name from Config Schema above — omitted entirely if empty, e.g. a config predating this field), then "Bridge 自動通知" with "Bridge" hyperlinked to this plugin's own GitHub repo (`https://github.com/darkstar1227/bridge`, not the repo being reported on), styled to blend into the surrounding text (`color: inherit; text-decoration: none;`) rather than reading as a typical blue underlined link. The plain-text version spells out the URL instead, since plain text can't carry a styled/hidden link: `— Bridge (https://github.com/darkstar1227/bridge) 自動通知`.

## Setup Skill: `/bridge:setup-email-updates`

A separate skill (`skills/setup-email-updates/SKILL.md`) responsible only for creating/editing `.bridge/email-config.json`. `send-update-email` never writes this file itself — clean separation of "configure" vs. "send".

**Mode detection** mirrors `send-update-email`: cwd is a git repo → single-repo mode; cwd is a parent folder → batch mode, scanning immediate subdirectories that are git repos.

`setup-email-updates` is inherently interactive (it asks for recipients) and is meant to be run by a human on demand — unlike `send-update-email-batch`, it is not designed to be scheduled under `/loop`.

**Single-repo mode:**
1. If `.bridge/email-config.json` already exists: show the current `recipients` and `senderName` and ask whether to update either. `lastSentSha` and `mcpServerName` are left untouched by any edit here, so re-running setup can never cause a duplicate send, a gap, or an orphaned MCP connection.
2. If it does not exist: ask the user for the recipient email list, the sender "from" string for this repo, and the sign-off name (`senderName`, defaulting to `git config user.name` if set — see Config Schema above). Register a dedicated `resend-<repo-slug>` MCP connection with the sender string (skipped if one already exists for this slug), then create the file with `lastSentSha` set to current HEAD (so tracking starts from "now" — this run does not retroactively email the full historical log), `mcpServerName` set to the connection just registered, and `senderName` set to the chosen sign-off name.
3. `git add`, `commit` (e.g. `chore: init bridge email config`), and `push` the new/updated file.

**Batch mode (parent folder):**
For each immediate subdirectory that is a git repo: if it already has `.bridge/email-config.json`, show its recipients and ask whether to update; if not, ask whether to initialize it and, if yes, ask for recipients. Repeat one repo at a time until all subdirectories are covered, then commit+push each changed repo's config individually (not a single combined commit across repos — each repo's config is versioned independently in that repo's own history).

## Error Handling & Edge Cases

| Situation | Handling |
|---|---|
| `git pull` fails (conflict/network) | Log error, skip repo — no email, no state change. `send-update-email-batch` continues to next repo. |
| `.bridge/email-config.json` missing | `send-update-email`: stop, tell the user to run `/bridge:setup-email-updates` first. `send-update-email-batch`: skip subdirectory silently — never auto-invoke setup. |
| No new commits since `lastSentSha` (including ranges excluded entirely by the content filter) | Skip — no email, state unchanged. |
| This repo's `resend-<repo-slug>` MCP connection not found | `send-update-email`: stop, tell the user to re-run `/bridge:setup-email-updates`. `send-update-email-batch`: log error, skip sending — never silent. |
| User declines to send at the confirmation step (`send-update-email` only — `send-update-email-batch` has no confirmation step) | Stop — no email, state unchanged. |
| Resend MCP tool call returns an error | Do not update state, do not commit. Report the error (with repo name) to the user / batch summary. |
| `package.json` absent (non-npm repo) | Fall back to commit-time-range block titles; keep root-cause bullet merging. |
| State commit/push fails after a successful send | Explicitly warn the user: email sent, but state not persisted — next run may re-send this range. |

## Verification Plan (no automated test suite — this is a skill, not code)

1. Create a throwaway test repo, add `.bridge/email-config.json` with your own email as the sole recipient, make a few commits (including a `package.json` version bump), run `/bridge:send-update-email`. Confirm: it shows the rendered subject/recipients/body and waits for confirmation; approving it sends the email with correctly grouped content and updates `lastSentSha` (committed+pushed); declining it sends nothing and leaves state untouched.
2. Create a parent folder with 2-3 test repos, one deliberately missing `.bridge/email-config.json`. Run `/bridge:send-update-email-batch` from the parent folder. Confirm the scan/skip logic and the end-of-run summary are correct, and that no confirmation prompt ever appears.
3. Run `/bridge:send-update-email` from inside a parent folder (not a repo) and `/bridge:send-update-email-batch` from inside a single repo. Confirm each stops with a clear message pointing at the other skill, rather than silently doing the wrong thing.
4. Deliberately remove or rename a repo's `resend-<repo-slug>` MCP connection (or don't register it yet) to exercise the failure path in both skills; confirm state is not falsely updated.
5. Run `/bridge:setup-email-updates` on a repo with no config (confirm it's created with `lastSentSha` at current HEAD, `mcpServerName` set, and the `resend-<repo-slug>` connection registered with the chosen sender) and again on the same repo (confirm it shows existing recipients and only changes `recipients`, never `lastSentSha` or `mcpServerName`). Repeat in batch mode against a parent folder with a mix of already-configured and unconfigured repos.
6. Confirm two different repos' emails arrive with two different sender display names, proving the per-repo MCP connection actually isolates sender identity as designed.

## Open Questions / Explicit Assumptions

- [ASSUMPTION] Commit message style varies by repo/team; grouping relies entirely on Claude's semantic reading of message + diff, with no required commit convention.
- [ASSUMPTION] All current recipients share the Asia/Taipei timezone, so it's hardcoded rather than made configurable.
- [ASSUMPTION] "Batch mode" repo discovery is a plain directory scan (immediate children only, not recursive) — nested repos-of-repos are out of scope.
- [OPEN] Exact wording/emoji set for section labels (新增/已修正/已優化) can be refined during implementation to match the reference example's tone as closely as possible.
- [ASSUMPTION] `/loop` batch runs happen on a single, persistent machine where `/bridge:setup-email-updates` has already registered every repo's `resend-<repo-slug>` MCP connection — those registrations live in local Claude Code config, not git, and won't exist on a fresh/ephemeral machine without re-running setup there first.
