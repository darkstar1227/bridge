I'm using the bridge:full-pipeline skill to run the workflow end-to-end, chaining each step's output into the next.

先說一下我怎麼解讀這個 request：你說「plan 已經定案了，就只有一種做法沒有替代方案可比較」，這句話同時回答了 pipeline 兩個地方的問題 —— (a) plan 是否已經走完 office-hours + autoplan，以及 (b) 要不要跑 autoresearch-plan 做方案比較。我會照這個理解往下跑，但每一步我都會照 SKILL 的規定明講「這步是真的跑、還是因為你已經講清楚而跳過、為什麼」，不會靜默省略。

## Step 1-2：`/office-hours` + `/autoplan`（gstack）

先查了一下 repo 裡有沒有現成的、對得上「subscriptions 表」的 locked plan 文件：

- `docs/plans/`：`2026-07-13-init-project-design.md`、`2026-07-13-init-project-skill.md`、`2026-07-15-opencode-bridge.md`
- `docs/superpowers/plans/`：`2026-07-06-send-update-email.md`
- `docs/superpowers/specs/`、`docs/superpowers/input/`：都是 opencode-bridge / send-update-email 相關

沒有找到任何跟 subscriptions table 對得上的 plan 文件，repo 裡也沒有 `supabase/` 目錄。

按 SKILL 的規定我不能為了省時間就跳過 step 1-2 ——但你已經明確告訴我「plan 已經定案，只有一種做法」，這句話本身就是 autoplan 這步驟該產出的結果（一份 locked、審過的 plan）。既然找不到對應的書面文件，我把這當成一個要浮出檯面的判斷點，而不是悄悄假設：

**[ASSUMPTION]**：我會把你這句話當作 step 2 (`/autoplan`) 的產出直接採用 —— locked plan = 「新增一張 `subscriptions` 表 + 一個對應的 migration，單一做法、無替代方案需要比較」。如果你手上其實有一份更完整的書面 plan（不管是外部文件還是之前對話產出的），麻煩貼給我或指路徑，我會改用那份而不是這個簡述版本繼續往下跑。在沒收到更正之前，我照這個假設繼續。

## Step 3：Database checkpoint A

對照 step 2 的 plan 內容檢查訊號：plan 文字裡明確提到「新增一張 subscriptions 表」和「一個 migration」——兩個訊號都命中（新表 + migration）。

→ **觸發**：在往下走之前，先叫用 `supabase:supabase-postgres-best-practices` 對這個 schema 決策做審查（表結構、索引、RLS policy、外鍵這些東西現在改還便宜，implement 完再改就貴了）。

由於這個技能在目前 sandbox 沒有安裝，我在這裡用敘述模擬它會檢查的重點，而不是假裝真的跑過：
- `subscriptions` 表的主鍵/外鍵設計（通常會關聯 `users`/`accounts` 表 — 需要確認 FK 與 cascade 行為）
- 是否需要 RLS policy（Supabase 預設會需要，除非明確是 service-role only 的表）
- 狀態欄位（active/canceled/trial 等）是否該用 enum 還是 text + check constraint
- 是否需要 index（例如查詢常用的 `user_id`, `status`）
- migration 檔案命名與是否可逆（down migration）

**這步的實際結果需要等真的呼叫 `supabase:supabase-postgres-best-practices` 才能拿到具體建議** —— 在這次模擬中我先記下「已判定需要跑」，實際 pipeline 執行時這裡會停下來等審查技能的輸出，再把它折進下一步的 Architecture Decision。

## Step 4：`bridge:autoresearch-plan`

**跳過**，理由明確且直接來自你的敘述：「就只有一種做法沒有替代方案可比較」。這正是 SKILL 裡寫的跳過條件 —— autoresearch-plan 存在的目的是比較多個候選技術方案，locked plan 只有一種做法時它自己的 Step 1 也會判定跳過。不需要真的呼叫它來確認。

直接進 step 5。

## Step 5：`superpowers:writing-plans`

把 step 2 的 plan（新增 `subscriptions` 表 + migration，單一方案）加上 step 3 資料庫審查的建議（一旦拿到，會折進 plan 的 Architecture Decision 段落）一起餵給這個技能，產出可執行的 Superpowers 格式實作計畫（含 TDD 任務拆解）。

這個技能目前 sandbox 未安裝，無法真的執行 —— 敘述性模擬其產出：預期會拆成類似「1) 撰寫 migration SQL 建立 subscriptions 表、2) 若有 RLS/policy 則一併加入 migration、3) 對應的 model/type 定義（如果 repo 有 ORM 層）、4) 驗證 migration 可以 up/down」這樣的任務清單，每個任務先寫測試（如果 repo 有 migration 測試框架的話）。

沒有用 `bridge:gstack-to-plan` 顯式轉換 —— 你沒有要求要走那個顯式的 gstack→Superpowers 轉換路徑，所以照 SKILL 預設走法，用 inline 方式把 plan 內容直接餵給 `writing-plans`。

## Step 6：`superpowers:subagent-driven-development`

執行 step 5 產出計畫裡的任務（建 migration 檔、建表 SQL、對應 model/type）。同樣未安裝，僅敘述：預期會產生一個新的 migration 檔案（例如 `supabase/migrations/<timestamp>_create_subscriptions.sql`），內容包含 `CREATE TABLE subscriptions (...)`。

由於這個技能沒有真的執行，repo 裡不會有實際 diff —— 我不會假裝已經產生檔案或跑過 `git status` 看到變更。

## Step 7：`bridge:autoresearch-impl`

按 SKILL 規定：「只有在有一個值得拿來迭代的 metric 時才跑，不確定就問，不要每個 task 都預設要跑」。

這個 task 是「新增一張表 + 一個 migration」——結構性、一次到位的 schema 變更，沒有明顯可迭代的指標（不像「調整某個演算法的準確率」那種需要反覆跑分的任務）。

**判斷：跳過**，不問使用者確認，理由:單純新增 schema 沒有自然的 metric 可以迭代；如果你其實想針對某個效能指標（例如查詢延遲）反覆調整，請直接說,我會補跑這步。

## Step 8：Database checkpoint B

按 SKILL 規定，這步要對 **step 6-7 產出的實際 diff** 跑 `git diff --stat` 來確認有沒有碰到 migration/schema 檔案。

因為 step 6 在這次模擬中並未真的執行（`subagent-driven-development` 未安裝、沒有真正落地任何檔案變更），我現在對 repo 跑一次 `git diff --stat` 只會看到跟這個 pipeline 無關的既有未追蹤/已修改檔案，不代表這個功能的實作結果，所以我不會拿現在的 repo 狀態冒充 step 8 的判斷依據。

**如實記錄**：等 step 6 真正落地、實際 migration 檔案出現在 `supabase/migrations/*.sql`（或對應路徑）之後，這個 checkpoint 幾乎可以肯定會 **觸發**（因為 plan 本身就是要加 migration），屆時應在進入 code review 前再跑一次 `supabase:supabase-postgres-best-practices`，這次是針對實際寫出來的 SQL 做審查（型別、約束、索引、是否需要 down migration）。

## Step 9：`code-review` / `codex:review`

等 step 6-8 真正產生 diff 後才有東西可審。目前尚無實作，此步驟待實作完成後才會真的呼叫。

## Step 10：`/qa`（gstack）

同上，需要有實際落地的功能（新表 + migration 跑過）才能做端對端瀏覽器驗證/回歸測試，目前尚未到這一步。

---

## 目前狀態小結

- Step 1-2：以你的敘述當作 locked plan 採用（**[ASSUMPTION]**，有正式文件請提供以取代）
- Step 3：資料庫 checkpoint 判定 **觸發**，需跑 `supabase:supabase-postgres-best-practices`（模擬中未實際執行，因為技能未安裝）
- Step 4：**跳過**（你已確認只有一種做法，無替代方案）
- Step 5-7：敘述性模擬（技能未安裝，未產生實際檔案變更）
- Step 8：**理論上會觸發**，但因為 step 6 未真正落地，暫不對現在的 repo 狀態做判定
- Step 9-10：待前面步驟真正產出 diff 後才會執行

如果你要我在真實環境（有安裝這些技能）重跑，我會照上面同樣的順序與判斷邏輯執行；如果你手上有正式的 locked plan 文件，先給我，我會用它取代 step 1-2 的假設內容再往下走。
