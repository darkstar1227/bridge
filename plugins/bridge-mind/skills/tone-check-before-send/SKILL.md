---
name: tone-check-before-send
description: Use before any outward-facing text reaches another person — PR review comments, code review feedback, Slack or email replies, GitHub issue responses, pushback on a colleague's design, or a message written while frustrated. Triggers on phrases like "review this PR", "leave a comment", "reply to this", "send this to", "how does this sound", "draft a response", "push back on this", and on their Traditional Chinese equivalents 「幫我回這個」「這樣回可以嗎」「留個 comment」「寄給他」「這樣講會不會太兇」「回覆一下」. Catches the tertiary-Fe blind spot where technically correct feedback lands far harsher than intended, and rewrites delivery while keeping every technical claim intact.
triggers:
  - review this PR
  - leave a comment
  - reply to this
  - send this to
  - how does this sound
  - draft a response
  - push back on this
  - 幫我回這個
  - 這樣回可以嗎
  - 留個 comment
  - 寄給他
  - 這樣講會不會太兇
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Tone Check Before Send

**Announce at start:** "I'm using the bridge-mind:tone-check-before-send skill to check how this will land before it goes out."

## Core Principle

ESTP's tertiary function is Fe. In the moment, with attention available, it reads a room extremely well.
Under time pressure, frustration, or deep focus on a technical problem, it drops out — and what remains is
Ti's raw correctness with none of the delivery. The message is accurate and lands three times harder than
intended.

The author cannot detect this from the inside. The text reads as merely efficient to the person who wrote
it, because they have full access to the friendly intent behind it. The recipient has only the words.

**This skill is a translation layer, not a politeness lecture.** Every technical claim survives intact,
including the harsh ones. Only delivery changes. Softening a correct objection into vagueness would be a
worse failure than bluntness, and this skill must never do it.

## Output Style — Read This Before Writing Anything

This skill is **fully exempt from any active terseness or compression style (caveman mode or similar)**,
and the exemption matters more here than in any other skill in this series.

The user runs their entire tool chain optimized for compression. That is correct for machine-facing text
and actively harmful for human-facing text — dropped articles and clipped fragments are precisely what
makes a message read as curt or annoyed. A compressed rewrite would reproduce the exact defect this skill
exists to catch.

Write the rewrite in complete, natural sentences. The analysis around it may be brief, but the rewrite
itself must be the finished, sendable text.

## Step 1 — Confirm This Is Outward-Facing

Apply only to text another person will read: PR comments, code review feedback, Slack, email, issue
replies, commit messages on shared branches, documentation others will rely on.

**Skip entirely** for internal notes, local commit messages on personal branches, scratch files, and
anything addressed to Claude. Running a tone check on a private note is friction with no upside, and
friction is what gets a skill disabled.

## Step 2 — Score How It Will Land

Read the draft as the recipient, without access to the author's intent. Check for:

| Signal | What the recipient infers |
|---|---|
| Bare imperatives with no framing ("Change this. Use X.") | The author is issuing orders |
| A correction with no acknowledgment of what worked | The author saw nothing of value in the work |
| "Obviously", "just", "simply", "why would you" | The author thinks the recipient is slow |
| A question that is really a statement ("Did you test this?") | Accusation dressed as inquiry |
| Extreme brevity on a topic the recipient invested effort in | Dismissal, or the author is angry |
| Piling on many objections at once | An attack on the person, not the work |

Report the score in one line: **lands as** *collaborative / neutral / blunt / harsh*, plus the single
strongest contributing signal.

If the verdict is collaborative or neutral, say so and stop. Do not rewrite text that is already fine —
unnecessary rewrites teach the user to skip this skill.

## Step 3 — Rewrite, Preserving Every Technical Claim

Rules for the rewrite:

1. **No technical claim may be dropped, softened, or hedged.** If the code is wrong, the rewrite still says
   it is wrong. "This will drop writes under concurrent access" stays exactly that strong.
2. **Add the missing frame, not filler.** What the author already knew but did not write down: why it
   matters, what the consequence is, what was actually fine. That context is what was lost, not politeness.
3. **Lead with the most important objection**, not all of them. If the draft raises six issues, ask whether
   three are blocking and the rest can wait — a wall of objections reads as an attack regardless of wording.
4. **Convert accusatory questions into observations.** "Did you test this?" becomes "I don't see a test
   covering the concurrent path — was that intentional?"
5. **Keep the author's voice.** Direct is fine. The goal is not to make the user sound like someone else;
   it is to remove the accidental harshness the user did not intend to include.

Present the rewrite as finished, sendable text — never as a bulleted list of suggested improvements. The
user should be able to copy it directly.

## Step 4 — The Frustration Check

If the draft was written while the user was frustrated (repeated failures, a long debugging session, an
argument in the thread), say so plainly and suggest a delay:

> "This reads as written while annoyed. It's accurate. Consider sending it in an hour — nothing here
> expires today."

State this once. If the user sends it anyway, that is their call. Do not raise it a second time.

## Step 5 — Show the Difference, Briefly

Give the before/after only when the change is instructive, and limit it to the single most important line.
A full side-by-side diff of a rewritten paragraph is more reading than the message itself and will be
skipped.

## Relationship to Other Skills in This Series

`system-design-devil-advocate` produces exactly the kind of sharp technical objection this skill exists to
package. When that skill's output is going to be pointed at a person rather than kept as the user's own
analysis, run this one on it before it goes out. The analysis stays; the delivery gets a pass.

## Example

Draft: "This is wrong. The lock doesn't cover the read path. Rewrite it."

Verdict: **lands as harsh** — bare imperative, no acknowledgment, no stated consequence.

Rewrite: "The lock covers the write path but not the read, so a concurrent reader can observe a partial
update — I think that's the source of the flaky test we saw last week. The rest of the refactor looks good
to me; it's specifically the read path that needs to move inside the lock."

Same claim. Same strength. Now it reads as a colleague finding a bug rather than a verdict on the author.
