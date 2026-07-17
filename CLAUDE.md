# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code plugin that bundles three unrelated skill families under one `bridge` namespace: gstack-plan → Superpowers `writing-plans` bridging, Resend-based repo update-email digests, and pipeline log review against a design doc. No build step, no runtime — pure skill definitions and plugin metadata.

## Plugin structure

```
.claude-plugin/plugin.json      — plugin manifest (name, version, description)
.claude-plugin/marketplace.json — local marketplace descriptor, used to install/test this plugin from a GitHub URL or local path
skills/<skill-name>/SKILL.md    — one skill per directory; SKILL.md is the full skill prompt
README.md                       — user-facing install and usage docs
```

Claude Code reads `skills/*/SKILL.md` automatically when the plugin is installed. The frontmatter (`---` block) controls `name`, `description`, `triggers`, and `allowed-tools`.

## Adding a new skill

1. Create `skills/<skill-name>/SKILL.md` with a YAML frontmatter block followed by the skill instructions.
2. No registration needed — Claude Code discovers skills by directory structure.
3. Bump `version` in `.claude-plugin/plugin.json` (semver).

## Python scripts

If any helper scripts are added, use `uv` for package management and `uv run` to execute them. Never use `pip install` or bare `python`.

```bash
uv add <package>
uv run script.py
```

## Skill authoring conventions

- `allowed-tools` in frontmatter restricts which Claude tools the skill may use.
- `triggers` lists natural-language phrases that should auto-invoke the skill.
- Skills must **not** implement code themselves — they instruct Claude how to act.
- Every skill that produces files must specify the output path (e.g. `docs/superpowers/input/`).
- Explicit `[ASSUMPTION: ...]` markers are preferred over silent gap-filling.

## Known output paths and shared config

- `docs/superpowers/{plans,specs}/` — gstack-to-plan handoff files
- `docs/pipeline-reviews/` — review-pipeline-logs reports
- `docs/autoresearch/plan/` — autoresearch-plan comparison logs (candidate approaches, metric, winner)
- `docs/autoresearch/impl/` — autoresearch-impl iteration logs (round-by-round variant/metric/keep-or-discard)
- `docs/opencode-model-tests/` — reports shared by `benchmark-opencode-models` (deep per-prompt time/quality/completeness/autonomy/discipline/TDD-discipline scores) and `check-opencode-models` (fast ping-only availability reports)
- `.bridge/email-config.json` (per target repo) — recipients, last-sent tracking, and Resend MCP connection; shared by `setup-email-updates`, `send-update-email`, and `send-update-email-batch`
