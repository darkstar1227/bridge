我先查了一下 repo，想找到你剛剛用 `/autoplan` 定案的那份「訂單匯出功能」plan：

- `git status` — 目前在 `main` 分支，有一些未追蹤/修改的檔案，但都跟這個功能無關。
- `docs/plans/` 裡只有 `2026-07-13-init-project-design.md`、`2026-07-13-init-project-skill.md`、`2026-07-15-opencode-bridge.md`，沒有訂單匯出相關的檔案。
- `docs/superpowers/plans/`、`docs/superpowers/specs/`、`docs/superpowers/input/` 也翻過了，只有 `2026-07-06-send-update-email.md`（plan/spec）和 `gstack-handoff-2026-07-15-opencode-bridge.md`（handoff），同樣沒有訂單匯出的東西。
- 全機器搜尋 `訂單`、`order-export` 相關檔名也沒有結果。

也就是說，`/autoplan` 定案的那份 plan 目前不在這個 `bridge` repo 裡（`bridge` 本身是純 skill 定義的 plugin repo，不是放實際功能 plan 的地方）。我沒辦法在這裡直接接上去跑完 pipeline，卡在兩個點，需要你補一下：

1. **plan 檔案在哪裡？** 是在另一個專案的 repo（例如放訂單系統程式碼的那個 repo）的 `docs/plans/` 或類似路徑下，還是只存在當時的對話 session 裡、還沒落地成檔案？如果只在 session 裡，麻煩貼一下 plan 全文或路徑，我才能繼續往下接（轉成 spec → 交給實作）。

2. **sync vs 背景 job 匯出，要先選一個。** 這是 plan 裡標記「還沒決定」的分叉點，會直接決定：
   - API 介面設計（同步回傳檔案 vs. 建立 job 後回傳 job id + 輪詢/webhook 通知）
   - 是否需要 queue/worker（例如 background job runner）
   - timeout / 使用者體驗（同步匯出大量訂單可能會 timeout；背景 job 需要額外的狀態追蹤與通知機制）
   
   你提到「這個功能不會動到資料庫 schema」，這點兩種做法都適用（背景 job 的狀態通常可以用既有的 job/queue 基礎設施而不需新表，如果你們本來就有的話）——但如果目前沒有任何 job/queue 機制，背景 job 做法可能還是需要一張輕量的狀態表或依賴外部 queue 服務，這會跟「不動 schema」的前提有衝突，需要你確認一下現有基礎設施狀況。

在我拿到 plan 內容、並且確認 sync/背景 job 的選擇之前，我沒辦法安全地把 pipeline 跑完（轉 spec、寫 plan-review、交付實作）——怕做了白工或做錯方向。

麻煩提供：
- plan 檔案路徑或內容
- sync 匯出 / 背景 job 匯出你想選哪個（或要不要我幫你列出兩者的取捨建議，讓你現場拍板）

拿到後我可以接著往下跑：把 plan 轉成 spec → 走 review（eng/design/CEO 視需要）→ 產出實作計畫 → 視你需求交給實作步驟。
