---
name: setup-email-updates
description: Create or edit the .bridge/email-config.json that send-update-email needs — recipients, last-sent tracking, and either a per-repo Resend MCP connection or a fully custom HTTP POST structure (endpoint, headers, body template), chosen per repo — for a single repo or in bulk across a parent folder. Always gitignores the config since it can hold plaintext secrets.
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

**Announce at start:** "I'm using the bridge-dev:setup-email-updates skill to configure who receives update emails for this repo."

## Purpose

`send-update-email` refuses to run against a repo that has no `.bridge/email-config.json`. This skill is the only thing that creates or edits that file — recipients, the `lastSentSha` tracking marker, and (on first setup) a dedicated per-repo Resend MCP connection so each repo can send under its own sender name.

## Requirements

- For `resend` provider setups: `RESEND_API_KEY` environment variable, set wherever *this skill* runs (only needed at setup time — see Step 3). `send-update-email` itself never needs this variable; by the time it runs, the key already lives inside the per-repo MCP server this skill registers.
- For `custom` provider setups: the user must supply the complete HTTP POST structure their endpoint expects — the URL, every header (including whatever auth scheme it uses), and the exact JSON body shape, given to you by the user (see Step 3b). This skill does not assume any particular vendor's API shape.
- `.bridge/email-config.json` must never be committed to git — it can hold plaintext secrets (any value inside `headers` for `custom`). This skill gitignores it as part of Step 3/Step 3b, regardless of which provider is chosen.

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
- **`custom`** — direct HTTP POST to any endpoint the user provides, using a POST structure they fully specify themselves. Go to Step 3b.

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

### Step 3b — `custom` provider

This provider makes no assumption about the target API's shape — the user supplies the complete POST structure themselves. Ask for, in order:

1. **The endpoint URL** — the full URL this skill will POST to.
2. **The complete `headers` object**, as JSON — every header the endpoint needs, including whichever auth scheme it uses (`Authorization: Bearer ...`, an API-key header, whatever their vendor requires). There is no assumed auth shape; the user's JSON is sent verbatim. If they don't include `Content-Type`, this skill adds `Content-Type: application/json` automatically at send time — mention this so they only need to specify it if they want something else.
3. **The complete request body**, as a JSON template, exactly matching what their endpoint's documentation expects — every field they'd normally hardcode (vendor ids, system names, flags, nested objects, whatever their API needs) written out literally. Wherever a value must vary per send, they mark the spot with one of these exact placeholder tokens (as a bare JSON string value, not concatenated into a larger string):
   - `"{{TO}}"` → the recipient list, substituted as a JSON array of email strings
   - `"{{TO_CSV}}"` → the recipient list, substituted as a single comma-separated string (use this instead of `{{TO}}` if their API wants one string, not an array)
   - `"{{SUBJECT}}"` → the rendered subject line
   - `"{{HTML}}"` → the rendered HTML email body
   - `"{{TEXT}}"` → the rendered plain-text email body (only needed if their API takes a separate text field)
   - `"{{FROM_NAME}}"` → the sign-off name given in step 5 below
   - `"{{REPLY_TO}}"` → the reply-to address given in step 6 below (substituted as an empty string if they skip it)

   Show them a concrete example if it helps, e.g.:
   ```json
   {"system": "relay-c3a238f1bd21", "to": "{{TO}}", "subject": "{{SUBJECT}}", "html": "{{HTML}}", "fromName": "{{FROM_NAME}}", "replyTo": "{{REPLY_TO}}"}
   ```
4. **Any secret values** embedded in the headers or body (bearer tokens, API keys). Treat these as secrets from the moment they're given: never echo them back, never put them in a commit message, never print them in a way that ends up in shell history logs you show the user.
5. **The sign-off name** to send under (e.g. `Justin(Shopify)`) — this is `senderName`, shown in the email body's sign-off line (see `send-update-email`'s Step 7) and available to the body template as `{{FROM_NAME}}`.
6. An optional `replyTo` address.
7. The recipient email addresses.

Write the user's `headers` and body template to temp files first and validate each is well-formed JSON before using it — this catches a malformed paste before it lands in the config:

```bash
mkdir -p .bridge
HEAD_SHA=$(git rev-parse HEAD)

HEADERS_FILE=$(mktemp)
cat > "$HEADERS_FILE" <<'EOF'
{"Authorization": "Bearer ..."}
EOF
jq empty "$HEADERS_FILE" || { echo "Invalid headers JSON — ask the user to fix it and retry."; exit 1; }

BODY_TEMPLATE_FILE=$(mktemp)
cat > "$BODY_TEMPLATE_FILE" <<'EOF'
{"system": "relay-c3a238f1bd21", "to": "{{TO}}", "subject": "{{SUBJECT}}", "html": "{{HTML}}", "fromName": "{{FROM_NAME}}", "replyTo": "{{REPLY_TO}}"}
EOF
jq empty "$BODY_TEMPLATE_FILE" || { echo "Invalid body template JSON — ask the user to fix it and retry."; exit 1; }

jq -n --argjson recipients '["alice@example.com", "bob@example.com"]' --arg sha "$HEAD_SHA" \
      --arg endpoint "https://example.com/api/send" \
      --slurpfile headers "$HEADERS_FILE" --slurpfile bodyTemplate "$BODY_TEMPLATE_FILE" \
      --arg senderName "Justin(Shopify)" --arg replyTo "justin.lee@example.com" \
  '{provider: "custom", endpoint: $endpoint, headers: $headers[0], bodyTemplate: $bodyTemplate[0],
    senderName: $senderName, replyTo: $replyTo,
    recipients: $recipients, lastSentSha: $sha, lastSentAt: null}' \
  > .bridge/email-config.json
rm -f "$HEADERS_FILE" "$BODY_TEMPLATE_FILE"
```

Replace every placeholder value (the heredoc contents, `--arg endpoint`, `--arg senderName`, `--arg replyTo`, `--argjson recipients`) with what the user actually gave you. Leave `lastSentAt` as `null`. There is no MCP registration step for this provider — `send-update-email` calls the endpoint directly using the config's own `endpoint`/`headers`/`bodyTemplate`.

Continue to Step 3c.

### Step 3c — Gitignore the config (both providers)

`.bridge/email-config.json` can hold plaintext secrets (any value inside `headers`, for `custom`) and must never be committed. Ensure it's gitignored before touching git at all:

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

Show the user the `provider`, `recipients` array, and sign-off field (`senderName`, for both providers) from the `cat` output in Step 2. Ask whether to add/remove/replace any recipients, and whether to change the sign-off name — this skill does not support switching a repo's `provider` after creation (delete `.bridge/email-config.json` and re-run Step 3 for that). Rewrite only `recipients` and `senderName` — every other field (`lastSentSha`, `lastSentAt`, `mcpServerName`, `endpoint`, `headers`, `bodyTemplate`, `replyTo`) must be preserved exactly as it was, so a re-run of this skill can never cause a duplicate send, a gap, or an orphaned connection.

For `resend`:

```bash
jq --argjson recipients '["alice@example.com", "carol@example.com"]' --arg sender "Justin Lee" \
  '.recipients = $recipients | .senderName = $sender' \
  .bridge/email-config.json > .bridge/email-config.json.tmp
mv .bridge/email-config.json.tmp .bridge/email-config.json
```

For `custom`:

```bash
jq --argjson recipients '["alice@example.com", "carol@example.com"]' --arg sender "Justin(Shopify)" \
  '.recipients = $recipients | .senderName = $sender' \
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
- This skill is interactive by design. Do not schedule it under `/loop`.
- `resend` provider: each repo gets its own dedicated Resend MCP connection (named `resend-<repo-slug>`) so it can send under its own sender name — this is why `send-update-email` never needs `RESEND_API_KEY` itself. Changing an existing repo's sender name isn't handled by this skill; to do that, run `claude mcp remove resend-<repo-slug>` first, then re-run this skill's create flow (Step 3a) to register it fresh with the new sender. Every machine that will run `send-update-email` for a given repo needs that repo's `resend-<repo-slug>` MCP connection registered on it — this lives in the local Claude Code config, not in git, so it does not travel with `git clone`. Re-run this skill on any new machine before expecting `resend` sends to work there.
- `custom` provider: no MCP connection or per-machine registration involved — the config itself carries the `endpoint`/`headers`/`bodyTemplate` needed to send. This is exactly why the config must stay gitignored (Step 3c): unlike `resend` (where the secret lives in local MCP config, never in the repo), `custom`'s secrets live in the config file itself (inside `headers`).
- `.bridge/email-config.json` is gitignored for both providers (Step 3c) and is never committed by this skill or by `send-update-email`. It's a local, per-machine file — copy it manually (out-of-band, not via git) to any other machine that needs to run sends for this repo.
