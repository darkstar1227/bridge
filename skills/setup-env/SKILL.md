---
name: setup-env
description: Export the user-scope Claude Code plugins, marketplaces, and gstack installation on this machine into a portable manifest, or install from an existing manifest onto a new machine to reproduce the same Claude Code environment. Trigger when the user wants to back up their plugin setup, replicate their Claude Code environment on a new machine, or bootstrap a fresh machine with the same plugins/skills they already use elsewhere.
triggers:
  - export my plugins
  - back up my claude code setup
  - install my plugins on a new machine
  - replicate my claude code environment
  - bootstrap this machine's claude code setup
  - sync plugins to new machine
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# Setup Env

**Announce at start:** "I'm using the bridge:setup-env skill to [export/install] this Claude Code environment's plugins."

## Purpose

Claude Code plugins/marketplaces are installed per-machine in `~/.claude/plugins/`. There's no built-in way to carry "everything I have installed" from one machine to another. This skill closes that gap in two directions: **export** snapshots the current machine's user-scope plugins and marketplaces (plus the separately-installed `gstack` skill suite) into a manifest file; **install** reads that manifest on a different machine and reproduces the setup by driving the real `claude plugin` CLI.

This only covers **user-scope** plugins (`scope: "user"` in `~/.claude/plugins/installed_plugins.json`) — plugins installed per-project (`scope: "project"`/`"local"`) belong to that project's own setup, not the user's personal environment, and are deliberately excluded.

## Step 1 — Determine Mode

If the user's request doesn't already make it obvious, ask (via `AskUserQuestion`) whether this is:
- **Export** — snapshot this machine's current setup to a manifest file
- **Install** — read an existing manifest and set this machine up to match

## Step 2 — Export

1. Read `~/.claude/plugins/installed_plugins.json`. Filter to entries where at least one install record has `"scope": "user"`.
2. Read `~/.claude/plugins/known_marketplaces.json` to resolve each plugin's marketplace alias (the part after `@` in its key, e.g. `context-mode@context-mode` → marketplace `context-mode`) to its actual source (`{"source": "github", "repo": "org/repo"}`).
3. Check whether `~/.claude/skills/gstack` exists and looks like a real install (has `setup` script, `package.json`). If so, capture it as a separate block — it is **not** part of the plugin-marketplace system, it's a standalone git-cloned tool.
4. Write the manifest to `docs/env-setup/claude-plugins-manifest.json` in this repo (create the directory if missing), using this shape:

```json
{
  "generatedAt": "<today's date, YYYY-MM-DD>",
  "marketplaces": [
    { "name": "claude-plugins-official", "repo": "anthropics/claude-plugins-official" }
  ],
  "plugins": [
    { "name": "context-mode", "marketplace": "context-mode" }
  ],
  "gstack": {
    "installed": true,
    "cloneUrl": "https://github.com/garrytan/gstack.git",
    "installPath": "~/.claude/skills/gstack",
    "setupCommand": "git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup"
  }
}
```

5. If the same plugin name appears against two different marketplaces (e.g. installed once from `claude-plugins-official` and once from its original community marketplace), include both entries but call this out to the user directly in chat as a likely-redundant duplicate — don't silently dedupe, since the user may have a reason for both, but don't hide it either.
6. Summarize in chat what was captured (counts of marketplaces/plugins, whether gstack was included) and the manifest's path. Recommend the user commit `docs/env-setup/claude-plugins-manifest.json` to git so it travels with the repo.

## Step 3 — Install

1. Locate the manifest — a path the user gave, or `docs/env-setup/claude-plugins-manifest.json` in this repo.
2. Run `claude plugin marketplace list` and `claude plugin list` to see what's already present on this machine — never re-add or re-install something already there.
3. For each marketplace in the manifest not already known, run `claude plugin marketplace add <repo>`.
4. For each plugin in the manifest not already installed, run `claude plugin install <name>@<marketplace>`.
5. If the manifest has a `gstack` block and `~/.claude/skills/gstack` doesn't already exist, **stop and ask the user before running `setupCommand`** — it clones a third-party repo and executes its own `./setup` script, which is a different trust boundary than installing a Claude Code plugin through the marketplace system. Only run it after explicit confirmation.
6. After a confirmed gstack install, ask the user whether to also add the gstack CLAUDE.md section (the block describing `/browse` and the other gstack skills) — don't add it unprompted, since it changes how every future session on this machine behaves.
7. Report what was added vs. already-present vs. skipped (e.g. gstack declined). Don't claim the environment is "fully replicated" if anything was skipped — list it explicitly.

## Notes

- This skill never modifies another repo's plugin scope (project/local installs) — it only touches user-scope state, which is what "this machine's personal environment" means here.
- Re-running export is safe and idempotent — it always overwrites the manifest with the current state, it doesn't merge with a stale one.
- Re-running install is safe — steps 3-4 already skip anything present; it will not duplicate-install a plugin.
