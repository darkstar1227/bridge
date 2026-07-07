# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code plugin that bridges gstack-reviewed plans into Superpowers `writing-plans` format. No build step, no runtime — pure skill definitions and plugin metadata.

## Plugin structure

```
.claude-plugin/plugin.json   — plugin manifest (name, version, description)
skills/<skill-name>/SKILL.md — one skill per directory; SKILL.md is the full skill prompt
README.md                    — user-facing install and usage docs
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
