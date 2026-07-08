---
name: setup-email-updates
description: Create or edit the .bridge/email-config.json that send-update-email and send-update-email-batch need — recipients, last-sent tracking, and a per-repo Resend MCP connection — for a single repo or in bulk across a parent folder.
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

Both `send-update-email` and `send-update-email-batch` refuse to run against a repo that has no `.bridge/email-config.json`. This skill is the only thing that creates or edits that file — recipients, the `lastSentSha` tracking marker, and (on first setup) a dedicated per-repo Resend MCP connection so each repo can send under its own sender name.

## Requirements

- `RESEND_API_KEY` environment variable, set wherever *this skill* runs (only needed at setup time — see Step 3). `send-update-email` itself never needs this variable; by the time it runs, the key already lives inside the per-repo MCP server this skill registers.

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

Ask the user for:
1. The recipient email addresses (they can list as many as they want).
2. The sender "from" string to use for this repo's emails, e.g. `Bridge Bot (FlightPath) <noreply@yourdomain.com>`. Suggest a default of `Bridge Bot (<repo name>) <their verified domain address>` if they don't already have one in mind, but let them override it freely — this is a per-repo value, not derived automatically.

Derive a slug for this repo and check whether a dedicated MCP connection already exists for it:

```bash
REPO_SLUG=$(basename "$(git rev-parse --show-toplevel)" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')
MCP_SERVER_NAME="resend-$REPO_SLUG"
claude mcp get "$MCP_SERVER_NAME" >/dev/null 2>&1
echo "exit: $?"
```

- Exit `0` → a connection with this name already exists (from an earlier partial setup attempt). Skip straight to writing the config below — reuse it as-is rather than re-registering.
- Non-zero → register it now, using the `RESEND_API_KEY` environment variable and the sender string from step 2 above:

```bash
claude mcp add "$MCP_SERVER_NAME" -e RESEND_API_KEY="$RESEND_API_KEY" -e SENDER_EMAIL_ADDRESS="Bridge Bot (FlightPath) <noreply@yourdomain.com>" -- npx -y resend-mcp
```

Replace the `SENDER_EMAIL_ADDRESS` value with the exact sender string the user gave you. If `RESEND_API_KEY` isn't set in your environment, stop and tell the user to export it before continuing — do not proceed to registration without it.

Now write the config, including the MCP connection name so `send-update-email` knows which one belongs to this repo:

```bash
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)
jq -n --argjson recipients '["alice@example.com", "bob@example.com"]' --arg sha "$HEAD_SHA" --arg mcp "$MCP_SERVER_NAME" \
  '{recipients: $recipients, lastSentSha: $sha, lastSentAt: null, mcpServerName: $mcp}' \
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

Show the user the `recipients` array from the `cat` output in Step 2. Ask whether to add, remove, or replace any addresses. Rewrite only `recipients` — `lastSentSha`, `lastSentAt`, and `mcpServerName` must be preserved exactly as they were, so a re-run of this skill can never cause a duplicate send, a gap, or an orphaned MCP connection:

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

## Step 5 — Batch: Scan Parent Folder

```bash
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    echo "$dir"
  fi
done
```

For each repo name printed, `cd` into it and run Steps 2-4 for that repo only, one repo at a time — ask the user about recipients for repo #1, finish it (including commit+push), then move to repo #2. Do not front-load every question before touching any repo.

## Notes

- This skill never sets `lastSentSha` to anything other than the current `HEAD` at creation time — it never touches `lastSentSha` on an edit.
- This skill is interactive by design. Do not schedule it under `/loop`; that's `/bridge:send-update-email-batch`'s job — it processes a parent folder of already-configured repos unattended, using the config and MCP connection this skill sets up.
- Each repo gets its own dedicated Resend MCP connection (named `resend-<repo-slug>`) so it can send under its own sender name — this is why neither `send-update-email` nor `send-update-email-batch` ever needs `RESEND_API_KEY` itself. Changing an existing repo's sender name isn't handled by this skill; to do that, run `claude mcp remove resend-<repo-slug>` first, then re-run this skill's create flow (Step 3) to register it fresh with the new sender.
- Every machine that will run `send-update-email` or `send-update-email-batch` for a given repo (including any machine running `/loop`) needs that repo's `resend-<repo-slug>` MCP connection registered on it — this lives in the local Claude Code config, not in git, so it does not travel with `git clone`. Re-run this skill on any new machine before expecting sends to work there.
