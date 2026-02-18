# OpenClaw Webhooks（Webhook 回呼）

OpenClaw 支援在特定工作完成後，將結果以 **HTTP webhook** 形式投遞到外部系統。

本文聚焦於最常見且最實用的場景：**Cron 任務完成後的 delivery webhook 回呼**。

---

## 概述

- webhook 主要用於：Cron job 完成後，將「本次 run 的完成事件」POST 到你的端點（自建 API / n8n / Zapier 等）
- 建議搭配：`sessionTarget: isolated` + `payload.kind: agentTurn`
- 設計重點：網路可達性、安全性驗證、可靠性（冪等/容錯）

---

## 解決的問題

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         沒有 webhook 時的痛點                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  痛點 1：結果只能留在 OpenClaw 內部                                          │
│    • 需要手動查看 cron runs 才知道成功/失敗                                 │
│    • 難以自動串接外部流程（例如：建立工單、寫入資料庫、觸發通知）            │
│                                                                             │
│  痛點 2：缺乏統一的事件出口                                                 │
│    • 不同任務各自採用不同通知方式                                           │
│    • 整體監控與告警難以標準化                                               │
│                                                                             │
│  痛點 3：自動化流程斷裂                                                     │
│    • 無法在任務完成後立即觸發下一步                                         │
│    • 需要額外輪詢或人工介入                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Webhook 帶來的價值                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✓ 自動串接：run 完成後立即把結果送到你的系統                               │
│  ✓ 標準出口：用 HTTP POST 統一承接所有任務完成事件                          │
│  ✓ 可監控：接收端可集中記錄、告警、重試策略                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 架構

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Cron delivery webhook 架構                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐                                                         │
│   │   Gateway     │                                                         │
│   │ Cron Scheduler│                                                         │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐      runs      ┌─────────────────────────┐              │
│   │  Cron Job     │──────────────▶│  Agent Execution        │              │
│   │ (schedule)    │               │ (isolated session)      │              │
│   └──────┬───────┘               └───────────┬─────────────┘              │
│          │                                    │                            │
│          │ finished run event (HTTP POST)     │                            │
│          ▼                                    ▼                            │
│   ┌──────────────────────┐         ┌──────────────────────┐               │
│   │ Your Webhook Endpoint │         │  Run Result / Error  │               │
│   │ (HTTPS)               │         │  (JSON event body)   │               │
│   └──────────────────────┘         └──────────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心概念

### Delivery Modes

在 cron job 中設定 `delivery` 以控制結果如何投遞：

- `none`：不投遞
- `announce`：投遞到聊天頻道
- `webhook`：投遞到 HTTP endpoint

> 實際可用模式與欄位以 Gateway 版本與 cron schema 為準。

### `sessionTarget` 與 `payload.kind` 限制

- `sessionTarget: "main"` **必須**搭配 `payload.kind: "systemEvent"`
- `sessionTarget: "isolated"` **必須**搭配 `payload.kind: "agentTurn"`

---

## 使用範例

### 範例 1：每日摘要（完成後 webhook 投遞）

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

## 實作建議

### 安全性

- **只用 HTTPS**
- **加入驗證**（擇一或混用）
  - 在 URL 帶 token（例如 `?token=...`）
  - 在 HTTP header 驗證（較佳，若接收端/平台可設定）
- **重放攻擊防護**：以 `(jobId, runId)` 或等價識別做去重

### 可靠性

- Endpoint 建議快速回 `2xx`，把耗時處理丟到 background job / queue
- 接收端需能容忍重送與順序不保證（冪等設計）

---

## 最小接收端範例（Node.js / Express）

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

## 常見問題

### Q1：Webhook payload 的 JSON 欄位是否固定？

**A：**不保證。建議接收端完整記錄原始 JSON，並只抽取必要欄位；避免對未保證的欄位做嚴格 schema 綁定。

### Q2：如何避免同一個 run 重複觸發造成重複處理？

**A：**接收端請以 `(jobId, runId)` 做去重（冪等），重複事件直接忽略。

---

*最後更新：2026-02-18*
