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

Creates or edits the `.bridge/email-config.json` a repo needs before `/bridge:send-update-email` will work — who gets notified, and (on first setup) registers a dedicated `resend-<repo-slug>` MCP connection with its own sender name, so each repo sends under its own identity. Works on a single repo, or in bulk when run from a parent folder containing multiple repos (asks one repo at a time). Interactive by design — not meant to run under `/loop`. Requires `RESEND_API_KEY` in your environment at setup time only.

**Triggers:**
- `/bridge:setup-email-updates`
- "setup email updates"
- "configure update email recipients"
- "init bridge email config"

### `/bridge:send-update-email`

Sends a readable, bullet-point update email via [Resend](https://resend.com) summarizing everything a repo shipped since the last send — grouped by version and by root cause, not listed commit-by-commit. Works on a single repo (run manually near the end of a session) or in batch across a parent folder of repos (run on a schedule via `/loop`). Sends through this repo's own `resend-<repo-slug>` MCP connection (registered by `/bridge:setup-email-updates`, one per repo) — this skill never holds an API key or a sender address itself.

**Triggers:**
- `/bridge:send-update-email`
- "send update email"
- "email changelog"
- "notify team of updates"

## Requirements

- [gstack](https://github.com/garrytan/gstack) — for `/autoplan`
- [superpowers](https://github.com/obra/superpowers) — for `writing-plans`
- [Resend](https://resend.com) account and API key, plus [`resend-mcp`](https://github.com/resend/resend-mcp) available via `npx` — for `/bridge:setup-email-updates`, which registers one dedicated MCP connection per repo (`send-update-email` itself needs neither)

## License

MIT
