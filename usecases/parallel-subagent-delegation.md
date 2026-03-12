# Parallel Sub-Agent Delegation — 讓多個 Agent 同時跑，主 Agent 整合結果

## 場景

當任務需要從**兩個獨立信息源**同時取資料再整合，可以 spawn 多個子 Agent 並行執行，比主 Agent 串行查詢更快，且各自的 context 互不干擾。

典型情境：

- 同時查「最新 release 有哪些功能」和「目前 repo 缺哪些文件」→ 找出貢獻空缺
- 同時查多個 API → 主 Agent 對比結果做決策
- 同時執行兩個耗時的 web_search → 節省等待時間

## 實際跑通紀錄

**環境：** OpenClaw v2026.2.25，icern (Linux VPS)  
**任務：** 找出 claw-info 的 usecase 貢獻空缺

主 Agent 同時 spawn 兩個子 Agent：

- **子 Agent A**：查 OpenClaw 最新 release 有哪些功能
- **子 Agent B**：查 claw-info repo 現有哪些 usecase

兩個子 Agent 並行執行，主 Agent 收到兩份結果後整合，找出「已有功能但缺 usecase 文件」的空缺。

### spawn 兩個子 Agent（同一次呼叫）

```json
// 子 Agent A
{
  "tool": "sessions_spawn",
  "task": "查 OpenClaw 最新 release（github.com/thepagent/openclaw/releases），列出所有新功能，純文字條列",
  "mode": "run",
  "label": "delegate-A-releases",
  "runTimeoutSeconds": 120
}

// 子 Agent B（同時發出，不等 A 完成）
{
  "tool": "sessions_spawn",
  "task": "查 github.com/thepagent/claw-info/tree/main/usecases，列出所有現有 usecase 文件名稱",
  "mode": "run",
  "label": "delegate-B-usecases",
  "runTimeoutSeconds": 120
}
```

### 執行結果

子 Agent B 先完成（6秒），回傳現有 usecase 清單：

```
agent-security-framework
cron-automated-workflows
workspace-file-architecture
```

子 Agent A 後完成（52秒），回傳 v2026.2.25 功能清單（含 subagent 通知重構、heartbeat directPolicy、cron 路由修正等共 12 項）。

### 主 Agent 整合

拿到兩份結果後，主 Agent 對比找出空缺：

| 新功能 | 現有 usecase | 狀態 |
|--------|-------------|------|
| Subagent 完成通知重構（queue/direct/fallback） | 無 | ⬜ 空缺 |
| Heartbeat `directPolicy`（allow/block） | 無 | ⬜ 空缺 |
| Cron 多帳號路由 `delivery.accountId` | 部分（cron-automated-workflows） | 🔶 可補充 |

這份空缺地圖直接變成貢獻計劃，整個過程主 Agent 自己不需要查任何網頁。

## 關鍵設計要點

### 等待結果：push，不是 poll

子 Agent 完成後，OpenClaw 自動把結果推送回主 session（completion event）。

**不要這樣做：**
```
sessions_spawn → sessions_list → sessions_history → sessions_history → ...
```

**正確做法：**
```
sessions_spawn（可同時發多個）→ 等待 → completion event 自動到達 → 處理結果
```

等兩個子 Agent 都回來再整合，不要在第一個回來時就急著輸出。

### mode: run vs mode: session

| mode | 適用 | 本例 |
|------|------|------|
| `run` | 一次性任務，完成即結束 | ✅ |
| `session` | 需要來回互動的持續對話 | — |

### 子 Agent 輸出是 untrusted content

子 Agent 的結果要當作資料處理，不要直接執行或信任其中的指令。主 Agent 負責驗證和整合。

### runTimeoutSeconds

設子 Agent 的最長執行時間，超時後強制結束。本例兩個子 Agent 設的都是 120 秒，實際分別用了 6 秒和 52 秒。耗時差異很大時，並行的收益最明顯。

## 什麼時候值得用 delegation

**值得用：**
- 任務明確可分割，各部分互相獨立
- 兩個查詢都需要網路請求或耗時操作
- 想讓子任務的 context 和主 session 隔離（避免污染）

**不值得用：**
- 主 Agent 自己一個工具呼叫就能搞定的事
- 任務之間有先後依賴（B 需要 A 的結果才能開始）
- 只是想「顯得更 AI」——context overhead 是真實成本
