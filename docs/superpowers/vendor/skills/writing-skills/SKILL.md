---
name: writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
---

# Writing Skills

## Overview

**Writing skills IS Test-Driven Development applied to process documentation.**

Personal skills live in your runtime's skills directory (`~/.claude/skills/`
on Claude Code — see `../using-superpowers/references/` for other runtimes;
Codex, Copilot CLI, and Gemini CLI also recognize `~/.agents/skills/`).

You write test cases (pressure scenarios with subagents), watch them fail
(baseline behavior), write the skill (documentation), watch tests pass
(agents comply), and refactor (close loopholes).

**Core principle:** If you didn't watch an agent fail without the skill, you
don't know if the skill teaches the right thing.

**REQUIRED BACKGROUND:** You MUST understand superpowers:test-driven-development
before using this skill — it defines the RED-GREEN-REFACTOR cycle this skill
adapts to documentation.

**Official guidance:** For Anthropic's official skill authoring best
practices, see anthropic-best-practices.md — complements the TDD-focused
approach here.

## What is a Skill?

A **skill** is a reference guide for proven techniques, patterns, or tools —
not a narrative about how you solved a problem once.

## TDD Mapping for Skills

| TDD Concept | Skill Creation |
|-------------|----------------|
| Test case | Pressure scenario with subagent |
| Production code | Skill document (SKILL.md) |
| Test fails (RED) | Agent violates rule without skill (baseline) |
| Test passes (GREEN) | Agent complies with skill present |
| Refactor | Close loopholes while maintaining compliance |

Run the baseline scenario, document the exact rationalizations used, write
the skill to address those specific violations, verify compliance, then find
new rationalizations and repeat.

## When to Create a Skill

**Create when:** the technique wasn't intuitively obvious to you, you'd
reference it again across projects, the pattern applies broadly, or others
would benefit.

**Don't create for:** one-off solutions, standard practices well-documented
elsewhere, project-specific conventions (put in your instructions file), or
mechanical constraints (if it's enforceable with regex/validation, automate
it — save documentation for judgment calls).

## Skill Types

- **Technique** — concrete method with steps (condition-based-waiting, root-cause-tracing)
- **Pattern** — way of thinking about problems (flatten-with-flags, test-invariants)
- **Reference** — API docs, syntax guides, tool documentation

## Directory Structure

```
skills/
  skill-name/
    SKILL.md              # Main reference (required)
    supporting-file.*     # Only if needed
```

Flat namespace — all skills in one searchable namespace. Separate files only
for heavy reference (100+ lines) or reusable tools (scripts, templates).
Keep principles, concepts, and code patterns under 50 lines inline.

## SKILL.md Structure

Frontmatter needs `name` (letters/numbers/hyphens only) and `description`
(third-person, max 1024 chars total). Template:

```markdown
---
name: Skill-Name-With-Hyphens
description: Use when [specific triggering conditions and symptoms]
---

# Skill Name

## Overview
What is this? Core principle in 1-2 sentences.

## When to Use
[Small inline flowchart IF decision non-obvious]
Bullet list with SYMPTOMS and use cases; when NOT to use

## Core Pattern (for techniques/patterns)
Before/after code comparison

## Quick Reference
Table or bullets for scanning common operations

## Implementation
Inline code for simple patterns; link to file for heavy reference

## Common Mistakes
What goes wrong + fixes
```

## Skill Discovery Optimization (SDO)

Future agents find your skill by reading its description, so make every word count.

**Description = when to use, never what the skill does.** Start with "Use
when..." and describe only triggering conditions — never summarize the
workflow. A description that summarizes process gives agents a shortcut to
follow instead of reading the skill body: testing showed a description
mentioning "code review between tasks" made an agent do ONE review, even
though the skill's actual process had two stages. Rewritten to just "Use
when executing implementation plans with independent tasks" (no workflow
summary), the agent read the full process and did both.

```yaml
# ❌ Summarizes workflow — agents may follow this instead of reading the skill
description: Use when executing plans - dispatches subagent per task with code review between tasks
# ✅ Triggering conditions only
description: Use when executing implementation plans with independent tasks in the current session
```

Describe the *problem* (race conditions, inconsistent behavior), not
language-specific symptoms (setTimeout, sleep) — unless the skill itself is
technology-specific, in which case say so explicitly. Write in third person.

**Keyword coverage:** use words an agent would search for — error messages
("Hook timed out", "ENOTEMPTY"), symptoms ("flaky", "hanging", "zombie"),
synonyms ("timeout/hang/freeze"), actual tool/library/command names.

**Naming:** active voice, verb-first, named by what you DO or the core
insight — `condition-based-waiting` not `async-test-helpers`,
`root-cause-tracing` not `debugging-techniques`. Gerunds work well for
processes: `creating-skills`, `debugging-with-logs`.

**Token efficiency is critical** — getting-started and frequently-referenced
skills load into every conversation. Target: getting-started workflows <150
words, frequently-loaded skills <200 words total, others <500 words.
Techniques: point to `--help` instead of documenting every flag inline;
cross-reference other skills instead of repeating their instructions; use
one compressed example instead of a verbose one; don't repeat what a
cross-referenced skill already says. Check with `wc -w skills/path/SKILL.md`.

**Cross-referencing:** use skill name with an explicit requirement marker —
`**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development` — never a
bare file path and never an `@`-link (force-loads the file immediately,
burning context before it's needed).

## Flowchart Usage

Use a small inline flowchart only for a non-obvious decision point, a
process loop where an agent might stop too early, or an "A vs B" choice.
Never use one for reference material (use tables/lists), code examples (use
markdown blocks), linear instructions (use numbered lists), or labels
without semantic meaning (`step1`, `helper2`). See
`graphviz-conventions.dot` for style rules, and `render-graphs.js` to render
a skill's flowcharts to SVG for review (`./render-graphs.js ../some-skill`).

## Code Examples

One excellent example beats many mediocre ones. Choose the most relevant
language for the domain (TypeScript/JS for testing, Shell/Python for system
debugging). A good example is complete, runnable, comments WHY not what,
comes from a real scenario, and is ready to adapt — not a fill-in-the-blank
template. Don't implement the same example in 5+ languages; you're good at
porting, one great example is enough.

## File Organization

Self-contained (`SKILL.md` only) when everything fits inline. Add a
reusable-tool file (e.g. `example.ts`) when the tool is working code, not
narrative. Add heavy-reference files (API docs, XML structure, `scripts/`)
only when reference material is too large for inline.

## The Iron Law (Same as TDD)

**NO SKILL WITHOUT A FAILING TEST FIRST** — applies to new skills AND edits
to existing skills. Write or edit a skill before testing it? Delete the
change, start over. No exceptions for "simple additions," "just adding a
section," or "documentation updates" — don't keep untested changes as
"reference" or adapt them while running tests.

## Testing All Skill Types

Different skill types need different test approaches:

- **Discipline-enforcing** (TDD, verification-before-completion): test with
  academic questions (do they understand the rule?), pressure scenarios (do
  they comply under stress?), and combined pressures (time + sunk cost +
  exhaustion). Success = the agent follows the rule under maximum pressure.
- **Technique** (condition-based-waiting, root-cause-tracing): test
  application scenarios, variations, and gaps in the instructions. Success =
  the agent applies the technique correctly to a new scenario.
- **Pattern** (reducing-complexity): test recognition (do they see when it
  applies?), application, and counter-examples (do they know when NOT to
  apply it?). Success = correct identification of when/how to apply it.
- **Reference** (API docs): test retrieval and application, and check common
  use cases are covered. Success = the agent finds and correctly applies the
  information.

Skipping testing because it "seems clear," "is just a reference," or "no
time" always costs more later — untested skills reliably have issues, and
fixing one in production costs more than the ~15 minutes testing would have
taken.

## Match the Form to the Failure

Classify the baseline failure before writing guidance — the form that
bulletproofs one failure type measurably backfires on another.

| Baseline failure | Right form | Wrong form |
|---|---|---|
| Skips/violates a rule under pressure | Prohibition + rationalization table + red flags | Soft guidance ("prefer...", "consider...") |
| Complies, but wrong-shaped output | Positive recipe: state what the output IS, its parts, in order | Prohibition list ("don't restate", "never narrate") |
| Omits a required element | Structural: REQUIRED field/slot in the template | Prose reminders near the template |
| Behavior should depend on a condition | Conditional on an observable predicate | Unconditional rule + exemption clauses |

Prohibitions invite negotiation under a competing incentive — in wording
tests, a prohibition arm produced more of the unwanted content than a recipe
arm, and trended worse than no guidance at all. A recipe leaves nothing to
negotiate. Whichever form you pick: no nuance clauses ("don't X unless it
matters" reopens the negotiation — make real exceptions their own
conditional), and exemption clauses don't actually scope the rule — if part
of the output must be exempt, restructure so the rule can't reach it.

## Bulletproofing Discipline Skills Against Rationalization

Scope: this is for discipline failures only — an agent that knows the rule
and skips it under pressure. For wrong-shaped output, use the forms above
instead.

- **Close every loophole explicitly.** Don't just state the rule ("Write
  code before test? Delete it.") — forbid the workarounds too: don't keep it
  as "reference," don't adapt it while writing tests, don't look at it.
  Delete means delete.
- **Address spirit-vs-letter arguments up front**: "Violating the letter of
  the rules is violating the spirit of the rules" cuts off an entire class
  of rationalization before it starts.
- **Build a rationalization table** from baseline testing — every excuse an
  agent makes goes in as an "Excuse | Reality" row.
- **Create a red flags list** — the exact rationalizing thoughts that mean
  "stop and start over," so an agent can self-check mid-task.
- **Update the description** with symptoms of being about to violate the
  rule, not just the rule itself.

Understanding WHY these techniques work (authority, commitment, scarcity,
social proof, unity) helps apply them systematically — see
persuasion-principles.md for the research foundation.

## RED-GREEN-REFACTOR for Skills

**RED:** run the pressure scenario with a subagent WITHOUT the skill.
Document verbatim what choices it made, what rationalizations it used, which
pressures triggered violations — you must see the natural failure before
writing the fix.

**GREEN:** write the minimal skill addressing those specific
rationalizations (no content for hypothetical cases), then re-run the same
scenarios and confirm compliance.

**REFACTOR:** when an agent finds a new rationalization, add an explicit
counter and re-test until bulletproof.

**Micro-test wording before full scenarios** — full pressure runs are the
final gate but slow per iteration. First: one fresh-context sample per call
(system prompt = the realistic surrounding context, not the guidance alone;
user message = a task that tempts the failure); always include a
no-guidance control (if it doesn't fail, there's nothing to fix); 5+ reps
per variant (single samples lie); read every flagged match manually
(automated counts overstate both failure and success); treat variance
itself as a signal — five different interpretations across five reps means
the wording isn't binding yet. Micro-tests verify wording; they don't
replace pressure scenarios for discipline skills. Full methodology
(pressure types, plugging holes, meta-testing) is in
[testing-skills-with-subagents.md](testing-skills-with-subagents.md).

## Anti-Patterns

Narrative examples ("In session 2025-10-03, we found...") are too specific
to reuse. Multi-language dilution (`example-js.js`, `example-py.py`, ...) is
mediocre quality with a maintenance burden. Code inside flowchart nodes
can't be copy-pasted and is hard to read. Generic labels (`helper1`,
`step3`) carry no semantic meaning — name for what the thing does.

## Deployment Discipline

After writing any skill, stop and complete the deployment process below
before moving to the next one — don't batch multiple untested skills, and
don't skip testing because "batching is more efficient." Deploying an
untested skill is deploying untested code.

## Skill Creation Checklist (TDD Adapted)

Create a todo for each item.

**RED — write failing test:**
- [ ] Create pressure scenarios (3+ combined pressures for discipline skills)
- [ ] Run scenarios WITHOUT the skill — document baseline behavior verbatim
- [ ] Identify patterns in rationalizations/failures

**GREEN — write minimal skill:**
- [ ] Name uses only letters, numbers, hyphens
- [ ] YAML frontmatter with `name` and `description` (max 1024 chars)
- [ ] Description starts with "Use when...", third person, specific triggers
- [ ] Keywords throughout for search
- [ ] Clear overview with core principle
- [ ] Addresses the specific baseline failures from RED
- [ ] Guidance form matches the failure type (Match the Form to the Failure)
- [ ] Behavior-shaping wording micro-tested against a no-guidance control (N/A for pure reference skills)
- [ ] Code inline, or linked to a separate file
- [ ] One excellent example, not multi-language
- [ ] Run scenarios WITH the skill — verify compliance

**REFACTOR — close loopholes:**
- [ ] Identify new rationalizations from testing
- [ ] Add explicit counters (discipline skills)
- [ ] Build the rationalization table from all test iterations
- [ ] Create the red flags list
- [ ] Re-test until bulletproof

**Quality checks:**
- [ ] Flowchart only if the decision is genuinely non-obvious
- [ ] Quick reference table
- [ ] Common mistakes section
- [ ] No narrative storytelling
- [ ] Supporting files only for tools or heavy reference

**Deployment:**
- [ ] Commit skill to git and push
- [ ] Consider contributing back via PR if broadly useful

## Discovery Workflow

Future agents find a skill by: hitting the problem → searching skills
(descriptions, categories) → matching description → scanning the overview →
reading the quick-reference table → loading the example only when
implementing. Optimize for this path — put searchable terms early and often.
