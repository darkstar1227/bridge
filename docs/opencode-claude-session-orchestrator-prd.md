# PRD: Claude Code ↔ OpenCode Session Orchestrator

## 文件資訊
- 文件版本：v1.0
- 文件日期：2026-07-14
- 文件類型：產品需求文件（PRD）
- 適用範圍：Claude Code 透過 Agent SDK 呼叫 OpenCode daemon，並支援 session 重用、開新 session、fork session 與 streaming 輸出

## 背景與問題定義
目前的目標不是單純把 Claude Code 接到 OpenCode，而是建立一個可長期使用的代理編排層，讓 Claude Code 在委派 OpenCode 工作時，同時具備兩種能力：延續既有上下文，以及在必要時乾淨地開新工作線。OpenCode 官方已提供 server、SDK、CLI、TUI 與 session 相關能力；其中 server 可作為常駐 backend，SDK 可程式化管理 session，CLI/TUI 則已支援 continue、指定 session、fork、新建與 resume 等行為[cite:128][cite:142][cite:106][cite:131][cite:138]。

若缺少這層 orchestration，常見結果是每次 task 都重新開對話、上下文反覆注入、token 成本偏高、長任務中斷後難以接續，以及不同任務線彼此污染。OpenCode 的 client/server 架構、session API 與事件串流能力，正好可作為解法基礎[cite:128][cite:142]。

## 產品目標
本產品要提供一個位於 Claude Code 與 OpenCode 之間的 orchestration service，負責 session 決策、任務轉派、輸出串流與狀態管理。系統必須支援預設重用 session、按需建立新 session、從既有 session fork 新分支，以及在任務執行中即時回傳 OpenCode 的事件流[cite:128][cite:138][cite:131]。

產品成功後，使用者應能用單一介面表達如下意圖：
- 延續上一個與某 repo / topic 對應的 session。
- 建立全新 session 處理不同任務。
- 從既有 session fork 一個分支做高風險改動。
- 在 Claude Code 中即時看到 OpenCode 執行中的 streaming 輸出與事件。

## 非目標
以下不在本期範圍內：
- 建立完整多租戶 SaaS 平台。
- 建立 OpenCode provider 抽象層，支援多個不同 agent backend。
- 設計 GUI 管理後台，除非作為後續延伸。
- 將所有 OpenCode 功能一比一映射到 Claude Code；本期以 session orchestration、task dispatch 與 streaming 為主[cite:128][cite:142]。

## 使用者與場景
主要使用者是進階開發者、DevOps / SRE 工程師、AI coding agent 重度使用者，以及希望把 Claude Code 作為主控代理、OpenCode 作為外部執行代理的人。這些使用者通常需要在同一 repo 上持續工作、跨多個 task 延續上下文，同時保留分支式探索與隔離能力。

典型場景包括：
- 持續修同一個服務的 bug，要求上下文延續。
- 針對大型 refactor 開一個乾淨 session，避免污染主線。
- 針對既有 session fork 分支，比較兩種實作方案。
- 長任務在 daemon 持續執行，Claude Code 或終端 client 中斷後再接回。
- 將 OpenCode 當成 Claude Code 的 delegated worker，並保留可觀察性[cite:128][cite:138][cite:131]。

## 核心假設
OpenCode server 可作為常駐 daemon 運行，並提供 session 管理與 OpenAPI/HTTP 介面；OpenCode SDK 可連到既有 server 並操作 session；CLI/TUI 已有 new、continue、resume、fork 的概念，代表產品語義已有對應基礎[cite:142][cite:128][cite:138][cite:131]。

另一項關鍵假設是：session 管理策略不應由 OpenCode daemon 自動決定，而應由 orchestration layer 根據 repo、branch、task group、topic 與使用者明示模式來決策。這樣才能同時實現 session 重用與開新 session 的能力[cite:128][cite:138][cite:147]。

## 產品範圍
本產品包含以下模組：

1. OpenCode daemon 管理模組：負責連線既有 server 或檢查其健康狀態。OpenCode server 支援以程式化方式互動，並提供 session 端點與 OpenAPI 文件[cite:142]。
2. Session Policy Engine：根據請求內容決定 reuse、new 或 fork。
3. Session Registry：保存 orchestration 層可追蹤的 session metadata，例如 repo、branch、topic、title、最近使用時間。
4. Task Dispatcher：向 OpenCode 指定 session 發送 prompt。
5. Streaming Adapter：將 OpenCode 事件流轉為 Claude Code 可顯示的即時輸出；OpenCode SDK 已提供 event 訂閱能力作為整合基礎[cite:128]。
6. Recovery & Retry：處理 client 中斷、network retry、server reconnect 與 health check。
7. Audit / Trace Hooks：選配，用於後續追蹤任務、session 與結果。

## 名詞定義
| 名詞 | 定義 |
|---|---|
| OpenCode daemon | 常駐中的 OpenCode server process，可被 SDK 或 CLI attach[cite:142][cite:138] |
| Session reuse | 將新 task 發送到既有 session，以延續同一段上下文[cite:128][cite:138] |
| New session | 建立一個全新 session，不承接既有對話上下文[cite:131][cite:132] |
| Fork session | 從既有 session 分支出新 session，以保留脈絡但隔離後續改動[cite:138][cite:144] |
| Session policy | orchestrator 根據規則決定要 reuse、new 或 fork 的策略 |
| Streaming adapter | 將 OpenCode 的事件流轉換成 Claude Code 端的即時輸出通道[cite:128] |

## 使用者需求
### Must-have
- 使用者可以明確要求「沿用既有 session」。
- 使用者可以明確要求「開新 session」。
- 使用者可以明確要求「fork 某個 session」。
- 系統可以在未明確指定時，自動選擇最合適的 session reuse 策略。
- Claude Code 呼叫 OpenCode 時，能即時看到 streaming 輸出，而不是任務完成後一次回傳。
- 系統可以列出可重用的 session 候選，供上層選擇或自動匹配[cite:128][cite:142][cite:131]。

### Should-have
- 支援 repo 維度與 branch 維度的 session 分組。
- 支援 topic / task-group 維度的 session 分組。
- 支援設定 session TTL 與 rotate 規則，以避免上下文過長。
- 支援 fallback：若指定 session 不存在，根據 policy 自動新建。

### Could-have
- 為 session 自動產生摘要與標籤。
- 建立 session ranking，優先推薦最相關的歷史 session。
- 在 Claude Code 中顯示 session tree 與 fork 關係。

## 主要使用流程
### 流程 A：重用 session
1. Claude Code 發出 task，並提供 repo / branch / topic 或直接給 session_id。
2. Orchestrator 查詢 Session Registry，若有明確 session_id，先驗證其存在；若沒有，則依 policy 搜尋最佳匹配 session[cite:128][cite:142]。
3. 找到可用 session 後，將 prompt 發送到該 session。
4. OpenCode 開始執行，orchestrator 訂閱事件流並即時轉送。
5. 任務完成後，更新 session metadata 與 last_used_at。

### 流程 B：開新 session
1. Claude Code 發出 task，指定 mode=new。
2. Orchestrator 呼叫 session.create 建立新 session[cite:128][cite:142]。
3. 將 prompt 發送到新 session。
4. 即時串流輸出。
5. 將該 session 記錄到 Session Registry，供後續 reuse。

### 流程 C：fork session
1. Claude Code 指定 mode=fork 並帶 source_session_id。
2. Orchestrator 驗證 source session 是否存在，並依 OpenCode 支援的 fork / continue-fork 語義建立分支 session；CLI 已明確支援 `--fork` 作為延續時保留原 session 的方式[cite:138][cite:144]。
3. 新分支 session 接收 task prompt。
4. 即時串流輸出。
5. Session Registry 記錄 parent-child 關係。

## 功能需求
### FR-1 OpenCode Daemon 連線
系統必須能連線到既有 OpenCode daemon，並在啟動時執行 health check。OpenCode server 提供 HTTP 介面與可檢視的 OpenAPI 規格，可用來驗證可用性與生成客戶端[cite:142]。

### FR-2 Session 查詢
系統必須能列出現有 session、讀取指定 session 與取得最近活動 session。OpenCode server 與 SDK 提供 session 相關操作基礎[cite:142][cite:128]。

### FR-3 Session 建立
系統必須能建立新 session，並附帶 title、repo、branch、topic 等 metadata。TUI 與 CLI 已具備 new session 概念，本產品需在 SDK / orchestration 層將其標準化[cite:131][cite:132][cite:138]。

### FR-4 Session 重用
系統必須支援以下重用方式：
- 直接指定 session_id。
- 根據 repo + branch + topic 自動匹配。
- 根據最近使用且狀態健康的 session 匹配。
- 指定 `continue last` 行為，等同 CLI 的 `--continue` 語義[cite:138][cite:136]。

### FR-5 Session Fork
系統必須支援從既有 session 建立分支 session，並記錄 parent_session_id。CLI `--fork` 已提供產品語義依據，本產品需在 SDK 整合層實現等價能力[cite:138][cite:144]。

### FR-6 Prompt Dispatch
系統必須能向指定 session 發送 prompt，並允許攜帶 task metadata，例如 task_id、requester、priority、task_group。

### FR-7 Streaming Output
系統必須支援即時輸出模型文字、工具事件、狀態變更與完成事件。OpenCode SDK 文件指出可透過程式化 client 與事件機制進行整合，適合作為 streaming adapter 的基礎[cite:128]。

### FR-8 Session Policy Engine
系統必須根據以下輸入決策 reuse / new / fork：
- 顯式 `session_mode`
- 顯式 `session_id`
- repo / branch / workspace
- topic / task_group
- 是否高風險改動
- 是否要求隔離上下文
- 既有 session 的可用性與新鮮度

### FR-9 Session Registry
系統必須維護下列 metadata：
- session_id
- title
- repo_path
- branch_name
- topic
- task_group
- parent_session_id
- created_at
- last_used_at
- last_status
- summary（可選）

### FR-10 Recovery
當 Claude Code 端中斷時，OpenCode daemon 不應因此丟失 session；重新連線後應能 resume 既有 session。這與 OpenCode 的 session / continue / resume 模式一致[cite:131][cite:136][cite:138]。

## 非功能需求
### 可用性
- daemon 健康時，orchestrator 不得因單一 task failure 而崩潰。
- 若 session 查詢失敗，必須有降級策略，例如改為新建 session。

### 效能
- session 決策延遲應盡量低於 300ms（不含 OpenCode 推理時間）。
- streaming 首次可見事件應盡量低於 2 秒，實際依 provider 與模型而定。

### 穩定性
- 與 OpenCode daemon 的連線失敗時，需具備 retry / backoff。
- 任務執行中的 client 中斷不應自動刪除 session。

### 可觀察性
- 記錄 request_id、task_id、session_id、source_session_id、mode、latency、terminal state。
- 支援 log level 與 tracing hook。

### 安全性
- daemon 預設應綁定 `127.0.0.1`；若需遠端存取，必須啟用額外驗證與 transport 保護。OpenCode CLI/server 文件提到可透過 server 使用者名稱與密碼做基本保護[cite:106]。

## API 介面草案
### 請求介面
```json
{
  "task": "修正 auth middleware race condition",
  "session_mode": "reuse",
  "session_id": "optional-existing-session-id",
  "source_session_id": "optional-parent-for-fork",
  "repo_path": "/workspace/service-a",
  "branch_name": "feature/auth-fix",
  "topic": "auth-middleware",
  "task_group": "bugfix",
  "title": "service-a auth fixes",
  "risk_level": "medium",
  "stream": true
}
```

### 回應介面
```json
{
  "request_id": "req_xxx",
  "session_id": "sess_xxx",
  "resolved_mode": "reuse",
  "parent_session_id": null,
  "stream_channel": "sse-or-adapter-channel",
  "status": "accepted"
}
```

### 模式定義
| mode | 說明 |
|---|---|
| reuse | 重用既有 session；若未指定 session_id，依 policy 自動挑選 |
| new | 建立全新 session |
| fork | 從 source_session_id 分支出新 session |
| auto | 由 policy engine 自動決定 |

## Session Policy 規則
### 預設規則
1. 若明確指定 `session_id` 且存在，優先 reuse。
2. 若 `session_mode=new`，直接建立新 session。
3. 若 `session_mode=fork`，必須要求 `source_session_id`。
4. 若 `session_mode=auto`：
   - 若 repo_path、branch_name、topic 與最近 session 高度一致，reuse。
   - 若 task 標記為高風險改動、架構重寫或實驗性探索，fork 或 new。
   - 若最近 session 過舊、狀態異常或上下文過長，new。
5. 若找不到適合 session，fallback 為 new[cite:138][cite:147]。

### Rotate 規則
以下條件可觸發 rotate：
- 同一 session 超過可接受上下文大小。
- topic 已明顯偏移。
- 連續多次任務失敗或 agent 進入混亂狀態。
- 使用者明示「換一條乾淨線」。

## Streaming 設計
OpenCode SDK 提供與 server 程式化互動的能力，適合建立 event adapter；產品需將 OpenCode 的事件流轉換為 Claude Code 可呈現的標準輸出事件[cite:128]。

建議至少轉換以下事件類型：
- `text_delta`：模型逐步輸出文字。
- `tool_start`：開始使用某個工具。
- `tool_end`：工具完成。
- `status`：例如 planning、running、waiting-input、completed。
- `error`：session 或 provider 錯誤。
- `done`：任務完成。

輸出要求：
- 須保序。
- 須支援部分輸出即時顯示。
- 須可關聯 request_id 與 session_id。
- 須在 client 重連後仍可重新 attach 到 session。

## 資料模型草案
### SessionRecord
```json
{
  "session_id": "sess_123",
  "title": "service-a auth fixes",
  "repo_path": "/workspace/service-a",
  "branch_name": "feature/auth-fix",
  "topic": "auth-middleware",
  "task_group": "bugfix",
  "parent_session_id": null,
  "created_at": "2026-07-14T10:00:00Z",
  "last_used_at": "2026-07-14T10:30:00Z",
  "last_status": "completed",
  "summary": "Investigated and patched auth race condition"
}
```

### TaskRecord
```json
{
  "task_id": "task_456",
  "request_id": "req_789",
  "session_id": "sess_123",
  "resolved_mode": "reuse",
  "input": "修正 auth middleware race condition",
  "status": "completed",
  "started_at": "2026-07-14T10:31:00Z",
  "completed_at": "2026-07-14T10:35:00Z"
}
```

## 驗收標準
### AC-1 重用 session
當使用者提供有效 `session_id` 並指定 `reuse` 時，系統必須將 task 發送到該 session，而不是建立新 session。

### AC-2 自動重用
當未提供 `session_id`，但 repo / branch / topic 與最近 session 相符時，系統必須在 `auto` 模式下選擇重用既有 session。

### AC-3 開新 session
當使用者指定 `new` 時，系統必須建立新 session，且新 task 不得寫入既有 session。

### AC-4 fork session
當使用者指定 `fork` 並提供有效 `source_session_id` 時，系統必須建立新分支 session，且保留 parent-child 關係[cite:138][cite:144]。

### AC-5 streaming
任務開始執行後，使用者必須能在 Claude Code 端於完成前看到逐步輸出，而不是只收到最終結果。

### AC-6 client reconnect
當 Claude Code 端中斷後重新連線，只要 OpenCode daemon 尚存，既有 session 仍可被重新 attach 或 resume[cite:131][cite:136][cite:138]。

## 風險與緩解
| 風險 | 說明 | 緩解方式 |
|---|---|---|
| session 污染 | 不相關任務共用同一 session，導致上下文偏移 | 導入 topic / task_group policy，必要時 rotate 或 fork[cite:147] |
| 過度切 session | 每個 task 都新建 session，導致上下文無法累積 | 預設 auto / reuse，並增加 session matching |
| child / fork 行為與 SDK 細節不一致 | 部分版本的 SDK 對 child session 曾有執行問題回報 | 對 fork 行為加版本相容性測試，必要時退回 CLI 語義或改以新 session + summary 注入[cite:148] |
| streaming 中斷 | SSE / adapter 中斷造成體驗不完整 | 支援 reconnect、buffer 與 done/error 補發 |
| daemon 故障 | backend crash 導致所有工作中斷 | 使用 process supervisor、health check 與自動重啟 |

## 里程碑
### Phase 1：最小可用版本
- 接上既有 OpenCode daemon。
- 支援 `reuse` / `new`。
- 支援 session list / get / create / prompt。
- 支援基本 streaming。

### Phase 2：進階 session 管理
- 支援 `fork`。
- 支援 Session Registry。
- 支援 auto policy。
- 支援 reconnect / retry。

### Phase 3：可觀察性與優化
- 加入 tracing / audit logs。
- session ranking 與自動摘要。
- policy tuning 與 context rotate。

## 成功指標
| 指標 | 目標 |
|---|---|
| session reuse rate | 同 topic 任務中，至少 70% 可成功重用既有 session |
| mistaken reuse rate | 錯誤重用到不相關 session 的比例低於 5% |
| first stream latency | 首次 streaming 事件在可接受門檻內；目標 2 秒以內，不含 provider 波動 |
| reconnect success rate | client 中斷後可成功接回既有 session 的比例高於 95% |
| forced-new fallback rate | 因 session 無效而被迫改為新建 session 的比例持續下降 |

## 技術建議
建議以 Node.js / TypeScript 實作 orchestration layer，直接使用 OpenCode JS/TS SDK 與 Claude Code Agent SDK。這樣最容易處理長連線、事件串流與 JSON 結構，且與 OpenCode 官方 SDK 的型別導向用法一致[cite:128]。

部署上建議：
- OpenCode 作為獨立 daemon 常駐。
- Orchestrator 作為本機 sidecar service。
- Claude Code 透過 Agent SDK 或本地 command / bridge 呼叫 orchestrator。
- daemon 預設綁定本機地址，並以 process supervisor 維持存活[cite:142][cite:106]。

## 後續延伸
後續可考慮：
- session semantic search
- 自動摘要與 compact
- 多 repo session map
- PR / branch 自動分支 session
- 與 observability 平台整合
- 將 session tree 視覺化呈現給 Claude Code 使用者

## 結論
本產品的核心不是「如何讓 Claude Code 單次呼叫 OpenCode」，而是「如何把 OpenCode 變成一個可持續、可分支、可恢復的 delegated worker」。OpenCode 官方已具備 server、SDK、session、continue、resume、fork 與 daemon 化的能力；PRD 的關鍵價值在於把這些既有能力整合成清晰一致的 orchestration 規則，讓使用者同時擁有 session 重用與開新 session 的能力，並能在 Claude Code 中取得穩定的 streaming 體驗[cite:128][cite:142][cite:138][cite:131][cite:144]。

## Claude Code 整合補充
### 整合原則
Claude Code 端不應直接把 OpenCode 當成一次性 shell command 呼叫，否則很容易退化成「執行後一次性收斂結果」的模式，無法穩定保證中途持續輸出。較正確的方式是：以 Claude Code Agent SDK 作為主控代理執行層，並在自訂 bridge 程式中同時管理 Claude 的 streaming 與 OpenCode daemon 的事件串流[cite:151][cite:165][cite:128]。

Claude Agent SDK 官方明確支援即時串流輸出；只要在 TypeScript 設定 `includePartialMessages: true`，SDK 就會持續吐出 `stream_event` 訊息，其中 `content_block_delta` 且 `delta.type === "text_delta"` 的事件可直接用來顯示逐段文字輸出[cite:165]。因此，Claude Code 端可以保證自身有 token-level 的可見輸出；而 OpenCode 端則應透過 server-sent events 訂閱機制把工作進度持續推回 bridge，再由 bridge 轉寫成 Claude 端可理解的進度文字[cite:128]。

### 建議架構
建議架構如下：

1. Claude Code Agent SDK 作為主控層。
2. OpenCode daemon 作為外部 delegated worker。
3. Orchestrator / Bridge 作為兩者中間層，負責 session policy、事件轉譯與心跳輸出。
4. Claude Code 只與 bridge 溝通，由 bridge 決定要 reuse、new 或 fork 哪個 OpenCode session[cite:151][cite:128][cite:142]。

此設計的關鍵不是讓 Claude 直接讀 OpenCode 的內部 token，而是讓 bridge 把 OpenCode 的事件轉換成 Claude 持續可見的文字敘述，例如「OpenCode 已重用 session X」、「正在讀取 12 個檔案」、「已開始執行測試」、「目前卡在工具等待中」。這樣即使 OpenCode 當前沒有穩定 token 級輸出，也能保證 Claude transcript 持續有可追蹤的文字流[cite:165][cite:128]。

### 保證 stream 顯示的設計
若目標是「讓 Claude 方便追蹤」，重點不是只有 raw token streaming，而是要保證 transcript 不長時間沉默。Claude Agent SDK 的 partial message streaming 可直接輸出 Claude 本身的增量文字；OpenCode SDK 則提供即時事件串流能力，可監聽 session 的執行中事件[cite:165][cite:128]。

因此，bridge 必須實作兩層 streaming：
- **Claude layer streaming**：將 Claude Agent SDK 的 `stream_event` 寫到 stdout 或 UI，確保 Claude 自己的推理文本與工具呼叫可即時顯示[cite:165]。
- **OpenCode progress streaming**：將 OpenCode event stream 轉成人類可讀的進度訊息，持續餵給 Claude 或直接顯示在 UI，使 Claude 能觀察 delegated work 的進展[cite:128]。

### 最小可行實作模式
Bridge 可以採用以下模式：

1. Claude 接到任務後，先輸出一行明確狀態，例如「已接受任務，正在解析 session policy」。
2. Bridge 完成 session resolve 後，立刻輸出「已重用 session xxx」或「已建立新 session xxx」。
3. OpenCode daemon 一旦開始工作，bridge 訂閱事件流，將重要事件映射成文字，例如：
   - `status: planning` → `OpenCode: planning task...`
   - `tool_start: Read` → `OpenCode: reading files...`
   - `tool_start: Bash` → `OpenCode: running commands...`
   - `status: waiting` → `OpenCode: waiting on tool / provider...`
   - `status: completed` → `OpenCode: task complete.`
4. 若一段時間內沒有新事件，bridge 主動送出 heartbeat，例如每 2 至 5 秒輸出一次 `OpenCode: still running...`，避免 Claude transcript 長時間靜默。

這種 heartbeat 補償機制是保證「持續有 stream 文字顯示」的核心，即使底層 provider 在某些階段不產出 token，也不至於讓上層觀察者失去狀態感知[cite:165][cite:128]。

### Claude Code 端實作要求
Claude Code 端應使用 Agent SDK 的 streaming 模式，而非單次同步模式。官方文件指出 streaming input mode 是偏好的使用方式，且 output streaming 需透過 `includePartialMessages: true` 啟用，之後從 `stream_event` 擷取 `text_delta` 即可逐步顯示內容[cite:163][cite:165]。

TypeScript 範例模式如下：

```ts
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Delegate this task to OpenCode and keep me updated continuously.",
  options: {
    includePartialMessages: true,
    allowedTools: ["Bash", "Read", "Write", "Agent"]
  }
})) {
  if (message.type === "stream_event") {
    const event = message.event;
    if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
      process.stdout.write(event.delta.text);
    }
  }
}
```

這段保證 Claude 自身的增量文字可被持續顯示；真正 delegated 給 OpenCode 的進度，則由 bridge 額外寫成可見文字狀態，合併進同一條 transcript[cite:165]。

### 推薦的 bridge 行為契約
為了讓 Claude 真正「方便追蹤」，bridge 不應只在結束時回摘要，而應遵守以下契約：

- 任務接受後 500ms 內至少輸出一條狀態文字。
- 每個 session 決策步驟都必須輸出狀態文字。
- 每個工具開始 / 完成事件都必須輸出狀態文字。
- 若超過 5 秒沒有任何事件，必須輸出 heartbeat。
- 任務完成時必須輸出 final state 與 session_id。
- 任務失敗時必須輸出 error state、最後已知進度與可恢復 session_id。

這些文字本身就是一種「可觀測 stream」，比只依賴模型 token 更適合實務追蹤 delegated worker 的狀態。

### 建議輸出格式
建議 bridge 對 Claude 顯示標準化前綴，讓 transcript 更好讀：

```text
[orchestrator] resolving session policy...
[orchestrator] reusing session sess_123
[opencode] planning changes...
[opencode] reading auth module...
[opencode] running tests...
[opencode] still running...
[opencode] completed task in sess_123
```

此格式的好處是 Claude 可直接把這些文字當成最新上下文的一部分來理解，且人類使用者也能一眼判斷目前卡在哪個階段。

### Hooks 與輔助追蹤
Claude Agent SDK 支援 hooks，可在 SessionStart、PostToolUse、Stop 等節點做額外紀錄或插入輔助訊息，適合用來做 audit、狀態追蹤與 completion note[cite:page:1]。

此外，Claude Code subagent / hook 生態的最佳實務也指出，若想讓輸出可見，hook 應將追蹤資訊印到 STDOUT，而不是寫到不可見的 TTY；這有助於把額外狀態放進 Claude transcript 中[cite:167]。

### 驗收標準補充
新增以下驗收項：

- **AC-7 Claude streaming visible**：Claude Code 在任務執行期間，必須能顯示增量文字，而非只顯示最終結果[cite:165]。
- **AC-8 OpenCode progress visible**：當任務 delegated 給 OpenCode 時，bridge 必須能持續輸出進度文字，即使沒有最終完成結果也能知道目前狀態[cite:128]。
- **AC-9 Heartbeat guarantee**：若 OpenCode 超過 5 秒未產生新事件，系統必須自動輸出 heartbeat 訊息，確保 Claude transcript 持續可追蹤。
- **AC-10 Recoverable failure visibility**：任務失敗時，Claude transcript 內必須包含最後已知 session_id 與失敗點，便於 resume。
