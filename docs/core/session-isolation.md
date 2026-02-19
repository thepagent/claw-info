# Session model 與隔離（main vs isolated vs cron）

> 本文是 OpenClaw 的核心概念深度解析：**什麼是 session**、為何需要隔離、以及你應該在「主會話（main）／隔離會話（isolated）／定時任務（cron）」之間如何做選擇。

---

## TL;DR（快速決策）

- **你正在跟 Agent 對話、需要它記得上下文、要多輪互動** → 用 **main session**
- **你要把一個耗時/高風險/需要不同模型的任務丟到背景跑，且不想污染主上下文** → 用 **isolated session（sub-agent）**
- **你要在特定時間自動跑（每天 9 點、每 30 分鐘…）** → 用 **cron**
  - cron 只是「觸發器」，觸發時仍會選擇 **main（systemEvent）** 或 **isolated（agentTurn）**

---

## 為什麼這很重要

### 1) 成本與品質
- 在 main session 讓模型背著整段長對話做任務：**更貴**、也更容易因為上下文太雜而產生偏移。
- 用 isolated session 做單一任務：上下文更短、更聚焦，通常 **更穩定**。

### 2) 安全與資料邊界
- main session 通常包含更多人類對話、偏好、個人資訊，若拿去做不相干的長任務，**外洩面積變大**。
- isolated session 可把任務輸入縮到最少，降低 prompt injection 與無意洩漏的機率。

### 3) 工程可維護性
- 把「對話」與「工作」分開：
  - main：協調、決策、互動
  - isolated：執行、產出、可重跑
- 也更容易在 cron / webhook / pipeline 中串接。

---

## 核心名詞與模型

### Session 是什麼？
在 OpenClaw 裡，**session** 是一段可持續的對話與執行上下文，包含：
- 對話歷史（messages）
- 工具可用性與 policy（哪些工具可用、是否 sandbox）
- 工作目錄（workspace）與可讀寫狀態
-（可選）記憶檔案策略（例如 main session 可能會被指示讀 MEMORY.md；isolated 通常不應該）

### 三種常見「執行型態」

1) **main session（主會話）**
- 目的：與使用者互動、維持連貫對話
- 特性：
  - 會保留大量上下文
  - 容易被「雜訊」影響
  - 適合做「協調/決策/澄清」

2) **isolated session（隔離會話 / sub-agent）**
- 目的：把某個任務丟給一個乾淨、獨立的上下文執行
- 特性：
  - **不共享 main 的對話歷史**（除非你把內容明確傳進去）
  - 適合：長任務、批次處理、風險較高的工具操作、需要不同模型/思考設定
  - 可把結果「回報」給 main（announce），或只回傳摘要

3) **cron（排程觸發）**
- 目的：在指定時間/週期觸發一段工作
- 重要觀念：cron 不是 session 類型，而是 **觸發器 + payload**
  - `sessionTarget: main` 必須搭配 `payload.kind: systemEvent`（把文字注入 main）
  - `sessionTarget: isolated` 必須搭配 `payload.kind: agentTurn`（啟動 isolated run）

> 這些限制在 docs/webhook.md 與 docs/cron.md 也有說明。

---

## 架構 / 心智模型

把 OpenClaw 想成「一個會話協調器 + 工具系統」，而不是單一聊天機器人：

```
┌──────────────────────────────────────────────────────────────────────┐
│                              使用者                                   │
└──────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         main session（對話/協調）                      │
│  - 多輪互動                                                            │
│  - 釐清需求                                                            │
│  - 決定是否要把工作委派出去                                             │
└──────────────────────────────────────────────────────────────────────┘
                     │ spawn / delegate
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    isolated session（執行/產出）                        │
│  - 獨立上下文、可換模型/思考設定                                        │
│  - 可跑很久、可重試                                                     │
│  - 產出結果（檔案/摘要/狀態）                                           │
└──────────────────────────────────────────────────────────────────────┘
                     │ announce / report
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         main session（彙整/回覆）                       │
└──────────────────────────────────────────────────────────────────────┘

（cron 只是定時從旁邊觸發：要嘛注入 main，要嘛啟動 isolated）
```

---

## 決策表：main vs isolated vs cron

> 先決條件：如果你「需要在固定時間自動觸發」，就直接進 cron；cron 之後再選 main/isolated。

| 需求/條件 | main session | isolated session | cron（main/systemEvent） | cron（isolated/agentTurn） |
|---|---:|---:|---:|---:|
| 多輪對話、需要追問/澄清 | ✅ 最適合 | ⚠️ 不適合（除非你自己設計回報/續跑機制） | ✅（但注入後仍在 main 互動） | ⚠️（isolated 通常是一次性 run） |
| 任務耗時（>1-2 分鐘） | ⚠️ 容易卡住對話節奏 | ✅ 最適合 | ⚠️ 文字提醒可以，但不建議做重活 | ✅ 最適合 |
| 想避免污染主上下文 | ❌ | ✅ | ❌（會注入 main） | ✅ |
| 需要不同模型/思考/timeout | ⚠️ 可能可做但不建議常態 | ✅ | ❌ | ✅ |
| 高風險工具操作（大量檔案改動、外部網路操作） | ⚠️ 可行但風險擴散 | ✅（更好控管與回收） | ❌ | ✅ |
| 需要固定時間自動跑 | ❌ | ❌ | ✅ | ✅ |
| 結果要自動投遞（announce/webhook） | 依版本/管線而定 | ✅ 常見做法 | ⚠️ 通常不走 delivery | ✅ 常見做法 |
| 適合做「協調/決策/回覆」 | ✅ | ❌ | ✅（本質是注入 main） | ⚠️（要回傳再由 main 彙整） |

---

## 常見工作流程（Recipes）

### Recipe 1：把複雜任務委派給 isolated sub-agent（spawn）

適用：
- 要讀很多檔案/寫很多檔案
- 要跑 shell 指令、抓 log、做重構
- 需要「結果」而不是「對話」

**模式：main 先定義輸入邊界 → isolated 執行 → main 收斂輸出**

範例（概念性）：

```text
main：
  1) 明確定義任務輸入（必要的檔案路徑、期望輸出、驗收標準）
  2) spawn isolated：把任務描述丟過去

isolated：
  1) 只讀/只寫 workspace 內必要範圍
  2) 產出 PR / patch / 報告
  3) 用 announce 回報 main
```

> 在 OpenClaw 內部工具層面，main 可用 `subagents` 相關能力去 spawn / steer / kill。

### Recipe 2：在 isolated 執行中追加指令（send / steer）

適用：你發現需求要微調，但不想把整個任務搬回 main。

做法：
- 讓 main 對正在跑的 sub-agent 發送「追加指令」：
  - 增加限制（例如「不要碰某個資料夾」）
  - 改變輸出格式（例如「輸出 zh-TW」）
  - 追加驗收（例如「補上 anti-patterns」）

注意：
- 追加訊息要像「patch 指令」一樣精準，避免再次引入大量上下文雜訊。

### Recipe 3：任務結束後的收尾（cleanup）

isolated 的好處之一是：你可以把「任務過程」跟「主對話」分離，但仍要做乾淨的收尾。

建議做法：
- **讓 isolated 在結束前寫出可驗證產物**（檔案、commit、測試輸出、變更摘要）
- 如果任務中途卡住：
  - 先 steer 提供缺的資訊
  - 不行就 **kill** 該 sub-agent，重新 spawn 一個乾淨的

反模式（不要做）：
- 讓卡住的 isolated 無限等待/無限重試
- 把 debug 對話塞回 main 造成噪音（把 debug 留在 isolated，main 只收斂結論）

### Recipe 4：用 cron 做「提醒」與「自動化任務」

cron 有兩條常見路徑：

#### A) cron → main（systemEvent）
適用：
- 簡單提醒、提示 main 去做某件事
- 例如 heartbeat 檢查、提示你看某份清單

（示意）
```yaml
sessionTarget: main
payload:
  kind: systemEvent
  text: "Read HEARTBEAT.md if it exists. Follow it strictly."
```

#### B) cron → isolated（agentTurn）
適用：
- 想在固定時間自動完成一個「可重跑、可投遞」的任務
- 例如：每日摘要、定期抓取報表、例行檢查

（示意）
```yaml
sessionTarget: isolated
payload:
  kind: agentTurn
  message: "整理今日重點與待辦，輸出精簡摘要。"
  timeoutSeconds: 120
delivery:
  mode: announce
  channel: "telegram:176096071"
  to: "176096071"
```

---

## Anti-patterns（常見反模式）

### 1) 在 main session 做長時間批次工作
- 症狀：對話被卡住、上下文爆長、模型開始答非所問
- 改法：把工作移到 isolated；main 只做「派工 + 收斂」

### 2) 把敏感/無關的上下文複製到 isolated
- 症狀：你為了「方便」把整段聊天貼過去
- 風險：外洩面積擴大、prompt injection 攻擊面更大
- 改法：只傳必要的規格/路徑/驗收條件；需要引用就用「摘要」

### 3) 把 isolated 當成第二個 main 來聊天
- 症狀：在 isolated 開多輪對話、反覆變更需求
- 結果：你失去「隔離」帶來的可控性
- 改法：
  - main 做互動
  - isolated 做一次性 run（或明確定義階段性 run）

### 4) 用 cron 注入 main 來做重活
- 症狀：每次 cron 觸發都把大任務塞進 main，導致主會話逐漸失控
- 改法：cron 觸發應盡量走 isolated/agentTurn，並使用 delivery 送回結果

### 5) 不做 cleanup：孤兒 sub-agent 堆積
- 症狀：同時存在大量背景 run，資源佔用、結果難以追蹤
- 改法：
  - 任務完成就結束
  - 失敗就 kill 並重跑
  - 用明確的命名/摘要讓 main 易於管理

---

## 失敗模式與排錯

### 問題：isolated 讀不到 main 的資訊/檔案？
- 說明：isolated 不會共享 main 的對話歷史；你必須「明確傳入」需要的資訊。
- 建議：
  - 把必要路徑/檔名/規格寫成清單
  - 讓 isolated 先回報它已讀到哪些檔案/理解到的需求（快速確認）

### 問題：cron 任務路徑/環境不一致
- 常見原因：sandbox / workspace 路徑在不同執行環境下不同。
- 建議：
  - 以 `/workspace`（或系統指定的 workspace 根）為基準撰寫路徑
  - 避免硬編本機絕對路徑（例如 `/Users/...`）

### 問題：結果投遞不到聊天/外部 webhook
- 建議：
  - 優先使用 cron 的 `delivery`（通常搭配 isolated/agentTurn）
  - webhook 端要做冪等（以 jobId/runId 去重），並記錄 request log 以利追查

---

## 安全 / Safety notes

- **最小化上下文**：isolated 只給它完成任務所需的最少資訊。
- **最小化權限**：配合 tooling policy / sandbox mode，避免在 main session 直接做高風險操作。
- **可審計產物**：讓 isolated 輸出「可檢查」的變更（diff、commit、測試結果）再回報。

---

## 延伸閱讀

- Cron：`docs/cron.md`
- Webhook：`docs/webhook.md`
- Sandbox：`docs/sandbox.md`
- Tooling safety：`docs/core/tooling-safety.md`
