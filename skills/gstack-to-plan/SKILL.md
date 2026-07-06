---
name: gstack-to-plan
description: Bridge a gstack-reviewed plan into a Superpowers writing-plans implementation plan. Reads the latest approved gstack plan, transforms it into a Superpowers-compatible spec, then invokes superpowers:writing-plans.
triggers:
  - bridge plan
  - gstack to plan
  - convert gstack plan
  - handoff to superpowers
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Bridge: gstack Plan → Superpowers writing-plans

**Announce at start:** "I'm using the bridge:gstack-to-plan skill to transform the gstack plan into a Superpowers implementation plan."

## Purpose

gstack produces strategic, reviewed plans (CEO / design / eng / DX reviewed). Superpowers `writing-plans` needs an execution-level spec: exact files, bite-sized tasks, test commands, verification steps. This skill bridges the gap.

## Step 1 — Locate the Source Plan

Search in this priority order:

1. File path provided as args (if the user specified one)
2. `docs/plan.md`
3. `docs/spec.md`
4. `plan.md`
5. `spec.md`
6. Any `.md` under `docs/` modified most recently (`ls -t docs/*.md 2>/dev/null | head -1`)
7. Any `.md` under `.gstack/` (`ls -t .gstack/**/*.md 2>/dev/null | head -1`)

Read the located file in full. If nothing is found, stop and ask the user to specify the plan file path.

## Step 2 — Extract Structured Information

Parse the plan and extract:

| Field | Where to look |
|-------|--------------|
| **Goal / problem statement** | Title, intro, executive summary |
| **Success metrics** | Acceptance criteria, success criteria, definition of done |
| **In-scope work** | Scope, features, deliverables |
| **Out-of-scope** | Non-goals, explicitly excluded items |
| **User / workflow** | Target user, use cases, user flows |
| **Technical constraints** | Tech stack, language, framework, APIs, infra limits |
| **Architecture decisions** | Architecture, design decisions, patterns, data models |
| **Open risks / assumptions** | Open questions, risks, assumptions, unknowns |
| **Implementation hints** | Any code-level notes, file mentions, libraries |

If a field is absent, mark it `[ASSUMPTION: ...]` and fill conservatively.

## Step 3 — Readiness Check

Before continuing, verify the extracted content contains ALL of:

- [ ] A clear problem statement (not just a feature name)
- [ ] Explicit scope boundaries (what IS and IS NOT included)
- [ ] At least one technical constraint (language, framework, or platform)
- [ ] At least one verification method (how to know it works)

If any item is missing, write the gap as an explicit assumption. Do not silently fill gaps.

## Step 4 — Write the Handoff Document

Save to: `docs/superpowers/input/gstack-handoff-YYYY-MM-DD-<feature-slug>.md`

Use today's date. Derive `<feature-slug>` from the plan title (lowercase, hyphens, no spaces).

The handoff document MUST follow this template exactly:

```markdown
# Gstack Handoff: <Feature Name>

_Source plan: <path to source file>_
_Bridged: <today's date>_

## Overview

<2-4 sentences: what this builds and why>

## Goal

<The core problem being solved, in one sentence>

## Success Metrics

<Bulleted list of acceptance criteria>

## Scope

<Bulleted list of what IS included>

## Non-Goals

<Bulleted list of what is NOT included>

## Technical Constraints

<Bulleted list: language, framework, platform, APIs, limits>

## Architecture Decisions

<Key decisions already made that the implementer must respect>

## File Structure Assumptions

<List of files expected to be created or modified, with one-line purpose each.
If the source plan is silent on this, derive from the architecture section.
Mark each line with [EXISTING] or [NEW]>

## Proposed Implementation Areas

<Group work into 2-5 logical areas. For each area:
- Name
- What it does
- Why it's a separate concern>

## Verification Expectations

<How to test/verify the feature works. Specific commands if known.>

## Open Questions / Explicit Assumptions

<List every gap filled by assumption. Format:
- [ASSUMPTION] <what was assumed> — <why this assumption was made>
- [OPEN] <unresolved question that the implementer must decide>>
```

## Step 5 — Invoke Superpowers writing-plans

After saving the handoff document, invoke:

```
superpowers:writing-plans
```

Tell it: "Use `docs/superpowers/input/<handoff-filename>` as the source spec."

Do NOT implement any code. Stop after the Superpowers plan is written.

## Transformation Rules

Apply these rules when converting gstack → handoff:

1. **Vague → concrete**: "improve performance" → "reduce p95 latency of `/api/search` below 200ms"
2. **Strategy → files**: "add caching layer" → "create `src/cache/redis-client.ts`"
3. **2-5 min granularity**: each implementation area should decompose into steps that take 2-5 minutes each when writing-plans runs
4. **No silent assumptions**: every guess must appear in the "Open Questions / Explicit Assumptions" section
5. **Verification first**: every area needs at least one verifiable output, not just "feature works"
