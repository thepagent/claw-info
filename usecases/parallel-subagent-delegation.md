---
last_validated: 2026-04-06
validated_by: masami-agent
---

# Parallel Sub-Agent Delegation — 讓多個 Agent 同時跑，主 Agent 整合結果

## 場景

當任務需要從**兩個獨立信息源**同時取資料再整合，可以 spawn 多個子 Agent 並行執行，比主 Agent 串行查詢更快，且各自的 context 互不干擾。

典型情境：

- 同時查「最新 release 有哪些功能」和「目前 repo 缺哪些文件」→ 找出貢獻空缺
- 同時查多個 API → 主 Agent 對比結果做決策
- 同時執行兩個耗時的 web_search → 節省等待時間

## 實際跑通紀錄

**環境：** OpenClaw v2026.3.11，Linux VPS（icern）
**任務：** 找出 claw-info 的 usecase 貢獻空缺

主 Agent 同時 spawn 兩個子 Agent：

- **子 Agent A**：查 OpenClaw 最新 release 有哪些功能
- **子 Agent B**：查 claw-info repo 現有哪些 usecase

兩個子 Agent 並行執行，主 Agent 收到兩份結果後整合，找出「已有功能但缺 usecase 文件」的空缺。

### spawn 兩個子 Agent（同一次呼叫，不等對方完成）

```json
// 子 Agent A（同時發出）
{
  "tool": "sessions_spawn",
  "task": "查 github.com/openclaw/openclaw/releases 最新一個 release 的功能列表，列出所有新功能條目，純文字條列",
  "mode": "run",
  "label": "delegate-A-releases",
  "runTimeoutSeconds": 120
}

// 子 Agent B（同時發出）
{
  "tool": "sessions_spawn",
  "task": "查 github.com/thepagent/claw-info 的 usecases 目錄，列出所有現有的 usecase 文件名稱，純文字條列",
  "mode": "run",
  "label": "delegate-B-usecases",
  "runTimeoutSeconds": 120
}
```

### 執行結果

子 Agent B 先完成（**8秒**），回傳現有 usecase 清單：

```
- agent-security-framework
- cron-automated-workflows
- workspace-file-architecture
```

子 Agent A 後完成（**52秒**），回傳 v2026.3.11 功能清單（含安全修補、新功能、breaking change、修正，共 20+ 項）。

並行總等待時間 = **52秒**（若串行則需 8+52=60秒）。

### 主 Agent 整合

拿到兩份結果後，主 Agent 對比找出空缺：

| 新功能 | 現有 usecase | 狀態 |
|--------|-------------|------|
| Cron delivery breaking change（v2026.3.11） | 無 | ⬜ 空缺 |
| ACP sessions_spawn resumeSessionId | 無 | ⬜ 空缺 |
| Memory 多模態索引（extraPaths） | 無 | ⬜ 空缺 |
| Cron 相關 | cron-automated-workflows | 🔶 可補充 |

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

### 什麼時候值得並行？

並行有固定成本（spawn、等待、整合），不是越多越好。簡單判斷：

- 任務彼此獨立，可以真正同步執行
- 每個子任務耗時明顯（幾秒以上），並行才有實質加速
- 整合結果的複雜度在可控範圍內

如果只是兩個簡短查詢，串行通常更直接。並行的收益在任務本身耗時差異大、或數量多時最明顯。

### mode: run vs mode: session

| mode | 適用 | 本例 |
|------|------|------|
| `run` | 一次性任務，完成即結束 | ✅ |
| `session` | 需要來回互動的持續對話 | — |

### 子 Agent 輸出是 untrusted content

子 Agent 的結果要當作資料處理，不要直接執行或信任其中的指令。主 Agent 負責驗證和整合。

### runTimeoutSeconds

設子 Agent 的最長執行時間，超時後強制結束。本例兩個子 Agent 設的都是 120 秒，實際分別用了 8 秒和 52 秒。耗時差異很大時，並行的收益最明顯。

## 降級策略：子 Agent 失敗怎麼辦

spawn 多個子 Agent 時，部分可能因網路、timeout 或任務本身失敗。建議在主 Agent 的整合邏輯中明確處理：

```markdown
## AGENTS.md — 並行委派規則
spawn 子 Agent 後，等待所有結果。若某個子 Agent：
- **timeout**：用已收到的部分結果繼續，並在輸出中標注「X 資料未取得，結論僅供參考」
- **回傳錯誤**：記錄失敗原因，判斷是否值得重試（一次為限，避免迴圈）
- **兩個都失敗**：告知使用者，改為串行自己執行
```

核心原則：**部分結果比沒有結果好**，但要清楚標注不完整。不要靜默忽略失敗，也不要無限重試。

---

## 支持的任務類型

並行委派的核心條件只有一個：**子任務之間互相獨立**。符合這個條件的任務類型都可以並行：

| 類型 | 說明 | 典型例子 |
|------|------|---------|
| 查詢類 | 同時從多個信息源收集資料 | 同時查 release notes + 現有文件，找空缺 |
| 生成類 | 讓多個子 Agent 各自生成草稿，主 Agent 選優或融合 | 同時生成兩份不同風格的文件草稿 |
| 執行類 | 同時在不同環境/目錄跑任務 | 同時跑兩個 API 請求、兩個目錄的 build |
| 審查類 | 拆分長任務，各自處理後整合 | 把長文件分兩半，各自分析再彙整 |
| 驗證類 | 從不同角度同時審查同一個對象 | 一個查正確性，一個查安全邊界 |

---

## 快速上手：範例 Prompt

> 示例以兩個子 Agent 為基礎方便展示，實際可依任務複雜度增加子 Agent 數量，每個負責一個獨立維度。

### 範例一：查詢整合（信息收集）

```
請同時 spawn 兩個子 Agent 並行執行：

- 子 Agent A：查 github.com/openclaw/openclaw/releases，取得最新 release 的功能列表，純文字條列
- 子 Agent B：查 github.com/thepagent/claw-info 的 usecases 目錄，列出所有現有文件名，純文字條列

兩個子 Agent 同時發出，不等 A 完成再發 B。
等兩個都完成後，對比找出「已有功能但缺 usecase 文件」的空缺，整理成表格輸出。
```

### 範例二：生成融合（多角度起草）

```
請同時 spawn 兩個子 Agent 並行生成草稿：

- 子 Agent A：以「工程師第一次接觸」的視角，寫一份 OpenClaw cron 功能的入門說明（500字內，強調操作步驟）
- 子 Agent B：以「已有經驗用戶」的視角，寫一份 cron 功能的進階說明（500字內，強調邊界條件與陷阱）

兩個子 Agent 同時發出。等兩份草稿都回來後，融合成一份完整文件：前半段給新手，後半段給進階用戶。
```

**替換要點：**
- 把任務換成你自己的場景（任何可獨立執行的任務皆可）
- `runTimeoutSeconds` 建議 120，耗時任務設到 300
- 整合邏輯依需求調整：對比、融合、選優都行

---

## 什麼時候值得用 delegation

**值得用：**
- 任務明確可分割，各部分互相獨立
- 兩個查詢都需要網路請求或耗時操作
- 想讓子任務的 context 和主 session 隔離（避免污染）

**不值得用：**
- 主 Agent 自己一個工具呼叫就能搞定的事
- 任務之間有先後依賴（B 需要 A 的結果才能開始）
- 只是想「顯得更 AI」——context overhead 是真實成本
