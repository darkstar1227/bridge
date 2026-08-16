# bridge-mind

Cognitive-support skill series for an ESTP thinker with ADHD.

Designed around the ESTP cognitive-function stack: Se (extraverted sensing, live in the moment, grab concrete data) → Ti (introverted thinking, fast logical breakdown) → Fe (extraverted feeling) → Ni (introverted intuition, weakest, used last). This ordering means an ESTP thinker naturally acts first and thinks while doing, resists getting stuck in abstract planning, and prefers reasoning backward from empirical results over building a complete theory before executing. Combined with a DevOps/LLM/quant-trading background, the problem these skills solve is: in situations that call for careful planning, long-horizon thinking, or counter-intuitive decisions, structured skills force in the steps an ESTP naturally tends to skip — upfront risk assessment, delayed-gratification-style compound learning, trade-offs that don't pay off immediately.

Fully autonomous, no slash command needed to trigger — Claude loads only each skill's `name` + `description` (~100 tokens) at startup, and only reads the full `SKILL.md` when a request matches that description ("progressive disclosure"). So each skill's `description` is written to be precise enough that it actually fires in the real situations it's meant for. Each one leans into or braces against a specific part of the Se → Ti → Fe → Ni stack: fast empirical validation where Se/Ti strengths shine, structured checklists where Ni (long-horizon planning) is naturally weak.

The series covers two layers. The **decision-support** skills address the ESTP function stack described above. The **executive-function** skills address ADHD: interrupted-state recovery, task initiation, time perception, and distraction handling. They share a plugin because the interventions overlap heavily — novelty-chase, activation energy, and time sense sit in both — and because `unfinished-work-audit` genuinely belongs to both.

Complementary to the [`i-have-adhd`](https://github.com/rmiddle/i-have-adhd) plugin rather than overlapping it: that one shapes how Claude *writes* (lead with the next action, number multi-step work, restate state). These handle *workflow*. Run both.

Three cross-cutting properties apply to every skill here:

- **Bilingual triggering.** Each `description` carries both English and Traditional Chinese phrasings, so a skill fires on 「要部署了」 as reliably as on "about to deploy". A risk check that only recognizes English is a risk check that misses the half of your sentences that aren't.
- **Exempt from compression modes.** Every skill explicitly overrides any active terseness style (caveman mode or similar) for its own output. Compression is right for machine-facing text and wrong here: an ambiguous risk warning is worse than none, a curt tone-check rewrite reproduces the exact defect it exists to catch, and reconstructed context compressed into fragments makes the reader rebuild the connections they are least able to rebuild. Structural compactness (verdict blocks, tables) is kept; grammatical compression is not. `i-have-adhd`'s output shaping is *structuring*, not compression — fully compatible, and followed when active.
- **Say it once, then comply.** No skill repeats a warning already given in the same session, comments on how long something has been sitting, or moralizes. A muted skill protects nothing, and the failure narrative is already well stocked.

## Hooks

Both ship with the plugin and are **non-blocking** — they inject context, never deny a call or stall an unattended `/loop`.

| Hook | Event | What it does |
|---|---|---|
| `risk-brake-guard.sh` | `PreToolUse` (shell tools) | Matches commands against seven irreversible-action classes and asks for `risk-brake-thinking` before proceeding. Deterministic where description-matching is probabilistic. |
| `focus-timer.sh` | `UserPromptSubmit` | Tracks elapsed session time in `.bridge/focus-state.json` (>45 min prompt gap starts a fresh session), nudging **once** at 2h and once at 4h. Never repeats a fired threshold. |

### Codex CLI support

Both hooks run under [Codex CLI](https://github.com/openai/codex) as well as Claude Code. The two runtimes get separate registrations pointing at the **same two scripts** — no duplicated logic:

| File | Runtime | Notes |
|---|---|---|
| `hooks/hooks.json` | Claude Code | `${CLAUDE_PLUGIN_ROOT}`, matcher `Bash` |
| `.codex-plugin/hooks.json` | Codex CLI | `${PLUGIN_ROOT}`, matcher `local_shell\|shell\|shell_command\|exec_command\|Bash\|Shell` |

The scripts read the command from `.tool_input.command`, `.cmd`, or `.CommandLine`, and join it if it arrives as an argv array — Codex's shell tools vary across all of those shapes where Claude Code's `Bash` only ever uses the first.

**Requires codex-cli ≥ 0.141.0.** Earlier builds honor `permissionDecision:"deny"` on `PreToolUse` but ignore `additionalContext`, and these hooks are deliberately non-blocking — so on an older build the risk guard would silently do nothing rather than degrade into blocking.

Installing into Codex is a separate step from installing into Claude Code:

```bash
codex plugin marketplace add https://github.com/darkstar1227/bridge
codex plugin add bridge-mind
```

Also confirm `~/.codex/config.toml` has both flags under `[features]`:

```toml
[features]
hooks = true
plugin_hooks = true
```

#### Hook trust — required, one time

Codex will not run a plugin hook until it has been **reviewed and trusted**, recording a `trusted_hash` under `[hooks.state]` in `~/.codex/config.toml`. Until then the hook is silently skipped — no error, no warning, it simply does not fire.

Trust is granted interactively. Run `codex` (the TUI) once in a project after installing and approve the two `bridge-mind` hooks when prompted. `codex exec` cannot grant trust: a non-interactive run has no one to ask, so it skips untrusted hooks and continues.

To verify the hooks work before granting trust, bypass it for a single invocation:

```bash
codex exec --dangerously-bypass-hook-trust "Reply: OK"
ls .bridge/focus-state.json   # focus-timer.sh ran if this exists
```

Two things worth knowing when testing:

- **Codex runs the installed cache copy**, not the working tree — `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/`. Editing a hook script in the repo has no effect until the plugin is reinstalled, even when the marketplace is a local path.
- Hooks run with the project directory as cwd, so `.bridge/` lands in the right place.

## State files

All under `.bridge/`, all gitignored, all personal rather than shared repo state.

| File | Written by | Purpose |
|---|---|---|
| `decisions.jsonl` | `risk-brake-thinking` | Warning/override/outcome history; calibrates how loudly the skill speaks |
| `focus-state.json` | `focus-timer.sh` | Session start, last seen, thresholds already fired |
| `focus-log.jsonl` | `time-blindness-guard` | Estimate vs. actual, for the personal multiplier |
| `inbox.md` | `distraction-capture` | Parked ideas, reviewed by `unfinished-work-audit` |

---

## Decision support (ESTP)

### `bridge-mind:rapid-prototype-thinking`

For technical evaluations (new APIs, frameworks, K8s configs, cheap-to-reverse architecture options). Replaces theoretical "in theory this should work" answers with the smallest runnable experiment that produces observable proof, converging by elimination instead of expanding every branch at once. Splits from `system-design-devil-advocate` on **cost to reverse**, not topic — cheap to undo lands here, expensive to undo lands there.

**Triggers:** "should I try this", "is this approach viable", "let's do a quick POC", "which option is better", "does this design look right" · 「這樣可行嗎」「快速試試看」「哪個比較好」「這設計對嗎」

### `bridge-mind:risk-brake-thinking`

Checklist before irreversible actions — production deploys, DB migrations, force-pushes, or taking a trading strategy live. Forces reversibility check, worst-case quantification, and a rollback plan before an execution plan, then emits a fixed 5-field verdict block scannable in seconds.

Three mechanisms keep it from being either ignorable or annoying:

- **A `PreToolUse` guard** (`hooks/risk-brake-guard.sh`) matches Bash commands against seven irreversible-action classes (`trade`, `destructive-sql`, `migration`, `deploy`, `force-push`, `publish`, `delete`) and injects context telling Claude to run the skill. Deterministic where description-matching is probabilistic — and **non-blocking**, so it never stalls an unattended `/loop` waiting on an answer nobody is there to give.
- **A decision journal** at `.bridge/decisions.jsonl` (gitignored) records every warning, override, and eventual outcome. The skill reads it first: overridden three times in a class with no bad outcome and it backs off; a real past failure and it leads with that record. ESTPs update on experience, not argument — so the log becomes the only argument that reliably lands.
- **A push-back rule**: state the worst case once, then comply. Never repeat a warning already given in the same session. One warning is a signal; two is noise, and a muted skill protects nothing.

**Triggers:** "about to deploy", "about to place the order", "about to migrate", "taking this strategy live", "ship it" · 「要部署了」「要下單」「要跑 migration」「這個策略要進實盤」「直接推上去」

### `bridge-mind:compound-learning-tracker`

For long-horizon skill learning (music theory, Rust, quant trading, an instrument) that hits a plateau. Measures **first** — commit counts, diff sizes, backtest outputs over a 2-week window — before asking how it's been going, since the gut feeling is the thing under investigation and can't also be the evidence. Separates real stagnation from perceived stagnation (the common case), redesigns the feedback loop to surface a visible result within 3 days, and allows lateral pivots instead of full abandonment.

**Triggers:** "I can't keep going with this", "feels like no progress", "should I switch methods", "is this exercise even useful" · 「卡住了」「沒進步」「練不下去」「要不要換方法」

### `bridge-mind:system-design-devil-advocate`

Plays skeptic on designs that are expensive to reverse (data models, service boundaries, public API contracts, deployment topologies) instead of agreeing with the user's excitement — stress-tests from a "maintaining this in six months" vantage point, surfacing only the 1-2 most painful issues with a concrete minimal-change fix. Explicitly stands down for cheap-to-reverse decisions, for settled decisions the user is now implementing, and for anything already mid-execution (that's `risk-brake-thinking`).

**Triggers:** "I'm planning to design it this way", "here's the architecture diagram", "should I split this into multiple services" · 「我打算這樣設計」「要不要拆服務」「這個 schema 這樣設計」

---

## Executive function (ADHD)

### `bridge-mind:resume-interrupted-work`

Answers "what was I doing?" from evidence rather than memory. An interruption discards the working-memory state that took twenty minutes to build — but that state is on disk: uncommitted diffs *are* the frozen mental state, a failing test marks the exact stopping point, the branch name records the intent. Reads all of it plus context-mode session memory (`ctx_search` recovers *why* an approach was chosen, the piece most completely lost), then hands the thread back.

Two details carry most of the value. It runs a **tangent check** — resuming a rabbit hole faster is not a win, so it compares the interrupted work against the stated goal and says plainly when they diverge. And it ends on **exactly one next action, never a menu**, because a menu is a decision and decision-making is the depleted resource.

**Triggers:** "what was I doing", "where was I", "pick up where I left off", "I lost my train of thought" · 「我剛剛在幹嘛」「我做到哪了」「接續一下」「現在什麼進度」

### `bridge-mind:task-activation`

For knowing exactly what to do and being unable to start. Not a knowledge problem, so explaining the task again does nothing — the gap is between knowing and starting.

Produces **one physical action** meeting four tests: a body can do it, it contains zero decisions, it takes under two minutes, and it names a real path in this codebase. "Open `src/auth.ts` and add `export async function authenticate(token: string) { return null }`" — not "implement authentication". Then **offers to do it**, because a file that already exists with a stub in it has a fundamentally different activation cost than an empty intention; the task changes from starting to continuing, and continuing was never broken.

The named anti-pattern is **producing a plan**. A plan feels like progress, is enjoyable to write, and leaves the user exactly as stuck — for someone already avoiding, an elaborate plan is avoidance with better production values. Also never asks why they haven't started, never mentions how long it's been sitting, never says "it's easy".

**Triggers:** "I can't start", "I don't know where to begin", "I keep putting this off", "this feels overwhelming" · 「動不了」「不知道從哪開始」「一直拖著沒做」「開不了頭」

### `bridge-mind:time-blindness-guard`

Time blindness is the absence of an internal clock, not carelessness — twenty minutes and three hours feel identical under full attention, which is why "I'll just finish this one thing" is sincere and reliably wrong. Handles both directions:

- **Elapsed time** — the manual counterpart to `focus-timer.sh`. Reports the number neutrally (never as a reprimand), checks physical needs that hyperfocus suppresses outright, and flags drift from the stated goal as an observation rather than a correction.
- **Estimate calibration** — logs estimate vs. actual to `.bridge/focus-log.jsonl` and feeds back the measured personal multiplier: "you estimated 45 min; your median across 11 tasks is 2.4x, so 1h50m." Shows the arithmetic rather than silently revising, because a visible number is one you can argue with. Stays quiet below 5 completed entries instead of inventing a ratio.

**Triggers:** "how long will this take", "how long have I been at this", "this should be quick", "I'll just finish this one thing" · 「這要多久」「我做多久了」「應該很快」「弄完這個就好」

### `bridge-mind:distraction-capture`

The "I'll just quickly…" moment. Tangents get chased not because they're more important but because **they'll be forgotten otherwise** — and for unreliable working memory that fear is well-founded, so the fix is a trustworthy place to put things, not discipline.

Triages first (something that genuinely *blocks* the current task is a discovered dependency, not a distraction), then appends one timestamped line to `.bridge/inbox.md` with the file, line, and originating task — **asking nothing**, since every question is a chance to get pulled into discussing the tangent. Closes by restating the thread you were on, which is where most of the value is: the real cost is the lost thread, not the lost seconds.

Two properties keep it working, and losing either breaks it: capture must be instant, and the inbox must actually get reviewed. An inbox that becomes a graveyard teaches, correctly, that parking equals discarding — so `unfinished-work-audit` reads it.

**Triggers:** "I'll just quickly", "wait, what about", "oh I should also", "while I'm in here" · 「順便」「我先弄一下」「突然想到」「岔題一下」

### `bridge-mind:unfinished-work-audit`

Sits across both layers. Counters Se novelty-chase — the pull toward whatever is newest, which makes the design phase compelling and the finishing phase not. Gathers hard evidence (unmerged and stale branches, untracked files, uncommitted work, stale TODO markers) and cross-references committed design specs against the codebase to find **specs with no implementation** — the most deceptive item in the audit, because the commit log reads as if something shipped.

Also the scheduled review that keeps the three companion logs honest, and **the only step anywhere in the series that closes them**: it drains `inbox.md`, asks about `decisions.jsonl` entries still holding `outcome: null`, and collects actuals for `focus-log.jsonl` estimates still holding `actual_min: null`. Skip it and all three degrade the same way — they accumulate, never calibrate, and two of them become records of unmet obligations. `time-blindness-guard` in particular stays silent below 5 completed entries rather than inventing a ratio, so without this step it simply never starts working.

Each item gets a **ship / kill / park** recommendation, where killing counts explicitly as a success outcome, and a WIP ceiling of 3 open threads is enforced. Doesn't moralize about discipline and doesn't block starting something new — it shows the pile, asks one question, and respects the answer.

**Triggers:** "what should I work on", "what's still open", "did I finish that", "I have too many things going", "let's start something new" · 「還有什麼沒做完」「東西太多了」「那個做完了嗎」「來做個新的」

### `bridge-mind:tone-check-before-send`

Covers the tertiary-Fe blind spot: under time pressure or deep technical focus, delivery drops out and what remains is Ti's raw correctness, landing far harder than intended. The author can't detect this from the inside — the text reads as merely efficient to whoever wrote it, because they have the friendly intent and the recipient has only the words.

A translation layer, not a politeness lecture: **every technical claim survives at full strength**, only delivery changes — softening a correct objection into vagueness would be a worse failure than bluntness. Scores how the draft lands (collaborative / neutral / blunt / harsh), stays silent when it's already fine, and returns finished sendable text rather than a list of suggestions. Runs on outward-facing text only; skips private notes entirely.

**Triggers:** "review this PR", "leave a comment", "reply to this", "how does this sound", "push back on this" · 「幫我回這個」「這樣回可以嗎」「寄給他」「這樣講會不會太兇」

## Requirements

None beyond Claude Code itself — every skill here uses only `Read`/`Grep`/`Glob`/`Bash`, and all state lives in gitignored files under `.bridge/`.
