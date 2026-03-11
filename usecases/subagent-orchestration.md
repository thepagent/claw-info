# Sub-Agent Orchestration：背景任務委派實戰指南

> 讓 agent 派出分身處理耗時任務，自己繼續回應主人——不阻塞、不遺漏、不失控。

---

## TL;DR

- **核心問題**：耗時任務（coding、分析、部署）會阻塞 agent 回應，讓使用者等不到人
- **解法**：派出 sub-agent 在背景執行，主 agent 保持可用
- **三個關鍵**：正確 spawn → 不阻塞監控 → 可靠完成通知
- **最大陷阱**：`process poll` 長等待會凍結主 session，使用者訊息無法處理

---

## 什麼時候該用 Sub-Agent？

### ✅ 適合委派

| 場景 | 原因 |
|------|------|
| 建立新功能 / 重構程式碼 | 需要大量檔案操作，耗時 10-30 分鐘 |
| PR review + 修復 | 需要理解程式碼脈絡後修改 |
| 大型分析報告 | 需要讀取多個資料源後整合 |
| 多步驟部署流程 | 需要依序執行多個指令 |

### ❌ 不適合委派

| 場景 | 該怎麼做 |
|------|---------|
| 改一行 code | 直接用 `edit` 工具 |
| 讀檔案內容 | 直接用 `read` 工具 |
| 簡單查詢 | 直接回答 |
| 需要即時互動的任務 | 主 agent 自己做 |

**判斷標準**：預估超過 2 分鐘的任務才值得派 sub-agent。

---

## Spawn 模式比較

OpenClaw 提供多種方式啟動背景任務：

### 1. `sessions_spawn`（推薦：ACP / Thread 場景）

適合需要獨立 session 的任務，特別是 Discord thread-bound 場景。

```
# 以下為 tool call 示意
sessions_spawn(
  runtime: "acp",
  task: "在 /path/to/project 實作 feature X，完成後跑測試",
  thread: true,        # 綁定 Discord thread
  mode: "session"      # 持久 session，可後續互動
)
```

**優點**：完成後自動回報、支援 thread 綁定、可追蹤
**適用**：coding 任務、需要使用者後續追問的場景

### 2. `exec` + PTY（推薦：CLI 工具場景）

適合直接呼叫 CLI 工具（如 `claude` CLI）在背景執行。

```
# 以下為 tool call 示意
exec(
  command: "claude -p '實作 feature X' --output-format stream-json",
  workdir: "/path/to/project",
  background: true,
  timeout: 1800,
  yieldMs: 10000      # 等待初始輸出後轉入背景
)
```

**優點**：直接控制 CLI 參數、可即時看輸出
**適用**：已有 CLI 工具的場景

### 3. tmux + Supervisor（推薦：長時間任務）

適合需要持久化、可恢復、可中途檢查的任務。

```bash
claude-supervisor run "task-name" /path/to/project \
  "實作 feature X，完成後跑測試" \
  --model sonnet --timeout 30
```

**優點**：tmux session 持久化、斷線可恢復、有結構化日誌
**適用**：超過 30 分鐘的大型任務、需要中途檢查進度的場景

---

## ⚠️ 最大陷阱：`process poll` 阻塞

這是 sub-agent 操作最常見的錯誤：

```
# ❌ 錯誤：長時間 poll 會阻塞主 session
exec(command: "claude -p '...'", background: true)
process(action: "poll", sessionId: "xxx", timeout: 300000)  # 等 5 分鐘
# → 這 5 分鐘內使用者發的任何訊息都無法處理！
```

```
# ✅ 正確：spawn 後立即回覆，靠通知機制得知完成
exec(command: "claude -p '...'", background: true)
# 立即告知使用者：「已派出分身處理，完成後會通知」
# 不 poll，靠完成通知機制
```

**原理**：agent 在執行 tool call 時無法處理新訊息。`process poll` 超過幾秒就會讓使用者感覺 agent 失去回應。

---

## 完成通知機制

Sub-agent 完成後，如何讓主 agent 知道？有三種策略：

### 策略 1：CLI System Event（推薦）

在 sub-agent 的 prompt 尾巴加上完成通知指令：

```
# prompt 尾巴加上（以下為示意，實際語法請以 openclaw system event --help 為準）：
完成後執行：openclaw system event --text "Done: [任務摘要]" --mode now
```

這會觸發主 session 的 system event，agent 會在下次喚醒時看到。

### 策略 2：外部監控腳本

派出 sub-agent 後，同時啟動一個監控腳本：

```bash
# 監控 sub-agent process，完成後發通知
# $PID 來自 exec 背景啟動後回傳的 process ID（或從 process list 查詢）
(while ps -p $PID > /dev/null 2>&1; do sleep 30; done; \
 openclaw message send --channel telegram --target <user_id> \
   --message "✅ 任務完成：[摘要]") &
```

**優點**：不依賴 sub-agent 記得發通知（機制 > 自律）
**適用**：關鍵任務，不能漏報

### 策略 3：Heartbeat 被動檢查

在 HEARTBEAT.md 的檢查清單中加入：

```markdown
- [ ] 檢查是否有背景任務完成 → `process list` + `git log --since="1 hour ago"`
```

**優點**：定時自動檢查，不需要額外機制
**缺點**：有延遲（取決於 heartbeat 間隔）

### 實戰建議：組合使用

```
策略 1（CLI event）  → 正常路徑，sub-agent 主動回報
策略 2（監控腳本）    → 備援路徑，防止 sub-agent 忘記或異常退出
策略 3（heartbeat）  → 最終兜底，定時掃描
```

---

## Timeout 設定原則

| 任務類型 | 建議 timeout | 說明 |
|---------|-------------|------|
| 小型修改（< 5 檔案） | 600s (10 min) | 通常 3-5 分鐘完成 |
| 中型功能（5-20 檔案） | 1800s (30 min) | 預設值，適合大部分任務 |
| 大型重構 / 新專案 | 3600s (60 min) | 需要大量探索和修改 |
| 分析報告 | 1200s (20 min) | 讀取 + 整理 + 撰寫 |

**最低門檻**：timeout 絕不低於 600 秒（10 分鐘），即使是小型任務。**推薦預設**：1800 秒（30 分鐘），寧可多等，不要因為 timeout 導致任務中斷後需要重做。

---

## 跨頻道回報

如果系統有多個頻道（Telegram、Discord 等），回報應遵循：

**在哪個頻道派的任務，就在哪個頻道回報。**

```
# Telegram 派出的任務 → 回報到 Telegram
openclaw message send --channel telegram --target <user_id> --message "✅ 完成"

# Discord 特定頻道派出的 → 回報到該頻道
openclaw message send --channel discord --target channel:<channel_id> --message "✅ 完成"
```

這避免使用者在 A 頻道下指令，卻要去 B 頻道找結果。

---

## 完整工作流範例

以下是一個完整的 sub-agent 委派流程：

```
使用者：「幫我在 project-x 實作登入功能」

Agent 思考：
1. 這是中型功能，需要多個檔案，預估 15-20 分鐘 → 適合委派
2. 使用者在 Discord #程式開發 頻道 → 回報到同頻道

Agent 執行：
1. spawn sub-agent（timeout: 1800s, prompt 包含完成通知指令）
2. 啟動監控腳本（備援通知）
3. 立即回覆使用者：
   「已派出分身處理登入功能實作，預估 15-20 分鐘。
    完成後我會在這裡回報。有其他事可以繼續跟我說！」

[15 分鐘後]

System Event: "Done: 實作登入功能，新增 3 個檔案，測試全過"

Agent 回覆：
「✅ 登入功能實作完成！
 - 新增：auth.ts, login.vue, auth.test.ts
 - 測試：3/3 通過
 - Commit: abc1234
 需要我說明實作細節嗎？」
```

---

## Anti-Patterns

### ❌ 串列等待多個 sub-agent

```
# 錯誤：一個一個等，總時間是所有任務的加總
spawn task A → poll 等完成 → spawn task B → poll 等完成
```

```
# 正確：同時派出，各自完成後通知
spawn task A（帶完成通知）
spawn task B（帶完成通知）
→ 兩個平行執行，各自回報
```

### ❌ 不告知使用者就派 sub-agent

```
# 錯誤：使用者不知道發生什麼，以為 agent 在發呆
[靜默 spawn sub-agent]
[20 分鐘後才回覆]
```

```
# 正確：立即告知
「這個任務比較大，我派一個分身在背景處理，預估 15 分鐘。
 你可以繼續跟我聊其他事！」
```

### ❌ 在核心工作區 spawn coding agent

```
# 錯誤：coding agent 可能修改 agent 自己的設定檔
spawn coding agent in ~/agent-workspace/

# 正確：只在專案目錄中工作
spawn coding agent in ~/projects/my-app/
```

---

## 監控與調試

### 檢查 sub-agent 狀態

```
# 列出所有 sub-agent
subagents(action: "list")

# 查看特定 session 歷史
sessions_history(sessionKey: "...")

# 緊急終止
subagents(action: "kill", target: "...")
```

### 常見問題排查

| 問題 | 原因 | 解法 |
|------|------|------|
| Sub-agent 沒回報 | prompt 沒帶完成通知指令 | 加上 `openclaw system event` 指令 |
| 任務中途停止 | timeout 太短 | 調高 timeout，最少 1200s |
| 使用者等不到回應 | 用了 `process poll` 長等待 | 改用通知機制，不 poll |
| 結果出現在錯頻道 | 沒指定回報頻道 | 在哪派就在哪報 |
| Coding agent 改了設定檔 | 在 agent workspace 執行 | 只在專案目錄中 spawn |

---

## 總結

| 原則 | 說明 |
|------|------|
| **Spawn 後立即回覆** | 不讓使用者等，告知任務已派出 |
| **通知靠機制不靠記憶** | CLI event + 監控腳本 + heartbeat 三層保障 |
| **不 poll 等結果** | `process poll` 超過幾秒就會阻塞主 session |
| **Timeout 寧長勿短** | 最少 1200s，中斷重做的成本遠大於多等幾分鐘 |
| **哪派哪報** | 跨頻道回報會讓使用者找不到結果 |
| **先告知再動手** | 透明度建立信任 |
