## Pipeline Log Review：order-pipeline-quiet

**結論：這份 log 嚴重不足，無法用來驗證 pipeline 是否照 plan 執行，也無法用來 debug 任何一筆訂單。**

### Plan 要求 vs. 實際 log

Plan（`review-pipeline-logs-workspace/fixtures/order-pipeline/plan.md`）定義了 4 個步驟，每個步驟都應該有 start + completion/success 兩行 log，並帶有可 debug 的細節：

1. **Validate order** — 應該看到 `order validated`，含 order id、item count
2. **Charge payment** — 應該看到 `charge succeeded`，含 charge id、amount
3. **Update inventory** — 應該看到 `inventory updated`，含 SKU、decremented quantity
4. **Send confirmation email** — 應該看到 `confirmation email sent`，含 recipient address

但實際的 log（`review-pipeline-logs-workspace/fixtures/order-pipeline-quiet/run.log`）只有兩行：

```
2026-07-08T14:02:17Z processing order
2026-07-08T14:02:19Z done
```

### 發現的問題

- **4 個步驟的 log 全部缺失**：沒有任何一行提到 validate、charge、inventory、email，也沒有對應的 success 關鍵字（`order validated` / `charge succeeded` / `inventory updated` / `confirmation email sent`）。
- **沒有任何可追蹤欄位**：order id、item count、charge id、amount、SKU、quantity、recipient 全部沒有出現。如果這筆訂單出問題，完全無法回頭查是哪個步驟失敗、失敗在哪個環節。
- **無法判斷「done」代表什麼**：`done` 可能代表 4 個步驟都成功執行完，也可能只是外層 wrapper 印出的訊息、跟內部步驟是否真的執行完全脫鉤。目前的 log 無法區分「pipeline 真的照 plan 跑完 4 步」還是「某個步驟被跳過或失敗但外層仍印出 done」。
- 兩行 log 之間只間隔 2 秒，對於「驗證 + 收單 + 扣庫存 + 寄信」4 個外部呼叫來說時間上是說得通的，但這只是巧合式的佐證，不能替代真正的步驟級 log。

### 建議

這個 log 不符合 plan 中「Verification Expectations」的要求（每個步驟都要有 start/completion 且含除錯細節）。建議：
1. 在每個步驟的進入點與完成點都加上帶有 plan 指定關鍵字的 log 行（`order validated` / `charge succeeded` / `inventory updated` / `confirmation email sent`）。
2. 每行帶上對應的除錯欄位（order id、item count、charge id、amount、SKU、quantity、recipient）。
3. 在補齊 log 之前，這個 pipeline 目前無法通過任何形式的自動化或人工驗證——現有的兩行 log 只能證明「進來了、結束了」，證明不了中間 4 步是否真的正確執行。
