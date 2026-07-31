# Design: bridge:todo-tracker skill

## Purpose

New skill in the `bridge` plugin that manages a single markdown todo list inside a *target* repo (the repo the user is currently working in, not the `bridge` repo itself), with a fixed set of states that reflect how development work actually stalls or progresses — not just open/closed.

## Storage

- File: `docs/todo/TODO.md` in the target repo (matches the existing "known output paths" convention in this repo's CLAUDE.md, e.g. `docs/pipeline-reviews/`, `docs/autoresearch/plan/`).
- Plain markdown, one `##` heading per todo item, state shown as a leading `[state]` tag in the heading.
- No JSON, no build step, no runtime — skill instructions operate on the file directly via Read/Edit/Write, consistent with "Skills must not implement code themselves."

### Item format

```markdown
## [thinking] 重構 auth middleware
- 建立: 2026-07-31
- 更新: 2026-07-31
- 備註: 考慮拆成兩個 middleware，還沒定案
```

### Archive section

Completed or deleted-but-kept-for-history items move to a `## Archive` section at the bottom of the same file (not a separate file), so the whole history stays in one reviewable place.

```markdown
## Archive
### [done] 舊項目...
```

## States (7, fixed set)

| State | Meaning |
|---|---|
| `backlog` | 慢慢實作，還沒開始的新功能/任務 |
| `thinking` | 思考中，方向或做法還沒定案 |
| `optimize-later` | 已可運作，優化想法留著未來慢慢考慮 |
| `handoff` | 交由他人接手 |
| `in-progress` | 進行中 |
| `needs-info` | 缺少細節或決策，需要回頭問清楚才能繼續 |
| `done` | 完成，移入 Archive |

The set is fixed (not free-text) to keep listing/filtering meaningful. New states are not added ad hoc — if a future need doesn't fit, revisit this list deliberately rather than inventing one-off tags.

## Operations

The skill is invoked via natural language (e.g. "新增 todo", "把 X 標成 thinking", "列出待辦", "歸檔 X") and performs one of:

1. **新增 (add)** — create a new `##` item, default state `backlog` unless the user specifies one, stamps 建立/更新 dates.
2. **改狀態 (set-state)** — change an item's `[state]` tag, update the 更新 timestamp, optionally append a 備註 note explaining the change.
3. **列出 (list)** — list items, optionally filtered by state; Archive is excluded from default listing.
4. **刪除/歸檔 (delete/archive)**:
   - Archive: move the item under `## Archive`, force state to `done`.
   - Delete: remove the item entirely — skill must confirm with the user before doing this (destructive, per repo-wide caution norms).

## Error handling

- If `docs/todo/TODO.md` doesn't exist yet, the skill creates it (with an empty `## Archive` section) on first `add`.
- If the user names a todo that doesn't match any heading, the skill lists close matches instead of guessing.

## Out of scope

- No cross-repo aggregation (that's a different, hypothetical skill).
- No JSON/CLI interface.
- No automatic archiving on a timer — archiving is always an explicit user action.
