---
name: setup-relay-provider-template
description: Wire cancerfreebiotech/claude-profile-kit's claude-project-template (orchestrator + 7 specialized subagents + native advisor) into the current project, driven entirely by an already-configured relay LiteLLM provider — queries the provider's gateway for its real model list, assigns a model per role, and writes every file (CLAUDE.md, .claude/agents/*.md, .claude/settings.json) without the user hand-editing anything.
triggers:
  - setup relay provider template
  - apply claude-project-template with relay
  - relay provider template
  - 套用 claude-project-template
  - 用 relay provider 設定 agent model
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Bridge: Setup Relay Provider Template

**Announce at start:** "I'm using the bridge:setup-relay-provider-template skill to wire claude-project-template to your relay provider."

## Purpose

`relay` (darkstar1227/relay) manages *which* LiteLLM gateway a Claude Code session talks to (`base_url`/`auth_token`, optionally a pinned `model`/`discover_models`). `claude-project-template` (cancerfreebiotech/claude-profile-kit) is a `.claude/` scaffold — one orchestrator + 7 subagents (`explorer`, `security-review`, `ui-designer`, `tech-writer`, `executor`, `verifier`, `summarizer`) + a native `advisorModel` — where each role pins its own model via YAML frontmatter.

These two are designed to compose, not overlap: relay owns the connection, the template owns per-role model choice. This skill's whole job is closing the gap between them — read the *actual* models the already-configured relay provider's gateway exposes, then write that into the template's files, so the user never opens `.claude/agents/*.md` or `.claude/settings.json` by hand.

**Hard constraint carried over from both projects' own docs:** never write, export, or otherwise cause `CLAUDE_CODE_SUBAGENT_MODEL` to be set anywhere in this flow — the template's README documents that when set, it clobbers every subagent's `model:` frontmatter, which defeats the entire point of this skill. Concretely this means: never pass `--subagent-model` to `relay provider add`, and check the target provider doesn't already have one set (Step 1).

## Step 1 — Resolve the relay provider

1. If the user named a provider, use it. Otherwise run `relay provider list` and, if there's exactly one, use it; if there are several, ask which one (plain text — a name is enough, don't over-format this as a menu).
2. Read that provider's config directly (mirrors relay's own `_provider_field` helper — see `relay:107-127` in the relay repo if you need to check the exact convention):
   ```bash
   PROVIDER_FILE="${HOME}/.claude-relay/providers/<name>.json"
   python3 -c 'import json; d=json.load(open("'"${PROVIDER_FILE}"'")); print(json.dumps(d))'
   ```
3. If `subagent_model` is present and non-empty in that file, stop and tell the user: this provider has `--subagent-model` set, which will override every role's model once you `relay run` it — the template's per-role assignment would be silently ignored. Ask them to `relay provider remove <name> && relay provider add <name> --base-url ... --token ... --discover-models` (no `--model`, no `--subagent-model`) before continuing, then re-run this skill.
4. Extract `base_url` and `auth_token`. These never get echoed to the user or written into any file this skill produces — they stay exactly where relay already keeps them (relay injects them at `relay run` time via its own generated settings file).

## Step 2 — Query the gateway for real model aliases

Don't guess model names — ask the gateway relay is already pointed at, the same way Claude Code's own `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` does:

```bash
curl -sS "${base_url%/}/v1/models" -H "Authorization: Bearer ${auth_token}"
```

LiteLLM-compatible gateways return `{"data": [{"id": "claude-proxy-opus", ...}, ...]}`. Extract the `id` list. If the endpoint 404s, try `${base_url%/}/model/info` (LiteLLM's native listing) before giving up and asking the user to paste their gateway's model list manually.

Keep only ids that look usable as Claude Code model aliases — Claude Code's discovery only recognizes names starting with `claude` or `anthropic` (documented in the template's own README), so filter to those and separately warn about any other ids on the gateway that won't work here.

## Step 3 — Copy the template into the current project

```bash
TMPDIR=$(mktemp -d)
git clone --depth 1 https://github.com/cancerfreebiotech/claude-profile-kit "${TMPDIR}/kit"
cp -r "${TMPDIR}/kit/templates/claude-project-template/.claude" ./.claude
cp "${TMPDIR}/kit/templates/claude-project-template/CLAUDE.md" ./CLAUDE.md   # only if ./CLAUDE.md doesn't already exist — see below
rm -rf "${TMPDIR}"
```

If `./CLAUDE.md` already exists, do NOT overwrite it — tell the user the template's `CLAUDE.md` content is available at the cloned path structure (dev principles / git conventions / risk-operation rules) and ask whether to merge manually or skip. Never silently clobber an existing project doc.

Do not create `.claude/settings.local.json` — Step 5 explains why it's unnecessary in this flow.

## Step 4 — Assign a model per role

Match the 7 roles + advisor against the filtered model list from Step 2 by tier, using name signals in the alias (`opus`/`gpt-5`/big → heavy tier; `haiku`/`mini`/`flash` → light tier; anything else → mid/default tier):

| Role | Default tier | Why |
|---|---|---|
| advisor (`advisorModel`) | heaviest available | strategic/high-level judgment |
| security-review | heaviest available | mistakes here are expensive |
| verifier | heaviest available | independent judgment call, no do-over |
| explorer | mid/default | breadth over depth |
| executor | mid/default | general-purpose implementation |
| ui-designer | mid/default | visual judgment, not deep reasoning |
| tech-writer | light | mechanical writing task |
| summarizer | light | condensing, not deciding |

If the gateway only exposes one or two distinct aliases, collapse tiers accordingly rather than forcing a 3-way split — never invent an alias that isn't in Step 2's list.

State the full role → model mapping to the user as a plain list before writing anything, and give them one chance to redirect ("swap X and Y", "put everything on the heavy tier") before proceeding — don't silently commit to the heuristic if they want to adjust it.

## Step 5 — Write the files

1. `.claude/settings.json` — set `"model"` to the default/mid-tier alias and `"advisorModel"` to the heavy-tier alias from Step 4. Leave `env` as `{}` — relay's own `relay run <name>` (or `relay provider use <name>`) injects `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` at launch time; baking a base_url into this file would fight relay's own env-injection precedence and drift out of sync the next time the provider's `base_url` changes.
2. Each `.claude/agents/*.md` — update the `model:` frontmatter key to the role's assigned alias from Step 4 (Edit tool, frontmatter block only, leave the rest of the agent prompt untouched).
3. Do not touch `env.ANTHROPIC_MODEL` / `CLAUDE_CODE_SUBAGENT_MODEL` anywhere — those are exactly the two keys that must stay unset for per-role assignment to hold (see Purpose section's hard constraint).

## Step 6 — Report and next steps

Tell the user, concisely:
- The role → model mapping that was written (table, from Step 4).
- That `.claude/agents/` is newly created and Claude Code only loads it on a fresh session start — an already-running session won't pick it up.
- The command to launch: `relay run <provider-name>` (or `relay provider use <provider-name>` then plain `claude`, if they prefer the persistent-switch flow over the one-off `run` flow). `relay run <name>` already execs `claude` itself — don't append a trailing `-- claude`, that would pass the literal string `claude` as one of `claude`'s own CLI args.
- A one-line reminder: don't add `--subagent-model` to this provider later, or the per-role mapping just written becomes dead weight.

Do not implement any application code as part of this skill — it only wires template + provider config together.
