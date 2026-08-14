---
name: setup-email-updates
description: Create or edit the .bridge/email-config.json that send-update-email and send-update-email-batch need — recipients, last-sent tracking, and either a per-repo Resend MCP connection or direct HTTP relay credentials, chosen per repo — for a single repo or in bulk across a parent folder. Always gitignores the config since it can hold a plaintext token.
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

- For `resend` provider setups: `RESEND_API_KEY` environment variable, set wherever *this skill* runs (only needed at setup time — see Step 3). `send-update-email` itself never needs this variable; by the time it runs, the key already lives inside the per-repo MCP server this skill registers.
- For `drava` provider setups: the relay endpoint URL, system id, and bearer token, given to you by the user (see Step 3).
- `.bridge/email-config.json` must never be committed to git — it can hold a plaintext secret (`token` for `drava`). This skill gitignores it as part of Step 3/Step 3b, regardless of which provider is chosen.

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

Ask the user which provider this repo should send through:
- **`resend`** — Resend via a dedicated per-repo MCP connection. Go to Step 3a.
- **`drava`** — direct HTTP POST to an internal relay endpoint (`https://drava.cancerfree.io/api/systems/send-email`), for repos under the newer internal email policy. Go to Step 3b.

Either way, finish with Step 3c (gitignore) before committing.

### Step 3a — `resend` provider

Ask the user for:
1. The recipient email addresses (they can list as many as they want).
2. The sender "from" string to use for this repo's emails, e.g. `Bridge Bot (FlightPath) <noreply@yourdomain.com>`. Suggest a default of `Bridge Bot (<repo name>) <their verified domain address>` if they don't already have one in mind, but let them override it freely — this is a per-repo value, not derived automatically.
3. The human name to sign off the email with (shown alongside the "Bridge 自動通知" line — see `send-update-email`'s Step 7). Default to the local git config's name and let them confirm or override:
   ```bash
   git config user.name
   ```
   If this prints something, offer it as the suggested default. If it's empty, just ask directly with no suggested default.

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

Now write the config, including the MCP connection name and sender name so `send-update-email` knows which connection belongs to this repo and who to sign the email from:

```bash
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)
jq -n --argjson recipients '["alice@example.com", "bob@example.com"]' --arg sha "$HEAD_SHA" --arg mcp "$MCP_SERVER_NAME" --arg sender "Justin Lee" \
  '{provider: "resend", recipients: $recipients, lastSentSha: $sha, lastSentAt: null, mcpServerName: $mcp, senderName: $sender}' \
  > .bridge/email-config.json
```

Replace the `--argjson recipients` value with the actual addresses the user gave you, as a JSON array literal (e.g. `'["alice@example.com","carol@example.com"]'`), and the `--arg sender` value with the sign-off name from step 3 above. Leave `lastSentAt` as `null` — `send-update-email` fills it in after the first real send.

Continue to Step 3c.

### Step 3b — `drava` provider

Ask the user for:
1. The relay endpoint URL — default to `https://drava.cancerfree.io/api/systems/send-email` unless they give a different one.
2. The `system` id (e.g. `relay-c3a238f1bd21`) — this identifies which registered system is sending, on the relay's side.
3. The bearer `token` for that system. Treat this as a secret: never echo it back, never put it in a commit message, never print it in a way that ends up in shell history logs you show the user.
4. The `fromName` to send under (e.g. `Justin(Shopify)`).
5. An optional `replyTo` address.
6. The recipient email addresses.

Write the config:

```bash
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)
jq -n --argjson recipients '["alice@example.com", "bob@example.com"]' --arg sha "$HEAD_SHA" \
      --arg endpoint "https://drava.cancerfree.io/api/systems/send-email" --arg system "relay-c3a238f1bd21" \
      --arg token "..." --arg fromName "Justin(Shopify)" --arg replyTo "justin.lee@cancerfree.io" \
  '{provider: "drava", endpoint: $endpoint, system: $system, token: $token, fromName: $fromName, replyTo: $replyTo,
    recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
```

Replace every placeholder value with what the user gave you. Leave `lastSentAt` as `null`. There is no MCP registration step for this provider — `send-update-email` calls the endpoint directly using the config's own `endpoint`/`system`/`token`.

Continue to Step 3c.

### Step 3c — Gitignore the config (both providers)

`.bridge/email-config.json` can hold a plaintext secret (`token`, for `drava`) and must never be committed. Ensure it's gitignored before touching git at all:

```bash
grep -qxF '.bridge/email-config.json' .gitignore 2>/dev/null || echo '.bridge/email-config.json' >> .gitignore
```

If `.gitignore` didn't exist, this creates it with that one line. Then commit only the `.gitignore` change — never the config file itself:

```bash
git add .gitignore
git commit -m "chore: gitignore bridge email config"
git push
```

If `git status` shows `.bridge/email-config.json` as already tracked (from a config created before this skill gitignored it), warn the user explicitly and offer to run `git rm --cached .bridge/email-config.json` (then commit that removal) so it stops being tracked — a `.gitignore` entry alone does not untrack an already-committed file. Do not run the removal without the user's go-ahead, since it rewrites what's tracked.

## Step 4 — Single-repo: Edit Existing Config

Show the user the `provider`, `recipients` array, and sign-off field (`senderName` for `resend`, `fromName` for `drava`) from the `cat` output in Step 2. Ask whether to add/remove/replace any recipients, and whether to change the sign-off name — this skill does not support switching a repo's `provider` after creation (delete `.bridge/email-config.json` and re-run Step 3 for that). Rewrite only `recipients` and the sign-off field — every other field (`lastSentSha`, `lastSentAt`, `mcpServerName`, `endpoint`, `system`, `token`, `replyTo`) must be preserved exactly as it was, so a re-run of this skill can never cause a duplicate send, a gap, or an orphaned connection.

For `resend`:

```bash
jq --argjson recipients '["alice@example.com", "carol@example.com"]' --arg sender "Justin Lee" \
  '.recipients = $recipients | .senderName = $sender' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
```

For `drava`:

```bash
jq --argjson recipients '["alice@example.com", "carol@example.com"]' --arg fromName "Justin(Shopify)" \
  '.recipients = $recipients | .fromName = $fromName' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
```

Replace `--argjson recipients` with the user's final list and the sign-off arg with their chosen name (unchanged if they didn't want to update it). `.bridge/email-config.json` is gitignored (Step 3c) — this write is local-only, no commit needed. If `.gitignore` somehow doesn't already have the entry (e.g. an edit on a config predating Step 3c), run Step 3c's gitignore commands now.

## Step 5 — Batch: Scan Parent Folder

```bash
for dir in */; do
  dir="${dir%/}"
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
    echo "$dir"
  fi
done
```

For each repo name printed, `cd` into it and run Steps 2-4 for that repo only, one repo at a time — ask the user about provider/recipients for repo #1, finish it (including the Step 3c gitignore commit/push), then move to repo #2. Do not front-load every question before touching any repo.

## Notes

- This skill never sets `lastSentSha` to anything other than the current `HEAD` at creation time — it never touches `lastSentSha` on an edit.
- This skill is interactive by design. Do not schedule it under `/loop`; that's `/bridge:send-update-email-batch`'s job — it processes a parent folder of already-configured repos unattended, using each repo's config.
- `resend` provider: each repo gets its own dedicated Resend MCP connection (named `resend-<repo-slug>`) so it can send under its own sender name — this is why neither `send-update-email` nor `send-update-email-batch` ever needs `RESEND_API_KEY` itself. Changing an existing repo's sender name isn't handled by this skill; to do that, run `claude mcp remove resend-<repo-slug>` first, then re-run this skill's create flow (Step 3a) to register it fresh with the new sender. Every machine that will run `send-update-email`/`send-update-email-batch` for a given repo needs that repo's `resend-<repo-slug>` MCP connection registered on it — this lives in the local Claude Code config, not in git, so it does not travel with `git clone`. Re-run this skill on any new machine before expecting `resend` sends to work there.
- `drava` provider: no MCP connection or per-machine registration involved — the config itself carries the `endpoint`/`system`/`token` needed to send. This is exactly why the config must stay gitignored (Step 3c): unlike `resend` (where the secret lives in local MCP config, never in the repo), `drava`'s secret lives in the config file itself.
- `.bridge/email-config.json` is gitignored for both providers (Step 3c) and is never committed by this skill or by `send-update-email`/`send-update-email-batch`. It's a local, per-machine file — copy it manually (out-of-band, not via git) to any other machine that needs to run sends for this repo.
