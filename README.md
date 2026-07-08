# bridge

A Claude Code plugin that bridges [gstack](https://github.com/garrytan/gstack) reviewed plans into [Superpowers](https://github.com/obra/superpowers) `writing-plans` format.

## What it does

gstack produces strategic plans reviewed by CEO / design / eng / DX lenses. Superpowers `writing-plans` needs execution-level specs: exact files, bite-sized tasks, test commands. This plugin bridges the gap.

**Workflow:**

```
/autoplan          → gstack reviews your plan
/bridge:gstack-to-plan  → transforms it into a Superpowers-compatible spec
                         → auto-invokes superpowers:writing-plans
/superpowers:executing-plans  → implement
```

## Install

### Via Claude marketplace (GitHub URL)

```
/plugin install https://github.com/ds-anxing/bridge
```

### Manual

Add this repo as a marketplace in Claude Code settings, then install the `bridge` plugin.

## Skills

### `/bridge:gstack-to-plan`

Reads the latest gstack-approved plan from your project, extracts structured information (goal, scope, constraints, architecture decisions), produces a Superpowers-compatible handoff doc, and invokes `superpowers:writing-plans`.

**Triggers:**
- `/bridge:gstack-to-plan`
- "bridge plan"
- "gstack to plan"
- "convert gstack plan"
- "handoff to superpowers"

### `/bridge:setup-email-updates`

Creates or edits the `.bridge/email-config.json` a repo needs before `/bridge:send-update-email` or `/bridge:send-update-email-batch` will work — who gets notified, and (on first setup) registers a dedicated `resend-<repo-slug>` MCP connection with its own sender name, so each repo sends under its own identity. Works on a single repo, or in bulk when run from a parent folder containing multiple repos (asks one repo at a time). Interactive by design — not meant to run under `/loop`; that's `/bridge:send-update-email-batch`'s job. Requires `RESEND_API_KEY` in your environment at setup time only.

**Triggers:**
- `/bridge:setup-email-updates`
- "setup email updates"
- "configure update email recipients"
- "init bridge email config"

### `/bridge:send-update-email`

Sends a readable, bullet-point update email via [Resend](https://resend.com) for a single repo, summarizing everything it shipped since the last send — grouped by version and by root cause, not listed commit-by-commit. Renders the email and shows it to you for confirmation before sending anything. Run manually, e.g. near the end of a session. Sends through this repo's own `resend-<repo-slug>` MCP connection (registered by `/bridge:setup-email-updates`) — this skill never holds an API key or a sender address itself.

**Triggers:**
- `/bridge:send-update-email`
- "send update email"
- "email changelog"
- "notify team of updates"

### `/bridge:send-update-email-batch`

The unattended counterpart to `/bridge:send-update-email` — run from a parent folder containing multiple repos (e.g. on a schedule via `/loop`), it scans for configured repos and sends each one's update email with no confirmation step, since there's no one to ask. Shares the same commit-gathering, content-filtering, grouping, and template logic; skips repos with no config or no new commits, and one repo's failure doesn't stop the others.

**Triggers:**
- `/bridge:send-update-email-batch`
- "send update email batch"
- "loop send update emails"
- "batch email changelog"

## Requirements

- [gstack](https://github.com/garrytan/gstack) — for `/autoplan`
- [superpowers](https://github.com/obra/superpowers) — for `writing-plans`
- [Resend](https://resend.com) account and API key, plus [`resend-mcp`](https://github.com/resend/resend-mcp) available via `npx` — for `/bridge:setup-email-updates`, which registers one dedicated MCP connection per repo (neither `send-update-email` nor `send-update-email-batch` needs an API key itself)

## License

MIT
