---
type: Operations Guide
title: Project, email, and environment operations
description: "Operational Bridge skills for project convention audits, Resend-based repository update emails, and portable user-scope Claude Code plugin environments."
resource: skills/init-project/SKILL.md
tags: [operations, project-setup, email, resend, environment]
---

# Project, email, and environment operations

## Family role

These skills apply the [plugin and skill model](../architecture/plugin-and-skill-model.md) to target repositories and user environments. They are operational workflows with deliberately narrow authority: detect and ask before applying optional setup, require confirmation before interactive sends, and keep credentials out of repository configuration.

## Project initialization and audit

`bridge:init-project` detects signals for Python/uv, Node/TypeScript, Docker, Supabase, and Git/environment conventions. Git/environment always applies; missing signals for other modules require a user yes/no decision before that module is considered active.

The active modules can create or assess:

- Python: `pyproject.toml`, Ruff configuration, and a pre-commit configuration (but it does not install the hook).
- Node/TypeScript: package-manager initialization by choice, strict `tsconfig.json`, ESLint/Prettier configuration, and optional confirmed hook tooling.
- Docker: profile-oriented compose layout that keeps stateful services under an `infra` profile and uses app-only `dev`/`prod` targets.
- Supabase: CLI/config readiness while never editing `supabase/migrations/`.
- Git/environment: `.env` gitignore coverage and placeholder-only `.env.example` entries derived from source usage.

It writes only a managed region in the target `CLAUDE.md` and emits `docs/init-project-report-YYYY-MM-DD.md`. Folder moves, existing-Makefile changes, package installation, pre-commit installation, and Supabase CLI installation remain gated or advisory. The skill ends with a read-only `claude-md-management:claude-md-improver` assessment.

This workflow **creates the conventions that govern future changes under** [the plugin and skill model](../architecture/plugin-and-skill-model.md). Source: [`skills/init-project/SKILL.md`](../../skills/init-project/SKILL.md).

## Repository update emails

The email skills form a configuration-to-delivery lifecycle:

```text
setup-email-updates
  -> .bridge/email-config.json + dedicated resend-<repo-slug> MCP connection
  -> send-update-email (interactive) OR send-update-email-batch (unattended)
```

`setup-email-updates` creates the per-target-repo configuration. The shared values include recipients, `lastSentSha`, `lastSentAt`, `mcpServerName`, and optional sender name. The Resend API key is required only for setup; the design keeps the key and sender address in the local dedicated MCP connection rather than the repository config.

`send-update-email` works in one repository and requires explicit approval after rendering the exact recipients, subject, and plain-text content. `send-update-email-batch` runs only from a parent folder, processes immediate git-worktree children, and isolates failure per repository without confirmation. Both:

- pull before gathering commits;
- ignore Bridge bookkeeping-only commits, routine CI/deploy work, and routine documentation changes, while retaining significant documentation changes;
- cluster retained changes by real-world topic rather than commit or version number;
- call the configured MCP send tool without a `from` override;
- update and commit state only after a successful send;
- warn clearly when sending succeeds but state persistence fails, because a later run may duplicate the range.

The paired prompts intentionally share core logic; edits to commit filtering, grouping, templates, send behavior, or persistence mechanics must be applied to both. This email lifecycle **is surfaced through** [the plugin and skill model](../architecture/plugin-and-skill-model.md) and is independent of [planning and pipeline workflows](../workflows/planning-and-pipelines.md), which do not send external notifications. Sources: [`skills/setup-email-updates/SKILL.md`](../../skills/setup-email-updates/SKILL.md), [`skills/send-update-email/SKILL.md`](../../skills/send-update-email/SKILL.md), and [`skills/send-update-email-batch/SKILL.md`](../../skills/send-update-email-batch/SKILL.md).

## Portable user-scope Claude environment

`bridge:setup-env` exports or installs a manifest at `docs/env-setup/claude-plugins-manifest.json`. It covers user-scope Claude plugins and marketplaces plus optional standalone gstack metadata; it explicitly excludes project/local plugin scope.

On export, it snapshots the current user-scope installation and marketplace origins. On install, it checks current state and adds only missing entries. It warns about duplicate plugins from different marketplaces and requires approval before cloning/running a third-party gstack `setupCommand`. It is designed to be idempotent but does not claim full replication when entries were skipped.

The manifest is an operational artifact named in `CLAUDE.md`; it **preserves the external plugin environment needed to use** [planning and pipeline workflows](../workflows/planning-and-pipelines.md). Source: [`skills/setup-env/SKILL.md`](../../skills/setup-env/SKILL.md).

## Change checklist

- Do not add secret values or sender identities to repository files; document only configuration locations and credential boundaries.
- Preserve state-update ordering for email delivery: send success precedes tracked-state mutation.
- Keep interactive and unattended email behavior distinct while synchronizing their shared core.
- Preserve `init-project`’s confirmation requirements and its migration/no-install safeguards.
- Keep setup-env limited to user scope unless the skill’s requirements intentionally change.
