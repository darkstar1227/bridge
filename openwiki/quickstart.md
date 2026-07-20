---
type: Repository Guide
title: Bridge plugin quickstart
description: "Entry point for the Bridge Claude Code plugin: its skill-based architecture, workflow families, OpenCode tooling, and safe ways to extend or validate it."
resource: README.md
tags: [claude-code, plugin, skills, workflows]
---

# Bridge plugin quickstart

## What this repository is

Bridge is a Claude Code plugin that packages workflow skills under the `bridge` namespace. It began as a bridge from gstack-reviewed plans to Superpowers execution plans, and now also covers project setup, environment portability, update emails, pipeline review, autoresearch, OpenCode delegation, and OpenCode model checks. The plugin manifest is [`.claude-plugin/plugin.json`](../.claude-plugin/plugin.json); it currently identifies the package as `bridge` and supplies its marketplace metadata.

This is not a conventional service or app: most behavior is declarative instruction in `skills/<name>/SKILL.md`, which Claude Code discovers when the plugin is installed. The repository’s canonical implementation model and change rules live in [the plugin and skill model](architecture/plugin-and-skill-model.md).

## Start here by intent

- **Create an implementation plan from a reviewed idea:** use [planning and pipeline workflows](workflows/planning-and-pipelines.md). The `gstack-to-plan` skill converts strategic review into a structured handoff and invokes Superpowers planning.
- **Run an end-to-end or lean development flow:** use [planning and pipeline workflows](workflows/planning-and-pipelines.md). The orchestrators sequence external skills, retain interactive decisions, and conditionally run Supabase guidance for schema work.
- **Standardize a target repository, configure update digests, or transfer a user-scope Claude setup:** use [project, email, and environment operations](operations/project-email-and-environment.md).
- **Delegate an implementation task to OpenCode or decide which models are usable:** use [OpenCode delegation and evaluation](opencode/delegation-and-evaluation.md). It explains the helper script’s retry and mutation safeguards as well as the fast and deep model checks.

## Repository map

| Area | Primary sources | Why it matters |
| --- | --- | --- |
| Plugin metadata | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Defines package identity and marketplace installation metadata. |
| Skill prompts | `skills/*/SKILL.md` | The main runtime behavior, triggers, tool permissions, safeguards, and output contracts. |
| OpenCode helpers | `skills/opencode-bridge/scripts/`, benchmark/check scripts | The imperative code used for guarded dispatch and repeatable model testing. |
| Example and durable artifacts | `docs/` | Design plans, handoffs, pipeline reviews, environment manifests, and model-test reports. |
| Repository conventions | `CLAUDE.md`, `README.md` | Contributor rules, output locations, and user-facing installation/usage context. |

## Working with the plugin

1. Read the relevant `SKILL.md` before changing a workflow. A skill’s YAML front matter declares its name, triggers, and `allowed-tools`; its body is the behavior contract.
2. Keep prompts explicit about output paths, user decisions, and assumptions. `CLAUDE.md` calls for `[ASSUMPTION: ...]` rather than silent gap filling.
3. Keep paired behavior synchronized. In particular, `send-update-email` and `send-update-email-batch` intentionally share gathering, filtering, grouping, template, and state-update rules; confirmation and parent-folder iteration are the intended differences.
4. Use `uv` for Python helper scripts. The OpenCode dispatcher has its own test suite under `skills/opencode-bridge/scripts/tests/`.
5. Treat uncommitted source changes as user work. At documentation initialization, `CLAUDE.md` and `skills/benchmark-opencode-models/scripts/smoke_test.py` were modified; this wiki does not reinterpret those edits as released behavior.

## Important boundaries

- The plugin uses external ecosystems rather than bundling their capabilities: gstack and Superpowers for planning/execution, Resend MCP for sending email, Supabase guidance for relevant schema changes, and the OpenCode CLI for delegated coding.
- The README is a useful user entrypoint but does not enumerate every currently tracked skill. Use the `skills/` tree and the focused pages in this wiki when assessing the current surface.
- Several skills intentionally stop for confirmation or missing information. Orchestrators are sequencers, not substitutes for user decisions or named downstream skills.

## Backlog

- **Skill-by-skill trigger catalog** — source anchor: `skills/*/SKILL.md`; deferred because the initial wiki prioritizes behavioral families over a duplicated inventory.
- **Experimental workspace and raw model-result analysis** — source anchor: `review-pipeline-logs-workspace/` and untracked `docs/opencode-model-tests/`; deferred because these artifacts are evolving and do not define stable plugin architecture.
