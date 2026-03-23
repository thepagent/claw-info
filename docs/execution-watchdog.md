# OpenClaw Execution Watchdog：Agent 執行驗證監工系統設計提案

> **狀態**：Ready for Review（MVP 已在 icern VPS 實測驗證）
> **作者**：wangyuyan-agent · claude
> **日期**：2026-03-20
> **適用版本**：OpenClaw ≥ 2026.3.7（需要 additive plugin hooks）
> **相關 Issue**：[openclaw/openclaw#40082](https://github.com/openclaw/openclaw/issues/40082)
> **實現**：[claw-watchdog](https://github.com/wangyuyan-agent/claw-watchdog)（Plugin 代碼）

---

## 1. 問題定義

當人類委派 OpenClaw agent 執行任務時，agent 可能聲稱完成了任務但實際上未執行。

典型場景：用戶說「查一下今天的天氣」，agent 回覆「對不起，連不上查詢天氣的網站」，但實際上網站是通的——agent 根本沒有發出任何網路請求。

這不是假設問題。OpenClaw Issue #40082 記錄了完全相同的症狀：

> "agents sometimes respond with placeholder text like: 'Still planning to check — let me do that now. One sec. Let me actually check now instead of just saying I will.' ... Users lose trust because OpenClaw sounds like it is working while not actually completing work."

現有的 OpenClaw 安全/監控機制（exec approvals、sandbox、watchdog）解決的是**權限控制和進程健康**問題，而非**執行真實性驗證**問題。目前沒有任何機制能夠獨立驗證 agent 是否真的去做了它聲稱做的事。

### 當前實作狀態

| 功能 | 狀態 |
|------|------|
| Hook payload 結構確認（probe 實測） | ✅ 已驗證 |
| L0 攔截真實偷懶場景 | ✅ 已驗證 |
| L1b 誤報 bug 發現並修復 | ✅ 已驗證 |
| Plugin 部署於 OpenClaw 實例 | ✅ 已實作，持續運行中 |
| L1a verb_tool_map.yaml 規則查表 | ⏳ Phase 2 |
| 待驗證隊列（多輪任務） | ⏳ Phase 2 |
| L2 Gemini Flash 語義判斷 | ⏳ Phase 2 |
| L3 獨立重複驗證 | ⏳ Phase 3 |

---

## 2. 核心設計哲學

### 憲法性原則

**不信任 agent 的自我報告。**

所有設計選擇都是這個原則的推論：

- 讀 `.jsonl` 而不讀 agent 的文字回覆作為執行證據
- 規則層不問 agent「你用了什麼工具」
- 告警由監工觸發，不由主 agent 發出
- 監工對主 agent 的執行流程零干預

### 設計原則

| 原則 | 含義 |
|------|------|
| 非干預式 | 監工可以被系統知道存在，但不改變主 agent 的任何行為、不影響任何執行結果 |
| 分層短路 | 大多數問題在成本最低的層攔截，只有複雜問題才往高成本層走 |
| 確定性信任錨點 | L0 和 L1 是純程序規則，零 LLM 依賴，行為完全可審計 |
| 平滑遷移 | MVP 做成 plugin，將來可無損抽出為獨立進程 |

---

## 3. 技術前提驗證

在設計之前，以下假設已全部驗證通過：

| 假設 | 狀態 | 說明 |
|------|------|------|
| `agent_end` hook（additive） | ✅ | agent loop 完成後觸發，可拿到 final message list 和 run metadata |
| `after_tool_call` hook（additive） | ✅ | 每次 tool call 後觸發，包含 tool name、params、result |
| `message_received` hook（additive） | ✅ | 收到 user 消息時觸發 |
| 以上 hooks 均不佔 slot | ✅ | 與 lossless-claw 等任何 ContextEngine 完全相容 |
| `session.jsonl` 由 gateway 寫入 | ✅ | agent 無法篡改自己的 session transcript |
| Plugins 與 gateway 同進程執行 | ✅ | 無需額外 IPC，但意味著配置文件需額外保護 |

**關鍵發現：`afterTurn` 不可用。** 它屬於 ContextEngine slot 的 lifecycle hook，slot 是排他性的（一次只能有一個 ContextEngine）。使用 `afterTurn` 會與 lossless-claw 等插件衝突。`agent_end`（additive hook）是正確的觸發點。

**Hook payload 已確認（2026-03-20，icern VPS 實測）：**

```
after_tool_call:
  toolName: string, params: object, result: { content: [{type, text}], details },
  error: undefined|object, durationMs: number, runId: string, toolCallId: string

message_received:
  from: string ("telegram:6276804274"), content: string, timestamp: number, metadata: object

agent_end:
  messages: object[] (role + content), success: boolean, error: undefined|object, durationMs: number
```

**⚠️ 無統一 sessionId 字段。** 三個 hook event 中均無 `sessionId`。`after_tool_call` 有 `runId`，`message_received` 有 `from`，`agent_end` 均無。MVP 使用 `from`（channel:userId）做 state bucket key。

---

## 4. 系統架構

### 4.1 總覽

```
用戶 ──派發任務──▶ 主 Agent (OpenClaw)
                         │
                   [執行過程]
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
 after_tool_call    message_received      agent_end
 (每次 tool call)   (user 本輪指令)     (本輪結束信號)
    │                    │                    │
    └────────────────────┼────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Execution Watchdog │
              │  Plugin             │
              │                     │
              │  in-memory state:   │
              │  turnState: Map     │
              │    <from> → {       │
              │      tools[]        │
              │      instruction    │
              │    }               │
              │  pending_queue: Map │
              │                     │
              │  判定邏輯：           │
              │  L0 → L1a → L1b    │
              │      → L2(async)   │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  告警通知             │
              │  Telegram / Webhook │
              └─────────────────────┘
```

### 4.2 Hook 綁定

```
監工 Plugin（additive hooks，不佔任何 slot）
│
├─ after_tool_call
│   → 以 lastReceivedFrom 定位 state bucket
│   → 記錄 tool call 到 turnState[from].tools[]
│   → 數據：toolName, params, result, runId, durationMs
│
├─ message_received
│   → 以 event.from 定位 state bucket（更新 lastReceivedFrom）
│   → 記錄本輪 user message（event.content）到 turnState[from].instruction
│   → 清空上一輪 tools[]（新一輪開始）
│   → 判定配對原則：「本輪 user message + 本輪 tool calls」
│
└─ agent_end（核心觸發點）
    → 以 lastReceivedFrom 定位 state bucket
    → 從 event.messages 提取 assistant 回覆文本
    → 觸發 L0 + L1 判定引擎
    → 處理 pending_verification_queue
    → 從 turnState Map 中刪除對應 entry
```

### 4.2.1 Session 隔離

Plugin 是 gateway 進程的單例，所有 session 共享同一個 plugin 實例。OpenClaw 支持多 session 並發——heartbeat session、主對話 session、subagent session 可以同時執行。**in-memory state 必須以 Map 組織，不能用裸變量。**

**⚠️ 無統一 sessionId。** 三個 hook event 中均無 `sessionId` 字段。MVP 使用 `from`（channel:userId，如 `"telegram:6276804274"`）做 state bucket key。`message_received` 有 `from` 字段；`after_tool_call` 和 `agent_end` 無 `from`，通過 `lastReceivedFrom` 橋接。

```typescript
interface TurnState {
  tools: ToolCallRecord[];
  instruction: string;
  from: string;
}

// ✅ 正確：按 from 隔離
const turnState = new Map<string, TurnState>();
let lastReceivedFrom: string = '';  // 橋接 message_received → agent_end

// ❌ 錯誤：裸變量，多 session 並發時互相污染
// let currentTurnTools: ToolCallRecord[] = [];
```

**⚠️ 已知限制 1：同一用戶的並發 run（Line 163）。** `from` 是用戶維度，不是 run 維度。同一用戶同時觸發多個 run（webhook 回呼、cron 任務、主對話並發）時，tool call 記錄會混入同一個 bucket。根本解法是 `from + runId` 組合 key，但 `message_received` 和 `agent_end` 沒有 `runId` 字段，需要通過 `after_tool_call`（有 `runId`）建立 `from → active runId` 映射表。此映射列為 **Phase 2 第一優先級**。

**⚠️ 已知限制 2：並發衝突的量化可見性。** MVP 在 audit log 中記錄每次 from-switch 降級事件（event type: `FROM_SWITCH_DEGRADED`），可通過 `grep FROM_SWITCH_DEGRADED audit.log | wc -l` 量化命中率。配置中預留 `useRunIdMapping: boolean` 旗標（默認 false），Phase 2 實現後用戶可選擇啟用。

**防呆策略（降級機制）**：當短時間內（3 秒）`from` 在不同來源間切換時，監工降級為「僅審計不告警」。降級時：
- 仍寫入 audit log，標記 event type `FROM_SWITCH_DEGRADED`，便於搜索和匯總
- 不靜默丟棄——真正的偷懶事件如果落在降級窗口，會在 audit log 中留痕，人類可事後 review
- Phase 2 的 `from + runId` 映射啟用後，此降級機制可被替代

### 4.3 數據來源

| 數據 | 主要來源 | 備用來源 |
|------|---------|---------|
| Tool call 記錄 | `after_tool_call` hook event | `session.jsonl` |
| User 本輪指令 | `message_received` hook event（每輪更新） | `session.jsonl` |
| Assistant 回覆文本 | `agent_end` final message list | `session.jsonl` |
| 完整上下文/回溯審計 | — | `session.jsonl`（只讀） |

設計原則：hook event 是主要數據通道（實時、結構化）；`.jsonl` 是備用數據源和審計依據。

---

## 5. 判定邏輯：四層遞進

每層只問自己層的問題，不越界。命中即止，不往下走。

### L0：結構性缺失檢測

```
成本：~0（純字符串匹配，無 LLM）
觸發：agent_end

條件：
  assistant 回覆文本中出現完成聲明詞
  （「已完成」「已發送」「已查詢」「搜索結果」「找到了」
    「結果如下」「已經」「done」「sent」「found」...）
  + 本輪 current_turn_tools[] 為空（零 tool call）
  + 聲明詞不處於否定語境中
    （「尚未完成」「我還沒發送」「not yet sent」不觸發）
    否定詞窗口：聲明詞前 6 個字符（中文）/ 30 個字符（英文）
    否定詞表：未/沒/沒有/尚未/還沒/無法/not/never/unable...

動作：
  → 直接告警，不往下走
```

**設計決策：L0 只讀 assistant 的文字做字符串比對，不試圖理解 user 指令的「意圖」。** 意圖判斷本身需要語言理解，會破壞 L0 作為純程序信任錨點的性質。意圖分析由 L1a 負責。否定語境排除同樣是純字符串操作，不引入 LLM，保持 L0 的確定性。

### L1a：Verb → Tool 合理性檢測

```
成本：極低（YAML 查表 + 關鍵詞匹配，無 LLM）
觸發：L0 通過後

流程：
  1. 從本輪 user 指令（current_turn_instruction）中提取行動 verb（關鍵詞匹配 + 同義詞表）
  2. 查 verb_tool_map.yaml 獲取期望的 tool 類型
  3. 比對 current_turn_tools[] 中是否包含期望的 tool 類型

條件：
  verb 匹配成功 + 期望的 tool 類型在 current_turn_tools[] 中不存在

動作：
  → 放入 pending_verification_queue（處理多輪任務）
  → 或直接告警（如果 session 已結束）

未匹配的情況：
  → L1a 無意見，放行給 L1b / L2
```

**`verb_tool_map.yaml` 示例：**

```yaml
# 行動動詞 → 期望的 tool 類型
# 人工維護，chmod 444，部署在 workspace 之外

verb_mappings:
  查: [web_fetch, web_search, memory_search]
  搜: [web_fetch, web_search]
  找: [web_fetch, web_search, read]
  發: [message]
  發送: [message]
  寫入: [write, edit]
  提交: [exec]
  下載: [web_fetch, exec]
  刪除: [exec, write]

# 同義詞表：自然語言 → 標準 verb
synonyms:
  冷不冷: 查
  帶傘: 查
  天氣: 查
  weather: 查
  send: 發
  search: 搜
  write: 寫入
  delete: 刪除
```

### L1b：Tool Call 序列內部一致性檢測（反向匹配）

```
成本：極低（字符串比對，無 LLM）
觸發：與 L1a 並行

流程：
  1. 掃描 assistant 回覆文本中的聲明詞
  2. 檢查 current_turn_tools[] 是否包含對應的 tool call

規則示例：
  - assistant 說「已發送」→ 檢查有無 message_send / message tool call
  - assistant 說「搜索結果」→ 檢查有無 web_search / web_fetch tool call
  - assistant 說「已寫入」→ 檢查有無 write / edit tool call
  - assistant 說「已刪除」→ 檢查有無 exec / delete tool call

條件：
  聲明詞存在 + 對應 tool call 不存在

動作：
  → 告警
```

**L1b 的優勢：不需要理解 user 的自然語言，只需要檢查 agent 的聲明與行為之間的一致性。** 這是純確定性檢測。

**`claim_tool_map.yaml` 示例：**

```yaml
# 聲明詞 → 期望的 tool 類型（用於 L1b 反向匹配）
# 只列「過去式確認詞」，不列推薦詞/建議詞（見 Anti-pattern 段落）
# 人工維護，chmod 444，部署在 workspace 之外

claim_mappings:
  已發送: [message]
  已寄出: [message]
  sent: [message]
  搜索結果: [web_search, web_fetch]
  已查詢: [web_search, web_fetch, memory_search]
  已完成: []          # 空表示任何 tool call 均可，但至少要有一個
  已寫入: [write, edit]
  已刪除: [exec, write]
  結果如下: [web_search, web_fetch, read, memory_search]
  找到了: [web_search, web_fetch, read, memory_search]
  done: []
  found: [web_search, web_fetch, read, memory_search]
```

### L2：語義判斷

```
成本：中（Gemini 2.5 Flash，異步後台）
觸發：L0 + L1 均通過後

流程：
  1. 將 user 指令、tool call 記錄、assistant 回覆打包
  2. 發送給 Gemini Flash，問：
     「以下是 agent 收到的任務、調用的工具、和返回的結果。
       結果是否合理回應了任務？有無明顯的邏輯不一致？」
  3. 收到判斷結果

適用場景：
  - Tool call 類型正確，但返回值與任務不相關
  - 查了天氣但返回 404 / 空內容 / 無關頁面
  - 發了消息但 target 不是用戶指定的人

動作：
  → 告警 + 附上 Flash 的判斷理由
```

### L3：獨立重複驗證（不在 MVP 範圍內）

```
成本：高
觸發：高風險任務 / 用戶明確標記需驗證

流程：
  監工自己重複執行同一個查詢，對比結果是否一致

TODO：
  - 定義「高風險任務」的標準
  - 設計結果比對的容差機制
  - 成本控制策略
```

---

## 6. 多輪任務處理

### 問題

用戶說「查天氣然後發給 Alice」，agent 可能在第一輪查天氣，第二輪才發消息。如果只看單輪，L1 會在第一輪結束時誤報「任務含'發'但沒有 message tool call」。

### 配對原則

**每輪獨立配對**：監工的判定單位是「本輪 user message + 本輪 tool calls」，不是把某一條 user message 對到整個 session 的所有 tool calls。`message_received` 記錄每一輪的 user 指令，`agent_end` 觸發後用本輪指令 + 本輪 tool calls 做判定，然後清空。

但這帶來一個問題：用戶在一條消息裡包含多個動作（「查天氣然後發給 Alice」），agent 可能跨輪完成。這就需要待驗證隊列。

### 解法：待驗證隊列

```python
# 極簡待驗證隊列（in-memory）
pending = {}  # from → {required_tools: set, deadline: timestamp, context: str}

# agent_end 觸發時：
# 1. L1 檢測到缺少某個期望的 tool call
#    → 不立即告警，放入 pending
#    → pending[from] = {
#        required_tools: {"message"},
#        deadline: now + 5min,  # 或 3 個 assistant turn 後
#        context: "用戶要求發送天氣給 Alice"
#      }
#
# 2. 後續 agent_end 觸發時，先檢查 pending：
#    → 本輪 tool calls 包含 pending 要求的 tool 類型？
#    → 是 → 從 pending 移除，任務正常完成
#    → 否 → 繼續等待
#
# 3. deadline 到了仍在 pending：
#    → 觸發告警
```

**Deadline 建議**：每個 assistant turn 後最多等 3 輪，或 5 分鐘，先到先觸發。

---

## 7. 通知層

### 即時告警

L0 / L1 命中時，通過 OpenClaw 自帶的 message tool 發送 Telegram 通知：

```
⚠️ 執行驗證告警

任務：查一下今天北京的天氣
Agent 回覆：「查詢結果顯示，北京今天晴轉多雲，氣溫 15-22°C」
命中聲明詞：「查詢結果」（COMPLETION_CLAIMS 列表中）
檢測層級：L0 — 完成聲明「查詢結果」但零 tool call
期望 tool：（任意，至少一個）
實際 tool calls：（無）
建議：手動確認或要求 agent 重試

Session (from)：telegram:6276804274
時間：2026-03-20 14:32:08
```

告警欄位說明：
- **命中聲明詞**：觸發檢測的關鍵詞（L1b 時為具體聲明詞，L0 時說明路徑）
- **期望 tool**：根據規則庫期望出現的 tool 類型（L1b 適用）
- **實際 tool calls**：本輪真實發生的 tool 調用列表
- **Session (from)**：channel:userId，可直接定位 session

### 異步報告

L2 判定結果寫入審計日誌文件（`~/.openclaw/watchdog/audit.log`），人類可定期查看。

### OpenFeedback / Webhook

預留 webhook 通知接口，支持接入 OpenFeedback 或任何自定義通知系統。

---

## 8. 部署方案

### MVP：OpenClaw Plugin

```
~/.openclaw/
├── extensions/
│   └── execution-watchdog/       # Plugin 目錄
│       ├── openclaw.plugin.json  # Plugin manifest
│       ├── index.ts              # Hook 註冊 + 判定引擎
│       └── package.json
│
# 以下文件部署在 workspace 之外，chmod 444
/etc/openclaw-watchdog/           # 或其他受保護路徑
├── verb_tool_map.yaml            # L1a 規則庫
├── claim_tool_map.yaml           # L1b 規則庫
└── alert_config.yaml             # 通知配置
```

**配置：**

```json
// openclaw.json
{
  "plugins": {
    "entries": {
      "execution-watchdog": {
        "enabled": true,
        "config": {
          "rulesPath": "/etc/openclaw-watchdog/",
          "alertChannel": "telegram",
          "l2Enabled": false,
          "l2Model": "gemini-2.5-flash",
          "pendingTimeoutMinutes": 5,
          "pendingMaxTurns": 3
        }
      }
    }
  }
}
```

### 遷移路徑：獨立進程

如需更強隔離，L0/L1 規則引擎設計為無狀態純函數庫，可直接抽出為獨立進程：
- 監聽 `.jsonl` 文件變更（`fs.watch`）
- 獨立的告警通道（不依賴 OpenClaw message tool）
- 獨立的進程權限和用戶

---

## 9. 安全考量

| 風險 | 緩解措施 |
|------|---------|
| Agent 通過 exec 修改規則文件 | `chmod 444` + 部署在 workspace 之外 |
| Agent 意識到監工存在並嘗試繞過 | 監工只讀系統級數據（hook events），不依賴 agent 配合 |
| session.jsonl 被篡改 | Gateway 寫入，agent 無修改權限 |
| 監工 plugin 自身被 prompt injection | Plugin 不接受任何來自 agent 的指令，純規則驅動 |
| 監工失效時的空窗期 | L0/L1 是同步的，幾乎無失效可能；L2 異步失敗不影響 L0/L1 |
| **空洞 tool call 繞過 L0/L1** | **已知攻擊面。** Agent 可發起無關的 tool call（如 exec 無意義命令）使 `tools.length > 0`，從而通過 L0 檢查。L0/L1 只檢測「有沒有做」和「類型對不對」，**不檢測「做的事和任務是否相關」**——後者是 L2 語義層的職責。Phase 2 的 L2 實現將覆蓋此攻擊面。 |

---

## 10. 適用 vs 不適用場景

### 適用

- **涉及外部 tool call 的任務**：查天氣、發消息、搜索網頁、調用 API、讀寫文件
- **需要高可靠性的關鍵任務**：提交表單、發送重要郵件、執行腳本
- **多 agent 協作場景**：子 agent 聲稱完成但實際未執行

### 不適用

- **純文本推理任務**：「分析這段代碼的邏輯」——沒有外部可觀測的 tool call
- **主 agent 和監工使用同一 LLM provider 且 provider 宕機**：L2 層失效（L0/L1 不受影響）
- **Agent 做了工作但質量差**：本系統驗證「做沒做」，不驗證「做得好不好」

### 常見誤報 Anti-pattern

規則調校時最容易踩的坑是**聲明詞表過寬導致誤報**。以下是一個典型場景：

```
用戶：「幫我想想要不要帶傘」
Agent：查了天氣（web_fetch ✅），回覆「根據天氣預報，今天多雲，建議帶傘」

L1b 行為：
  ✅ 「根據天氣預報」→ 有 web_fetch tool call，一致，通過
  ❌ 如果把「帶傘」列為聲明詞 → 誤報（agent 確實做了工作）
```

**教訓**：`claim_tool_map.yaml` 的聲明詞必須精確到**過去式確認詞**——「已發送」「已完成」「已查詢」「結果如下」，不能包含「建議」「可以」「應該」「可能」這類推薦詞或建議詞。判斷標準是：這個詞是否意味著 agent 聲稱自己**做了某個動作**？如果只是在**表達觀點或建議**，就不應列入。

同理，`verb_tool_map.yaml` 的同義詞表不應把所有名詞都映射為行動 verb。「天氣」→ 查 是合理的（用戶大概率想查天氣），但「數據」→ 查 就太寬（用戶可能只是在討論數據概念）。寧可漏報讓 L2 接手，也不要在 L1 層大量誤報——誤報多了用戶會關掉告警，比沒有監工更糟。

---

## 11. 實現方案

### 11.1 實現形態對比

| 方案 | 描述 | 優點 | 缺點 | 結論 |
|------|------|------|------|------|
| A. CLI 事後掃描 | 獨立命令行工具，手動或 cron 觸發，掃描 `.jsonl` | 最簡單；無需理解 plugin 體系 | 非實時；不知道 turn 邊界；用戶需記得執行 | ❌ 不符合即時告警需求 |
| B. tail -f + 狀態機 | 獨立進程 watch `.jsonl`，自行推斷 turn 邊界 | 完全獨立於 OpenClaw | 需要 heuristic 判斷 turn 邊界；exec 長等待時誤判；前期已否決 | ❌ 已否決 |
| **C. OpenClaw Plugin** | 註冊 additive hooks，隨 gateway 進程常駐 | 精確的 turn 邊界（`agent_end`）；結構化 tool 數據（`after_tool_call`）；零額外進程管理 | 與 gateway 同進程，需注意 session 隔離 | ✅ **MVP 採用** |

**選擇 C 的理由**：hooks 是事件驅動的，需要接收方常駐；gateway 進程本身就是常駐的；plugin 跟著 gateway 活著，不需要自己管生命周期。CLI 作為 Phase 2 的事後審計輔助工具補充，與 plugin 共用同一套判定引擎，代碼零重複。

### 11.2 代碼實現

完整代碼見 `execution-watchdog/index.ts`。以下是核心設計要點：

**狀態管理**：用 `from`（channel:userId）做 Map key，`lastReceivedFrom` 變量橋接 `message_received` → `agent_end`。

```typescript
const turnState = new Map<string, TurnState>();  // from → state
let lastReceivedFrom: string = '';                // 橋接無 from 的 hooks

// message_received: 更新 lastReceivedFrom + 創建/重置 state
// after_tool_call:  用 lastReceivedFrom 定位 state，追加 tool 記錄
// agent_end:        用 lastReceivedFrom 定位 state，執行判定，然後 delete
```

**判定引擎**：L0 掃描 COMPLETION_CLAIMS 聲明詞列表 × 零 tool call；L1b 掃描 CLAIM_TOOL_MAP 聲明詞 × 期望 tool 類型匹配。兩層都是純字符串匹配，零 LLM。

**assistant 文本提取**：從 `agent_end` 的 `event.messages` 中過濾 `role === "assistant"`，展開 `content` 數組中 `type === "text"` 的條目。

### 11.3 實現注意事項

**Session 隔離**：Plugin 是 gateway 進程的單例。hook event 中無統一 `sessionId`，MVP 使用 `from` 做 bucket key。OpenClaw personal assistant 場景下單 channel 並發極少，`from` 足夠。Phase 2 如需更精確隔離，可引入 `runId`（`after_tool_call` 獨有）映射表。

**Hook event payload 已確認**（2026-03-20 實測）：所有字段名在代碼中直接使用真實名稱，無待確認項。關鍵字段：`event.toolName`（非 `tool`）、`event.content`（非 `text`）、`event.messages`（非 `finalMessages`）、`event.from`（非 `sender`）。

**⚠️ agent_end.messages 包含整個 session 歷史**（2026-03-20 實測發現）：`event.messages` 不是只有本輪的 assistant 回覆，而是整個 session 的完整 message list。如果掃描所有 `role=assistant` 的 message，歷史對話中出現的聲明詞會導致 L1b 誤報。**必須只取最後一條 `role=assistant` 的 message**（即本輪回覆）。

**規則庫加載**：MVP 階段 COMPLETION_CLAIMS 和 CLAIM_TOOL_MAP 硬編碼在代碼中。Phase 2 改為從 YAML 文件動態加載，支持 hot-reload。

---

## 12. 開發路線

### Phase 1：MVP（目標：可用）

- [ ] 建立 plugin 骨架，註冊 `agent_end` + `after_tool_call` + `message_received` hooks
- [ ] 實現 L0 判定引擎（完成聲明詞表 + 零 tool call 檢測）
- [ ] 實現 L1b 反向匹配（聲明 vs tool call 一致性）
- [ ] 實現基礎告警（Telegram message）
- [ ] 驗證 hook payload 結構（`console.log` 確認）
- [ ] 編寫 `verb_tool_map.yaml` 初始規則（20-30 條）

### Phase 2：增強（目標：好用）

- [ ] **`from + runId` 映射表**（第一優先級）：解決同一用戶並發 run 的 state 串擾問題
- [ ] 實現 L1a verb 提取 + YAML 規則查表
- [ ] 實現待驗證隊列（多輪任務支持）
- [ ] 實現 L2 Gemini Flash 異步語義判斷（同時覆蓋「空洞 tool call」攻擊面）
- [ ] 加入 webhook 通知接口
- [ ] 審計日誌系統
- [ ] CLI 審計工具（`openclaw-watchdog audit`，復用判定引擎，讀 `.jsonl`）

### Phase 3：擴展（目標：生態）

- [ ] L3 獨立重複驗證
- [ ] 系統層可觀測性整合（網路請求 / 文件 I/O 交叉驗證）
- [ ] 信任評分機制（類似 AgentSign 的 trust score）
- [ ] 獨立進程部署模式
- [ ] 提交 OpenClaw upstream RFC，推動「可驗證執行」成為一等公民特性

### 項目歸屬路徑

| 階段 | 歸屬 | 說明 |
|------|------|------|
| 現在 | claw-info `docs/` | 設計文件（本 proposal） |
| Phase 1 跑通後 | 獨立 repo + npm 包 | 迭代最快，不被 upstream review cycle 卡住 |
| Phase 3 穩定後 | openclaw upstream RFC | 以真實運行記錄為論據，推動進入官方生態 |

claw-info 放「為什麼做、怎麼想的」，獨立 repo 放「怎麼做、怎麼用」，互相引用。

---

## 13. 相關工作

| 項目 | 與本提案的關係 |
|------|-------------|
| [AgentSign](https://libraries.io/npm/agentsign-openclaw) | 執行鏈簽名，驗證「是否被篡改」；本提案驗證「是否真的執行了」 |
| [SlowMist Security Guide](https://github.com/slowmist/openclaw-security-practice-guide) | 三層防禦矩陣（事前/事中/事後）；本提案聚焦事後獨立驗證 |
| [ClawSec](https://github.com/prompt-security/clawsec) | Skill 完整性保護 + 漏洞掃描；不涉及執行真實性 |
| [NemoClaw (NVIDIA)](https://nvidianews.nvidia.com/news/nvidia-announces-nemoclaw) | 隱私控制 + 安全護欄；不涉及執行驗證 |
| OpenClaw Issue #40082 | 描述了相同症狀；歸因為上游模型故障，未從監工角度解決 |
| OpenClaw Issue #16808 | Stuck loop watchdog；只檢測進程健康，不驗證執行真實性 |

---

## 附錄 A：OpenClaw Plugin Hooks 參考

```
Additive Hooks（可多個 plugin 同時監聽）：
  before_tool_call    攔截 tool call，可讀 params
  after_tool_call     tool call 完成後，可讀 params + result
  tool_result_persist tool 結果寫入 .jsonl 前的同步鉤子
  message_received    收到 user 消息
  message_sending     發出消息前
  message_sent        消息發出後
  agent_end           整輪 agent 執行完成，可讀 final message list + run metadata
  session_start       session 開始
  session_end         session 結束

Exclusive Slots（只能有一個 plugin 佔據）：
  contextEngine       上下文管理（default: legacy）
  memory              記憶系統（default: memory-core）
```

## 附錄 B：名詞定義

| 術語 | 定義 |
|------|------|
| 主 Agent | 執行用戶任務的 OpenClaw agent |
| 監工 | 獨立驗證主 agent 執行真實性的系統 |
| 完成聲明詞 | Agent 回覆中表示任務已完成的關鍵詞 |
| Tool call | Agent 通過 OpenClaw tool 系統發出的工具調用 |
| Turn | 一輪完整的 user → agent 交互週期 |
| Pending queue | 等待後續 turn 補充 tool call 的待驗證任務隊列 |
