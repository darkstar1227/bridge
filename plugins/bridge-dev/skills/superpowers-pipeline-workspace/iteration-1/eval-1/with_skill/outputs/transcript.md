我使用 bridge:superpowers-pipeline skill，跑核心 Superpowers 流程（跳過 gstack 的規劃/研究層），過程中會檢查是否涉及資料庫變更。

## Step 1 — 確認 spec

依照搜尋順序（明確路徑 → `docs/plan.md` → `docs/spec.md` → `docs/` 底下最新修改的 `.md`），找到 `docs/spec.md`，內容確認提到：

- 新增 `audit_logs` 資料表
- 對應的 RLS（Row Level Security）policy

以此作為本次流程的 spec 來源，直接進入 Step 2。

## Step 2 — `superpowers:writing-plans`

將 `docs/spec.md` 轉成可執行的實作計畫（[模擬執行，因為 superpowers:writing-plans 在此環境未安裝]）。產出的計畫大致包含：

1. 建立 migration：新增 `audit_logs` 表（欄位：`id`, `actor_id`, `action`, `target_table`, `target_id`, `metadata jsonb`, `created_at`）
2. 在同一個 migration 或後續 migration 中啟用 RLS 並加上對應 policy（例如僅允許 service role 寫入、僅允許本人或管理員讀取）
3. 視情況新增對應的 ORM/型別定義或 API 層程式碼

## Database checkpoint A（依 plan 內容判斷）

Plan 內容明確提到「新表」與「RLS policy」——這是明確的 schema 變更訊號，符合 skill 規定的判斷條件（新表、migration、index、RLS policy、外鍵等）。

**判定：觸發。** 在進入實作前，先呼叫 `supabase:supabase-postgres-best-practices`（[模擬執行，此 skill 在此環境未安裝]）針對計畫中的表結構與 RLS 設計給意見，例如：

- 建議 `audit_logs` 使用 `created_at` 加索引以利依時間查詢
- RLS policy 建議明確拆成 `SELECT`/`INSERT` 個別 policy，避免用單一寬鬆 policy
- 建議 service role 走 `bypass RLS` 而非額外 policy，前端/一般使用者角色權限收斂到唯讀且僅限本人相關紀錄

計畫依此意見微調後，進入 Step 3。

## Step 3 — `superpowers:subagent-driven-development`

執行計畫中的任務（[模擬執行，此 skill 在此環境未安裝]）。模擬產出的 diff 大致如下：

```
supabase/migrations/20260717120000_add_audit_logs.sql | 42 ++++++++++++++++++
lib/db/schema/audit-logs.ts                            | 18 ++++++++
app/api/audit-logs/route.ts                            | 35 +++++++++++++
```

## Database checkpoint B（依 `git diff --stat` 判斷）

模擬的 diff 中出現 `supabase/migrations/*.sql`（新增 migration 檔）以及 `lib/db/schema/audit-logs.ts`（ORM/schema 定義檔對應到資料表）——同樣命中 skill 規定的訊號（migration 檔案、schema 定義檔、ORM model 檔）。

**判定：觸發。** 在進到收尾步驟前，再次呼叫 `supabase:supabase-postgres-best-practices`（[模擬執行]）針對實際落地的 SQL 做一次覆核，重點檢查：

- migration 是否可安全重跑（`IF NOT EXISTS` 等）
- RLS policy 是否真的在 migration 裡被 `ENABLE ROW LEVEL SECURITY` 並附上對應的 `CREATE POLICY` 陳述式，而非只在計畫中提到卻漏寫
- 索引、外鍵約束是否對應到查詢模式

覆核通過（無阻斷性問題）後進入 Step 5。

## Step 5 — `superpowers:finishing-a-development-branch`

實作與兩次資料庫覆核都完成後，呼叫此 skill（[模擬執行]）決定 merge / PR / cleanup 的收尾方式。

---

### 小結

- Spec 來源：`docs/spec.md`（找到，內容含 `audit_logs` 表 + RLS policy）
- 流程：writing-plans → **checkpoint A（觸發）** → subagent-driven-development → **checkpoint B（觸發）** → finishing-a-development-branch
- 兩個資料庫檢查點都因為明確訊號（spec/plan 提到新表與 RLS；diff 出現 migration 與 schema 檔）而觸發 `supabase:supabase-postgres-best-practices`，並非無腦每次都跑。

以上為完整流程模擬結果；由於 `superpowers:writing-plans`、`superpowers:subagent-driven-development`、`superpowers:finishing-a-development-branch` 以及 `supabase:supabase-postgres-best-practices` 在目前環境中並未實際安裝，各步驟的產出（計畫內容、diff、覆核意見）為依 spec 內容合理模擬，尚未寫入實際檔案。若要正式執行，需要在有這些 skill 的環境中重跑。
