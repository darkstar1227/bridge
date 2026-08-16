---
name: task-activation
description: Use when the user knows what needs doing but cannot start — task paralysis, procrastination on something they actually want to do, a task that feels like an undifferentiated blob, or repeated circling without beginning. Triggers on phrases like "I can't start", "I don't know where to begin", "I keep putting this off", "this feels overwhelming", "I've been staring at this", "where do I even start", and on their Traditional Chinese equivalents 「動不了」「不知道從哪開始」「一直拖著沒做」「感覺好龐大」「開不了頭」「卡在起點」. Breaks the activation barrier by producing one physically executable first action under two minutes — never another plan, since planning is the most common avoidance behavior.
triggers:
  - I can't start
  - I don't know where to begin
  - I keep putting this off
  - this feels overwhelming
  - where do I even start
  - 動不了
  - 不知道從哪開始
  - 一直拖著沒做
  - 感覺好龐大
  - 開不了頭
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
---

# Task Activation

**Announce at start:** "I'm using the bridge-mind:task-activation skill to find the smallest physical first action."

## Core Principle

Task paralysis is not a knowledge problem. The user already knows what to do — that is what distinguishes it from confusion, and why explaining the task again does nothing. The gap is between knowing and starting, and it does not respond to information.

What it responds to is **an action small enough that starting requires no decision.**

## The Named Anti-Pattern: Producing a Plan

**Making a plan is the single most common way this skill fails.**

A plan feels like progress, is genuinely enjoyable to produce, and leaves the user exactly as unable to start as before — now with the added weight of a document they are not acting on. For someone who is already avoiding, an elaborate plan is avoidance with better production values.

Also disqualified for the same reason: a task breakdown with more than three items, a checklist, an estimate, a list of considerations, a "here's how I'd approach it" overview.

**The deliverable is one physical action.** If the output could be described as a plan, it is wrong.

## Output Style

Output is **exempt from any active terseness or compression style (caveman mode or similar)**, but should be genuinely short here — not because of compression, but because length is itself a barrier when someone cannot start. Complete sentences, very few of them.

If the `i-have-adhd` skill is active, follow its output shaping. Leading with the next action is exactly right for this skill.

## Step 1 — Find the Real First Action

Look at the actual code, not the description of the task. The first action must satisfy all four:

1. **Physical** — a body can do it. Open a file. Type a function signature. Run a command. Not "think about", "decide", "consider", "review", "understand".
2. **Zero decisions** — every choice is already made. "Add a function called `authenticate` that returns `null`" contains no decision. "Add the auth function" contains several.
3. **Under two minutes** — short enough that starting costs less than continuing to avoid.
4. **Specific to this codebase** — a real path, a real function name, a real line. Never a generic template.

| Too big (a decision, not an action) | Right size |
|---|---|
| "Implement authentication" | "Open `src/auth.ts` and add `export async function authenticate(token: string) { return null }`" |
| "Fix the flaky test" | "Run `npm test -- retry.test.ts` and paste me the first failure line" |
| "Refactor the config module" | "Open `config.ts` and cut the `DATABASE_URL` block into a new file `config/db.ts`" |
| "Write the migration" | "Run `supabase migration new add_user_role` — it just makes an empty file" |

Note what the right-hand column has in common: the outcome is guaranteed. Nothing there can fail, be wrong, or require judgment. That is what makes it startable.

## Step 2 — Offer to Do It

**Then offer to perform that first action immediately.**

This is not laziness on the user's part and should never be framed as a concession. The barrier is activation energy, and a file that already exists with a stub in it has a fundamentally different activation cost than an empty intention. Once something exists on disk, the task changes from *starting* to *continuing* — and continuing was never the broken part.

> "Want me to just add that stub now? Then you'd be editing rather than starting."

## Step 3 — Stay for the Second Action Only

After the first action lands, give exactly one more — the immediate next thing, no further.

Do not, at this point, produce the full remaining sequence. Momentum is now doing the work; a roadmap arriving mid-momentum is a fresh wall. If the user asks for the whole plan, give it — but do not volunteer it.

## Step 4 — When Even the First Action Is Too Big

If the user still cannot move, the action was not small enough. Halve it, without comment on the fact that it was halved.

"Open the file" is a legitimate first action. So is "run the command that shows the error." There is no floor below which this becomes silly — the only failure is an action that does not get taken.

## What This Skill Must Never Do

- **Never ask why they have not started.** They do not know, the question implies they should, and it converts a solvable problem into a personal one.
- **Never mention how long it has been sitting.** Not as motivation, not as context, not in passing.
- **Never say "it's easy" or "it's just".** If it were easy from here, the skill would not have triggered. Saying so only establishes that the difficulty is a personal failing.
- **Never produce encouragement in place of an action.** Encouragement without a next step is a pleasant way of leaving someone stuck.

## Boundary vs Other Skills

| Situation | Skill |
|---|---|
| Knows the task, cannot start | **this skill** |
| Lost the thread of what they were doing | `resume-interrupted-work` |
| Too many things open, cannot pick | `unfinished-work-audit` |
| Wants to know whether the approach is right | `rapid-prototype-thinking` |

## Example

User says: 「這個 auth 的東西我拖三天了,動不了」

Don't: break it into phases, estimate it, or ask what is blocking them.

Do: read the codebase, find that `src/auth.ts` does not exist yet, and say —

> "First action: create `src/auth.ts` with one line — `export async function authenticate(token: string) { return null }`. That is the whole step; it does not have to work.
>
> Want me to add it now? Then you are editing a file instead of starting a project."
