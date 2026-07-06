---
name: setup-email-updates
description: Create or edit the .bridge/email-config.json that send-update-email needs — recipients and last-sent tracking — for a single repo or in bulk across a parent folder.
triggers:
  - setup email updates
  - configure update email recipients
  - init bridge email config
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Bridge: Setup Email Updates

**Announce at start:** "I'm using the bridge:setup-email-updates skill to configure who receives update emails for this repo."

## Purpose

`send-update-email` refuses to run against a repo that has no `.bridge/email-config.json`. This skill is the only thing that creates or edits that file — recipients and the `lastSentSha` tracking marker.

## Step 1 — Detect Mode

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

- Prints `true` → **single-repo mode**: go to Step 2.
- Errors (not a git repo) → **batch mode**: go to Step 5.

## Step 2 — Single-repo: Check Existing Config

```bash
test -f .bridge/email-config.json && cat .bridge/email-config.json || echo "NO_CONFIG"
```

- Prints `NO_CONFIG` → go to Step 3 (create).
- Prints JSON → go to Step 4 (edit).

## Step 3 — Single-repo: Create Config

Ask the user for the recipient email addresses (they can list as many as they want). Then run:

```bash
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)
jq -n --argjson recipients '["alice@example.com", "bob@example.com"]' --arg sha "$HEAD_SHA" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
```

Replace the `--argjson recipients` value with the actual addresses the user gave you, as a JSON array literal (e.g. `'["alice@example.com","carol@example.com"]'`). Leave `lastSentAt` as `null` — `send-update-email` fills it in after the first real send.

Then commit and push:

```bash
git add .bridge/email-config.json
git commit -m "chore: init bridge email config"
git push
```

## Step 4 — Single-repo: Edit Existing Config

Show the user the `recipients` array from the `cat` output in Step 2. Ask whether to add, remove, or replace any addresses. Rewrite only `recipients` — `lastSentSha` and `lastSentAt` must be preserved exactly as they were, so a re-run of this skill can never cause a duplicate send or a gap:

```bash
jq --argjson recipients '["alice@example.com", "carol@example.com"]' \
  '.recipients = $recipients' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
```

Replace the `--argjson recipients` value with the user's final list. Then commit and push:

```bash
git add .bridge/email-config.json
git commit -m "chore: update bridge email config recipients"
git push
```
