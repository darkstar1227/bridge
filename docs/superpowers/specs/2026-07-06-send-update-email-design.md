# Design: `/bridge:send-update-email` + `/bridge:setup-email-updates`

_Date: 2026-07-06_
_Status: Approved by user, pending final review before implementation planning_

## Overview

Two new skills in the `bridge` plugin:

- `/bridge:send-update-email` — sends colleagues a readable, well-formatted update email whenever a tracked repo has new commits since the last send. It uses the Resend API to deliver mail, groups related commits/npm-version bumps into single explanations, and tracks per-repo send state inside the repo itself (committed to git) so state travels with the repo across machines and clones.
- `/bridge:setup-email-updates` — the companion setup skill that creates/edits the `.bridge/email-config.json` a repo needs before `send-update-email` will work, for one repo or in bulk across a parent folder.

Both are pure skills (Markdown instructions for Claude to follow at execution time via Bash/curl/Read/Write) — consistent with this repo's "no build step, no runtime" convention. No new script files or package.json are introduced.

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

Single skill: `skills/send-update-email/SKILL.md`, invoked as `/bridge:send-update-email`.

The skill auto-detects its mode based on the current working directory — no separate skill and no `--batch` flag:

```
/bridge:send-update-email
  │
  ├─ cwd is a git repo? ──yes──▶ Single-repo mode: process only this repo
  │
  └─ no (cwd is a parent folder) ──▶ Batch mode:
        scan immediate subdirectories;
        for each subdirectory that is a git repo AND has
        `.bridge/email-config.json`, run the same core workflow
```

This keeps one copy of the send/grouping/template logic — no risk of two skill files drifting apart.

## Core Workflow (runs once per repo, in either mode)

1. `git pull` to bring the repo to the latest remote state.
   - On failure: log the error, skip this repo (no email, no state change). In batch mode, continue to the next repo.
2. Read `.bridge/email-config.json` for `recipients` and `lastSentSha`.
   - If missing, in single-repo mode: stop and tell the user to run `/bridge:setup-email-updates` first — `send-update-email` does not create config itself (that's the setup skill's job).
   - If missing, in batch mode: skip this subdirectory silently (no prompt — batch mode is meant to run unattended).
3. Run `git log <lastSentSha>..HEAD` to get the accumulated commits.
   - If no new commits: skip — no email sent, `lastSentSha` unchanged.
4. For each commit in range, read the commit message and diff, paying particular attention to `version` changes in `package.json`.
5. Apply the two-level grouping logic (see below) to build the email body.
6. Render the HTML (+ plain-text fallback) template and call the Resend API to send to `recipients`.
   - On Resend API error: do not update state, do not commit. Report the error (with repo name) to the user / to the batch-mode summary.
7. On successful send: update `lastSentSha` to current HEAD and `lastSentAt` to now, then `git add`, `commit` (fixed message, e.g. `chore: update bridge email state`), and `push` `.bridge/email-config.json` back to the repo.
   - If this commit/push step fails after the email was already sent: explicitly warn the user that the email went out but the state wasn't persisted, so the next run may re-send the same range.

## Batch Mode Summary

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
  "lastSentAt": "2026-07-01T09:00:00Z"
}
```

- `recipients`: flat array of email addresses; all are `to` recipients of one shared email (no per-recipient personalization, no BCC split).
- `lastSentSha`: HEAD commit at the time of the last successful send; the anchor for the next `git log` range.
- `lastSentAt`: informational only, for human debugging — not used in any logic branch.

### Secrets (environment variables — never written to any config file)

- `RESEND_API_KEY` — Resend API key.
- `BRIDGE_EMAIL_FROM` — sender address, in `"Display Name <email@domain>"` format (domain must be verified in Resend). This is global (one value for all repos). The skill constructs the per-repo `From` header by inserting the repo name between the display name and the email — e.g. `BRIDGE_EMAIL_FROM="Bridge Bot <noreply@example.com>"` + repo `FlightPath` → `From: Bridge Bot (FlightPath) <noreply@example.com>`. No per-repo sender config needed.

If either is missing: single-repo mode stops and tells the user exactly what to set; batch mode logs the error for that run and skips sending (never silently drops it).

## Commit / Version Grouping Logic

Two levels of merging, modeled directly on the reference email the user provided:

**Level 1 — consecutive small version bumps → one version block.**
Extract `package.json` version changes across the commit range (e.g. v3.1.1 → v3.1.2 → ... → v3.1.5). If a consecutive run of versions all revolve around the same theme (e.g., all are fixes/optimizations for the same underlying area), collapse them into a single version block. The block heading uses the *latest* version number in that run, plus a one-line theme summary written by Claude (e.g., "v3.1.5 — 平台安全性與穩定性修正"). A version that introduces an independent new feature gets its own block, titled after that feature.

**Level 2 — same-root-cause commits → one bullet.**
Within a version block, commits are read (message + diff) and judged by Claude for shared root cause / same class of issue (no reliance on Conventional Commits or any enforced message format). Commits sharing a root cause collapse into a single bullet describing the fix's effect on users/system, not a per-commit list. Each block groups its bullets under whichever of **新增 / 已修正 / 已優化** subsections apply (subsections with nothing to report are omitted, not shown empty).

If `package.json` does not exist (non-npm repo): skip version-number-based titling; use the commit-time range as the block boundary/heading instead, and keep applying Level 2 same-root-cause bullet merging based on commit semantics.

## Email Template

Modeled on the user-provided reference example — a clean, document-style layout (not a colored card/box design):

```
Subject: <repo 名稱> 已更新到 <最新版本號>
From: <BRIDGE_EMAIL_FROM display name>（<repo 名稱>）<BRIDGE_EMAIL_FROM email>
To: <recipients>

大家好,

<repo 名稱> 發布了 <最新版本號>（本封合併 <N> 版更新，含 vX.X.X ~ vY.Y.Y）。

發布時間: <最新 commit 時間> (Asia/Taipei, UTC+8)

<版本號> — <這批更新的一句話主題>
新增
• xxx
已修正
• xxx（合併同根因的多個 commit）

<版本號> — <另一批更新的主題>
已修正
• xxx
已優化
• xxx

—
查看完整 commit 記錄: <repo remote URL>
— Bridge 自動通知
```

Styling: light inline CSS only — bold larger text for version headings, bold small labels for 新增/已修正/已優化, standard bullet lists, generous line spacing, system font stack, `max-width` for readability. No colored box/card chrome. A plain-text version with equivalent structure is sent alongside the HTML body (Resend supports both `html` and `text` in one send). Timezone is fixed to `Asia/Taipei (UTC+8)` — not configurable, since all current recipients are in the same timezone.

## Setup Skill: `/bridge:setup-email-updates`

A separate skill (`skills/setup-email-updates/SKILL.md`) responsible only for creating/editing `.bridge/email-config.json`. `send-update-email` never writes this file itself — clean separation of "configure" vs. "send".

**Mode detection** mirrors `send-update-email`: cwd is a git repo → single-repo mode; cwd is a parent folder → batch mode, scanning immediate subdirectories that are git repos.

**Single-repo mode:**
1. If `.bridge/email-config.json` already exists: show the current `recipients` list and ask whether to add/remove/replace any. `lastSentSha` is left untouched by any edit here — only `recipients` can change, so re-running setup can never cause a duplicate send or a gap.
2. If it does not exist: ask the user for the recipient email list, then create the file with `lastSentSha` set to current HEAD (so tracking starts from "now" — this run does not retroactively email the full historical log).
3. `git add`, `commit` (e.g. `chore: init bridge email config`), and `push` the new/updated file.

**Batch mode (parent folder):**
For each immediate subdirectory that is a git repo: if it already has `.bridge/email-config.json`, show its recipients and ask whether to update; if not, ask whether to initialize it and, if yes, ask for recipients. Repeat one repo at a time until all subdirectories are covered, then commit+push each changed repo's config individually (not a single combined commit across repos — each repo's config is versioned independently in that repo's own history).

## Error Handling & Edge Cases

| Situation | Handling |
|---|---|
| `git pull` fails (conflict/network) | Log error, skip repo — no email, no state change. Batch mode continues to next repo. |
| `.bridge/email-config.json` missing | Single mode: stop, tell the user to run `/bridge:setup-email-updates` first. Batch mode: skip subdirectory silently. |
| No new commits since `lastSentSha` | Skip — no email, state unchanged. |
| `RESEND_API_KEY` / `BRIDGE_EMAIL_FROM` unset | Single mode: stop, state exactly what's missing. Batch mode: log error, skip sending — never silent. |
| Resend API returns an error (4xx/5xx) | Do not update state, do not commit. Report the error (with repo name) to the user / batch summary. |
| `package.json` absent (non-npm repo) | Fall back to commit-time-range block titles; keep root-cause bullet merging. |
| State commit/push fails after a successful send | Explicitly warn the user: email sent, but state not persisted — next run may re-send this range. |

## Verification Plan (no automated test suite — this is a skill, not code)

1. Create a throwaway test repo, add `.bridge/email-config.json` with your own email as the sole recipient, make a few commits (including a `package.json` version bump), run `/bridge:send-update-email`. Confirm: the email arrives with correctly grouped content, and `lastSentSha` is updated and committed+pushed.
2. Create a parent folder with 2-3 test repos, one deliberately missing `.bridge/email-config.json`. Run the same command from the parent folder. Confirm the scan/skip logic and the end-of-run summary are correct.
3. Deliberately misconfigure `RESEND_API_KEY` to exercise the failure path; confirm state is not falsely updated.
4. Run `/bridge:setup-email-updates` on a repo with no config (confirm it's created with `lastSentSha` at current HEAD) and again on the same repo (confirm it shows existing recipients and only changes `recipients`, never `lastSentSha`). Repeat in batch mode against a parent folder with a mix of already-configured and unconfigured repos.

## Open Questions / Explicit Assumptions

- [ASSUMPTION] Commit message style varies by repo/team; grouping relies entirely on Claude's semantic reading of message + diff, with no required commit convention.
- [ASSUMPTION] All current recipients share the Asia/Taipei timezone, so it's hardcoded rather than made configurable.
- [ASSUMPTION] "Batch mode" repo discovery is a plain directory scan (immediate children only, not recursive) — nested repos-of-repos are out of scope.
- [OPEN] Exact wording/emoji set for section labels (新增/已修正/已優化) can be refined during implementation to match the reference example's tone as closely as possible.
