收到,implementation 這步改用 OpenCode 來做,不再用 Claude subagent。之後我不會再為這個選擇跟你確認。

判斷依據:
- 這個 repo(bridge plugin)裡本來就有現成的橋接：`skills/opencode-bridge`(單次委派 OpenCode、回傳結構化 handoff report)和 `skills/opencode-subagent-driven-development`(包一層 superpowers 的 `subagent-driven-development` 執行迴圈,implementer 換成 OpenCode,spec-compliance / code-quality review gate 照舊保留)。
- 因為我們現在是「pipeline 跑到一半」,implementation 是 plan-execution 流程裡的下一步,不是單獨、臨時的委派請求,所以符合 `opencode-bridge` skill 裡 Step 0 寫的條件:「已經在一個 active 的 subagent-driven-development / executing-plans 流程裡被呼叫」→ 直接進 Step 1,不用再跳出來問你要不要走 standalone。
- 換句話說,review gate(spec 對齊、code quality 檢查)不會因為換成 OpenCode 而消失,只是「誰寫程式碼」從 Claude subagent 換成 OpenCode CLI。

接下來我會做的事:
1. 檢查 `~/.opencode-bridge/config.json` 是否存在且能解析(default model、fallback models、per-attempt/chain timeout、ping timeout)。如果沒有設定過,我會用建議預設值建立一份,不會為了這個逐項再問你。
2. 確認 `uv run .../dispatch.py` 呼叫 `opencode` CLI 這條路徑在 Bash 權限允許清單裡,避免每次都跳權限提示。
3. 用這個 OpenCode 路徑執行原本排定的 implementation 任務,拿回 done/failed/timed-out 狀態、變更檔案清單、實作摘要。
4. 沿用原本 superpowers 的 spec-compliance review 與 code-quality review 兩道關卡來驗收這次 OpenCode 產出的結果,跟原本用 Claude subagent 時一樣嚴格。

如果之後你想切回 Claude subagent,直接說一聲就好,我會照做,不用重新走一次選擇流程。
