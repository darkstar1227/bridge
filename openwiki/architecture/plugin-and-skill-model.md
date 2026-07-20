---
type: Plugin Architecture
title: Plugin and skill model
description: "How Bridge is packaged and executed as a Claude Code plugin, including skill discovery, prompt contracts, helper-script boundaries, and safe change practices."
resource: .claude-plugin/plugin.json
tags: [architecture, claude-code, skills, authoring]
---

# Plugin and skill model

## Architecture in one sentence

Bridge is a declarative Claude Code plugin: its manifest identifies the package, and most operational behavior is authored as independently discoverable `SKILL.md` prompts rather than as a persistent application runtime.

The package metadata in [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json) supplies the plugin name, version, description, author, license, and keywords. Claude Code discovers `skills/<skill-name>/SKILL.md` directories without a central registration file, as documented in [`CLAUDE.md`](../../CLAUDE.md). This model **provides the operational interface for** [planning and pipeline workflows](../workflows/planning-and-pipelines.md), [project/email/environment operations](../operations/project-email-and-environment.md), and [OpenCode delegation and evaluation](../opencode/delegation-and-evaluation.md).

## What a skill owns

Each skill is a full workflow contract. Its YAML front matter names the skill, describes when it should be invoked, lists natural-language triggers, and restricts `allowed-tools`. Its body then specifies the ordered procedure, input discovery, decision points, output paths, error handling, and stop conditions.

For example:

- [`skills/gstack-to-plan/SKILL.md`](../../skills/gstack-to-plan/SKILL.md) translates a reviewed plan into a handoff document and invokes the next planning skill.
- [`skills/full-pipeline/SKILL.md`](../../skills/full-pipeline/SKILL.md) is deliberately a sequencer: it must not replace named downstream skills or make interactive decisions itself.
- [`skills/send-update-email/SKILL.md`](../../skills/send-update-email/SKILL.md) describes an external side effect in detail, including preview, confirmation, MCP delivery, and persistence ordering.

The important design consequence: changing prose can change runtime behavior. Treat prompt edits with the same care as code changes.

## Conventions that preserve reliable behavior

`CLAUDE.md` establishes the shared authoring rules:

- Declare only the tools a skill needs in `allowed-tools`.
- State an output path whenever a skill creates an artifact.
- Mark uncertainty as `[ASSUMPTION: ...]`; do not silently fabricate missing domain details.
- For large log processing, use context-mode first and bring only derived findings into the conversation. If those findings identify target-repository source, use codegraph (initializing or syncing it when needed) rather than broad source scans.
- Use `uv` and `uv run` for Python helpers; do not use bare `python` or `pip install`.

These conventions **govern the specifications passed through** [planning and pipeline workflows](../workflows/planning-and-pipelines.md) and **supply setup and safety instructions to** [OpenCode delegation and evaluation](../opencode/delegation-and-evaluation.md).

## Prompt boundary versus code boundary

Most skills are prompt-only. The main imperative exception is the OpenCode subsystem:

- `skills/opencode-bridge/SKILL.md` manages interactive configuration, permissions, process invocation, and result handling.
- `skills/opencode-bridge/scripts/dispatch.py` implements repeatable state handling, JSON-stream classification, process-group timeouts, retry/fallback decisions, and structured handoff reports.
- Benchmark/check scripts reuse that dispatch behavior for disposable-repository tests.

This is a deliberate split: prompt logic asks humans for values and chooses workflow context; the helper makes concurrency, timeout, and mutation behavior less dependent on conversational interpretation. See [OpenCode delegation and evaluation](../opencode/delegation-and-evaluation.md) for the lifecycle and test surface.

## Adding or changing a skill

1. Read the closest existing skill and `CLAUDE.md`; create `skills/<name>/SKILL.md` with valid plugin front matter.
2. Specify triggers, tool permissions, inputs, output locations, and explicit behavior for missing prerequisites or user approval.
3. Reuse a shared workflow only when the boundary is real. If two skills intentionally share core behavior, state the synchronization requirement in both prompts (the email pair does this).
4. Add or update helper tests when changing imperative scripts. For the dispatcher, run from `skills/opencode-bridge/scripts/`:
   ```bash
   uv run pytest tests/test_dispatch.py -v
   ```
5. Bump the semantic version in `.claude-plugin/plugin.json` for a plugin release, then make README changes when the user-facing surface changes.

## Source references

- Plugin/package: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Contributor rules and shared outputs: `CLAUDE.md`
- User-facing installation and selected usage: `README.md`
- Behavior definitions: `skills/*/SKILL.md`
