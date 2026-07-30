Source: https://github.com/obra/superpowers
44c9b2d6e889982ac18c27d05a19fefe335194e1
cloned 2026-07-30T07:08:05Z

## Simplification pass (2026-07-30)

All 14 SKILL.md files condensed to cut context/token cost: removed
duplicate ASCII flowcharts that restated adjacent prose, illustrative
"Example Workflow"/"Real Example" sections, and repetitive
rationalization/red-flag tables — while keeping every operational rule,
template, checklist, and code example load-bearing to executing the skill.

Deleted entirely (dev/eval artifacts, not runtime content):
- `brainstorming/visual-companion.md` + `brainstorming/scripts/` (browser
  mockup companion — out of scope for this plugin's pipeline skills)
- `systematic-debugging/CREATION-LOG.md`,
  `systematic-debugging/test-academic.md`,
  `systematic-debugging/test-pressure-{1,2,3}.md` (skill-authoring eval
  scenarios, not needed to use the skill)

Untouched: `anthropic-best-practices.md` (Anthropic's official docs, only
loaded on demand), `persuasion-principles.md`,
`testing-skills-with-subagents.md`, and the per-platform reference files
under `using-superpowers/references/` — all lazy-loaded reference material
with no steady-state cost.

SKILL.md total: 3185 → 2273 lines. Vendor directory: 540K → 408K.
