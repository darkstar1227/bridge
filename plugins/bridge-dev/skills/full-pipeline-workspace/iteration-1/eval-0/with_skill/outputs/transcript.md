我正在使用 bridge:full-pipeline skill，依序把整個 workflow 串起來，把每一步的產出接到下一步當輸入。

## 目前所在位置

你說「剛用 /autoplan 把訂單匯出功能的 plan 定案了」，所以 Sequence 裡的：

- **步驟 1 `/office-hours`** — 已完成（在啟動這個 pipeline 之前，你已經自己走過釐清問題/限制的階段）。
- **步驟 2 `/autoplan`** — 已完成，plan 已定案，但裡面還留了一個未決的技術方向：sync 匯出 vs. 背景 job 匯出。

我先檢查了一下 repo 實際狀態，確認有沒有現成的 plan 檔可以直接接手：

```
$ git status --short
$ ls docs/plans docs/superpowers docs/pipeline-reviews
```

結果：`docs/plans/`、`docs/superpowers/{input,plans,specs}/` 裡都沒有任何跟「訂單匯出」相關的檔案（現有的都是別的功能，例如 opencode-bridge、init-project）。也就是說這次的 /autoplan 產出目前只存在於我們的對話脈絡裡，沒有落地成 `docs/plan.md` 或 `docs/spec.md`。這不影響我往下走，但等一下第 4 步 `bridge:autoresearch-plan` 去「定位 plan 檔」時會找不到檔案，我會用你剛剛口述的 plan 內容代替，並在下面標出這點。

所以這次執行從**步驟 3（Database checkpoint A）**開始接續。

## 步驟 3 — Database checkpoint A（對 autoplan 產出的 plan 做檢查）

依 SKILL.md 的判斷邏輯，在 plan checkpoint 要檢查 plan 的 scope/architecture 內容有沒有提到：新表、migration、index、RLS policy、foreign key，或任何 schema 變更。

你已經明確說了：「這個功能不會動到資料庫 schema」。訂單匯出功能（無論是 sync 匯出還是背景 job 匯出）本質上是讀取既有訂單資料、產生匯出檔案/串流輸出，不涉及新增資料表或欄位變動，這跟你的描述一致，我沒有看到任何 schema 訊號。

**判斷：不觸發 `supabase:supabase-postgres-best-practices`。** 這裡不呼叫，直接往下走。

## 步驟 4 — `bridge:autoresearch-plan`

這一步的觸發條件是：locked plan 裡有超過一個「真的值得比較」的候選技術方向。你的 plan 明確寫了兩個候選方案且尚未決定：

1. Sync 匯出（同步、即時回傳）
2. 背景 job 匯出（非同步、事後通知/輪詢取得結果）

這正好符合 autoresearch-plan 存在的理由（未定案的架構選擇，值得在寫死之前做一次有界限的比較），所以**我會呼叫 `bridge:autoresearch-plan`**，而不是跳過。

我看了一下這個 skill 實際的 Step 1 / Step 2 邏輯（真的讀了 `skills/autoresearch-plan/SKILL.md`，這部分不是模擬）：

- **Step 1** 會用跟 `gstack-to-plan` 一樣的順序去找 plan 檔（明確路徑 → `docs/plan.md` → `docs/spec.md` → `docs/` 或 `.gstack/` 下最新修改的 `.md`）。如前面查過的，這次沒有現成檔案，所以在真實執行中它會直接用你剛剛描述的 plan 內容繼續，或反問你 plan 檔在哪 —— 這裡我用你口述的內容當作 plan 來源繼續走。
- **Step 2** 要求先釘死三件事才能開始比較：**scope**（差異軸）、**budget**（比較輪數/時間上限）、**metric + 方向**（用什麼單一指標判勝負，越高越好還是越低越好）。

我能從目前資訊推得的：
- **Scope**：sync 匯出 vs. 背景 job 匯出，單一變因，符合它「一次只比一個軸」的要求。

我**推不出**、且 plan 裡也沒有寫「成功指標/驗收標準」可以借用的：
- **Budget**：要比幾輪、每個候選花多少預算沒有訂。
- **Metric + 方向**：候選方案要用什麼單一數字定輸贏（例如：p95 匯出延遲、超時/失敗率、匯出檔案上限大小下的記憶體使用、實作複雜度所需工時）沒有講。

依 SKILL.md 的規則（「Only fall back to AskUserQuestion for whichever of the three you couldn't confidently derive」），這是 pipeline 該停下來讓你決定的地方，不是我可以替你猜的部分——尤其 sync vs. 背景 job 這個選擇，通常取決於你們的匯出資料量/超時容忍度，這種業務判斷我不該幫你拍板。

**在這裡暫停，需要你回答：**

1. 這次比較要用什麼指標定勝負？例如：
   - 大量訂單（比如 10 萬筆）匯出時的延遲/是否會 timeout
   - 對現有 API/伺服器資源的佔用（同步阻塞 request thread vs. 背景 worker）
   - 使用者體感（同步等待 vs. 非同步通知/輪詢的 UX 成本）
   - 實作複雜度（背景 job 需要 queue/worker 基礎設施，sync 不需要）
2. 比較的 budget 抓多大？例如「各花一輪分析，不做真的效能測試，只用推理/既有數據估算」，或是「各起一個最小 harness 實測一次」。

等你回答後，我會依你選的 metric 呼叫 `bridge:autoresearch-plan`，讓它針對兩個候選各起一個 subagent 產出該指標的數字，比出贏家，然後把贏家寫成 Architecture Decision，折進步驟 5 `superpowers:writing-plans` 要吃的 plan 裡。

## 尚未執行的後續步驟（等上面決定後才會走）

- **步驟 5 `superpowers:writing-plans`** — 把 autoplan 的 plan ＋ autoresearch-plan 選出的贏家方案，轉成可執行的實作計畫。
- **步驟 6 `superpowers:subagent-driven-development`** — 依計畫執行任務。
- **步驟 7 `bridge:autoresearch-impl`** — 只有在有一個值得反覆迭代對照的指標時才會跑；訂單匯出這種功能是否需要，我會在步驟 6 完成、看到實際任務內容後再判斷要不要問你，而不是預設一定要跑。
- **步驟 8 Database checkpoint B** — 對步驟 6-7 的實際 diff 跑 `git diff --stat`，檢查有沒有碰到 `supabase/migrations/*.sql`、schema 定義檔或 ORM model 檔。目前預期會跟 checkpoint A 一樣是「沒有」，但我會用實際 diff 再驗一次，不會因為 checkpoint A 過了就跳過。
- **步驟 9 `code-review` / `codex:review`** — 對最終 diff 做標準審查。
- **步驟 10 `/qa`** — 端到端瀏覽器驗證與回歸檢查。

一有你對 metric/budget 的回覆，我就會從步驟 4 接續往下跑完剩下的流程。
