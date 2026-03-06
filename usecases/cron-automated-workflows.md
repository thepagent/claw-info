# Cron 自動化工作流實戰：從提醒到全自動報告

> 一份從簡單提醒到複雜自動化的漸進式指南，涵蓋常見工作流模式、避坑經驗與最佳實踐。
>
> 目標讀者：想用 OpenClaw cron 自動化日常任務的人。

---

## TL;DR

- Cron 是「觸發器」，不是執行引擎——它觸發 main（systemEvent）或 isolated（agentTurn）session
- 從簡單開始：先做「提醒」（main/systemEvent），再進化到「全自動任務」（isolated/agentTurn）
- 三層架構：cron（定時觸發）→ session（執行環境）→ delivery（結果投遞）
- payload 是獨立指令來源，不會自動繼承 AGENTS.md 或 SOUL.md 的規則

---

## 1. 為什麼要用 Cron？

手動觸發任務有幾個問題：

- **會忘記**：每天該做的事，靠人記憶不可靠
- **不一致**：每次手動做，流程可能不同
- **浪費時間**：重複性工作佔據寶貴的互動時間

Cron 解決這些問題：設定一次，持續自動執行。

---

## 2. Cron 的三層架構

理解 cron 的關鍵是把它拆成三層：

```
┌──────────────────────────────────────────────────────────────────────┐
│  第一層：觸發（When）                                                  │
│  - schedule.cron: "30 9 * * *"  ← 每天 09:30                         │
│  - schedule.kind: "cron" | "at"                                       │
│  - schedule.timezone: "Asia/Taipei"                                   │
└──────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  第二層：執行（How）                                                   │
│  - sessionTarget: "main" + payload.kind: "systemEvent"                │
│    → 注入文字到主會話（適合提醒、心跳）                                  │
│  - sessionTarget: "isolated" + payload.kind: "agentTurn"              │
│    → 啟動獨立會話（適合耗時任務、自動報告）                              │
└──────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  第三層：投遞（Where）                                                 │
│  - delivery.mode: "announce" | "none"                                 │
│    → announce: 結果自動發到指定頻道                                     │
│    → none: 由 session 內自行處理投遞                                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 常見工作流模式

### 模式 A：簡單提醒（main/systemEvent）

**適用場景：** 提醒 agent 在主會話中做某件事

**範例：心跳檢查**

```
觸發：每 30 分鐘
執行：main / systemEvent
投遞：不需要（在 main 內處理）
```

payload 範例：
```
Read HEARTBEAT.md if it exists. Follow it strictly.
```

**特點：**
- 文字注入主會話，agent 在對話脈絡中處理
- 適合輕量任務（<1 分鐘）
- 不適合耗時或需要獨立上下文的工作

### 模式 B：全自動報告（isolated/agentTurn）

**適用場景：** 定時產出報告，自動投遞到聊天頻道

**範例：每日投資組合巡檢**

```
觸發：每小時 :10
執行：isolated / agentTurn
投遞：announce 到 Telegram 或 Discord
```

payload 範例：
```
你是加密貨幣投資組合巡檢員。
執行以下步驟：
1. 讀取 portfolio_inspection.py 的輸出
2. 分析市場狀況
3. 產出簡潔報告（含盈虧、警報、建議）
```

**特點：**
- 獨立上下文，不污染主會話
- 可設定不同模型（例如用便宜模型跑例行報告）
- 結果透過 delivery 自動投遞

### 模式 C：Session 內自行投遞（isolated + delivery:none）

**適用場景：** 任務需要投遞到多個目標，或需要特殊格式（Components v2）

**範例：晨報 / 晚報**

```
觸發：每天 07:00 / 21:00
執行：isolated / agentTurn
投遞：none（由 session 內用 message 工具自行發送）
```

payload 範例：
```
你是 AI 助手，負責產出每日晨報。
1. 查詢今日行程
2. 查詢天氣
3. 查詢市場資訊
4. 用 message 工具發送報告到 Telegram（target: 123456）
5. 同時發送到 Discord（target: channel:789012）
```

**特點：**
- 最大彈性：可同時投遞多個目標
- 可使用 Components v2 等進階格式
- 需要在 payload 中明確寫出投遞邏輯

---

## 4. Payload 撰寫最佳實踐

### 4.1 Payload 是獨立的

**最重要的一點：** isolated session 的 payload 是獨立指令來源。它不會：
- 自動讀取 AGENTS.md
- 自動讀取 SOUL.md
- 繼承主會話的上下文

因此，payload 必須包含任務所需的**所有資訊**。

### 4.2 用精確關鍵字觸發 Skill

**不好的寫法：**
```
幫我看看投資組合怎麼樣
```

**好的寫法：**
```
執行投資組合巡檢：
1. cd ~/projects/trading-bot
2. python3 portfolio_inspection.py
3. 分析 JSON 輸出
4. 用 message 工具發送報告到 target: channel:123456
```

### 4.3 包含失敗處理

```
如果 portfolio_inspection.py 執行失敗：
1. 檢查錯誤訊息
2. 發送簡短警報：「巡檢腳本執行失敗：[錯誤摘要]」
3. 不要嘗試手動修復
```

---

## 5. 常見陷阱與解法

### 陷阱 1：main + agentTurn（錯誤組合）

`sessionTarget: main` 必須搭配 `payload.kind: systemEvent`。
`sessionTarget: isolated` 必須搭配 `payload.kind: agentTurn`。

混搭會導致 cron 觸發但不執行。

### 陷阱 2：一次性 cron 忘記 autoDelete

```
schedule.kind: "at"（一次性）→ 必須加 autoDelete: true
```

否則過期的 cron job 會一直留在清單中。

### 陷阱 3：規則變更後忘記同步 cron payload

你在 AGENTS.md 改了規則 ≠ isolated session 知道了。
因為 payload 是獨立指令來源。

**解法：** 每次改 AGENTS.md 的規則，檢查所有相關 cron 的 payload 是否需要同步更新。

### 陷阱 4：Timeout 太短

isolated session 預設有 timeout。如果任務需要：
- 呼叫外部 API（可能慢）
- 執行腳本（可能需要幾分鐘）
- 產出長報告

就要設定足夠的 `timeoutSeconds`。

### 陷阱 5：Cron 堆積

太多同時觸發的 cron 會互相競爭資源。

**解法：** 錯開觸發時間。例如：
- 巡檢：每小時 :10
- 晨報：07:00
- 晚報：21:00
- 心跳：:00, :30

---

## 6. 進階模式

### 6.1 鏈式 Cron（結果驅動下一步）

```
Cron A（06:50）→ 收集資料、寫入暫存檔
Cron B（07:00）→ 讀取暫存檔、產出報告
```

注意：兩個 cron 之間透過**檔案**傳遞資料，不透過 session。

### 6.2 條件執行

在 payload 中加入條件判斷：

```
1. 檢查今天是否為工作日
2. 如果是假日，只發送簡短摘要
3. 如果是工作日，發送完整報告（含行程提醒）
```

### 6.3 模型選擇策略

- **例行報告**（結構固定）→ 用便宜/快速模型
- **需要分析判斷**（市場異常偵測）→ 用強力模型
- **簡單提醒**（心跳）→ 用最便宜的模型

在 cron 設定中可以指定不同模型，優化成本。

---

## 7. 決策樹：我該用哪種模式？

```
需要定時自動跑？
├─ No → 不需要 cron
└─ Yes
    ├─ 任務 < 1 分鐘且需要主會話上下文？
    │   └─ Yes → 模式 A（main/systemEvent）
    └─ No
        ├─ 結果只需投遞到單一目標？
        │   └─ Yes → 模式 B（isolated + delivery:announce）
        └─ No
            └─ 模式 C（isolated + delivery:none，自行投遞）
```

---

## 8. 安全注意事項

- **Payload 不要包含 secrets**：API key、token 等應由執行環境提供，不要寫死在 payload 中
- **限制 cron 權限**：isolated session 只給完成任務所需的最少工具
- **監控 cron 執行**：定期檢查 cron 是否正常觸發、是否有失敗
- **一次性 cron 必開 autoDelete**：避免過期 job 堆積

---

## 更新記錄

- 2026-03-04：初版（基於實際部署經驗撰寫）
