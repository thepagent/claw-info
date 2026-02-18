# OpenClaw Webhooks（Webhook 回呼）

本文說明 OpenClaw 目前最常見的 webhook 用法：**Cron 任務完成後的投遞（delivery）回呼**，用於把執行結果以 HTTP POST 送到你的系統（自建 API / n8n / Zapier 等）。

> ⭐ 文件屬於說明性質；實際 webhook payload 欄位可能隨版本演進。接收端建議以「冪等 + 可容錯」方式設計。

---

## 概述

- ⭐ **主要用途**：Cron job 執行完成 → 以 webhook 將 run 結果事件 POST 到外部端點
- ⭐ **推薦搭配**：`sessionTarget = isolated` + `payload.kind = agentTurn`
- ⭐ **設計重點**：可達性（網路）、安全性（驗證）、可靠性（冪等 / 重送容忍）

---

## 1. Cron delivery webhook（完成事件回呼）

建立 cron job 時，在 job 物件設定：

- `delivery.mode: "webhook"`
- `delivery.to: "https://<your-endpoint>"`

### 1.1 流程圖（ASCII）

```
+------------------+        runs        +-------------------+
| OpenClaw Cron Job| --------------->   |  Agent execution  |
| (schedule)       |                   | (isolated session)|
+------------------+                    +-------------------+
          |                                         |
          |  finished run event (POST)              |
          v                                         v
+------------------+                         +------------------+
|  Your Webhook    | <-----------------------|   OpenClaw       |
|  Endpoint (HTTPS)|                         |   Gateway        |
+------------------+                         +------------------+
```

### 1.2 Job 範例

```json
{
  "name": "daily-summary",
  "schedule": { "kind": "cron", "expr": "0 9 * * *", "tz": "America/New_York" },
  "payload": {
    "kind": "agentTurn",
    "message": "整理今日重點與待辦，輸出精簡摘要。",
    "timeoutSeconds": 120
  },
  "delivery": {
    "mode": "webhook",
    "to": "https://example.com/openclaw/webhook"
  },
  "sessionTarget": "isolated",
  "enabled": true
}
```

---

## 2. `sessionTarget` 與 `payload.kind` 的限制

- `sessionTarget: "main"` **必須**搭配 `payload.kind: "systemEvent"`
- `sessionTarget: "isolated"` **必須**搭配 `payload.kind: "agentTurn"`

一般 webhook delivery 最適合用 `isolated + agentTurn`：
- 執行結果與主會話隔離
- webhook 可在完成後統一接收成功/失敗結果

---

## 3. Webhook 會收到什麼資料

你的端點將收到一個 HTTP POST（Content-Type: application/json），內容為「該次 cron run 的完成事件」。

由於欄位可能調整，接收端建議：

- ⭐ **完整記錄原始 JSON**（便於除錯與回溯）
- ⭐ 只抽取你真正需要的少數欄位（例如 jobId、runId、status、timestamps）
- ⭐ 以 `(jobId, runId)` 做去重（冪等）

---

## 4. 安全性與可靠性建議

### 4.1 安全性

- ⭐ **只用 HTTPS**
- ⭐ **驗證來源**（二選一或混用）
  - 在 URL 帶 token（例如 `?token=...`）
  - 在 HTTP header 驗證（較佳；若你的接收端/平台容易設定）
- ⭐ 在接收端做 **重放攻擊防護**
  - 儲存已處理 `(jobId, runId)`
  - 重複事件直接忽略

### 4.2 可靠性

- ⭐ Endpoint 需「快速回應」：建議立刻回 `2xx`，後續工作丟到 queue / background job
- ⭐ 接收端需能容忍重送與順序不保證

---

## 5. 最小接收端範例（Node.js / Express）

```js
import express from "express";

const app = express();
app.use(express.json({ limit: "2mb" }));

app.post("/openclaw/webhook", (req, res) => {
  // TODO: 驗證 token / header
  console.log("OpenClaw cron event:", JSON.stringify(req.body));
  res.sendStatus(200);
});

app.listen(3000, () => console.log("listening on :3000"));
```

---

## 6. 除錯清單

- Gateway 是否能從其網路環境連到你的 URL？（DNS / 防火牆 / NAT）
- 你的 endpoint 是否能穩定回 `2xx`？是否會 timeout？
- 是否有記錄 webhook 原始 JSON？
- 是否有做冪等處理（避免同一 run 重複入庫/重複觸發）？
