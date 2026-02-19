# 訊息路由與 Channel Plugins（Messaging routing & channel plugins）

> 本文說明 OpenClaw 在「收到訊息 → 路由到 session/agent → 產生回覆 → 送回原平台」這條鏈路上，實際是如何運作的。
>
> 目標讀者：需要
> - 新增/除錯 Telegram / Discord / Signal 等通道整合的人
> - 理解為什麼訊息沒有進到正確 session、或回覆跑到奇怪地方的人
> - 設計安全策略（避免 prompt injection、避免誤發訊息）的人

---

## TL;DR

- OpenClaw 的「訊息路由」本質是：**把外部事件（inbound）映射到內部 session，並把 agent 產生的 outbound 回覆送回同一個對話上下文**。
- Channel plugin 負責「跟外部平台對接」，Gateway 負責「統一路由/狀態/權限」。
- 你要區分三件事：
  1) **訊息來源**（哪個 channel / 哪個 chat / 哪個 thread）
  2) **要送到哪個 session**（main 或 isolated 或 cron）
  3) **如何回覆**（直接在當前 chat reply，或跨 session send，或主動推送）
- **最常見的問題**不是模型，而是：
  - bot 沒收到事件（webhook/長連線問題）
  - 路由鍵不一致（chat_id / threadId 變了）
  - 權限/安全政策阻擋 message tool

---

## 1. 為什麼這很重要

訊息路由是所有「24/7 代理」的神經系統：

- **可靠性**：訊息沒進來/回不去，就等於整個 agent 失明失語。
- **安全性**：錯路由可能造成「把私人資訊回到錯的群」「把指令回到公開頻道」。
- **可維運性**：理解路由模型，才能定位是 channel、gateway、session 還是 tool policy 的問題。

---

## 2. 核心概念

### 2.1 Inbound vs Outbound

- **Inbound**：外部平台送進 Gateway 的事件（例如 Telegram message update）。
- **Outbound**：Gateway/agent 透過 channel plugin 把回覆送回外部平台。

> 重要原則：**Inbound 的 metadata 不是“裝飾”，它是路由鍵**。

### 2.2 路由鍵（Routing keys）

典型會用到的路由鍵（依平台不同而不同）：

- `channel`：telegram / discord / signal ...
- `chat_id`：對話/群組 ID（最常用）
- `message_id`：某一則訊息 ID（用於 reply-to）
- `threadId` / `topicId`：群組內的主題/討論串（例如 Telegram topics）
- `sender_id`：發訊者 ID（私訊情境常用）

OpenClaw 會把這些資訊包成「聊天上下文」，用於：

- 決定回覆要送到哪裡（同 chat、同 thread）
- 決定是否要用 reply（引用回覆）
- 避免把訊息送錯地方

### 2.3 Session 與路由的關係

- **main session**：跟人類互動的主要上下文。訊息路由通常會把同一個 chat 映射到同一個 main session。
- **isolated session（sub-agent）**：背景任務。它可以在完成後把結果「回送」到 main session（或直接 message tool 回到 chat）。
- **cron**：只是觸發器；觸發後仍會選擇 main（systemEvent）或 isolated（agentTurn）。

---

## 3. 架構 / 心智模型

下面用一個「Telegram 私訊」例子說明完整資料流：

```
[Telegram]
  │  (message update)
  ▼
[Channel plugin: Telegram]
  │  normalize inbound payload
  ▼
[Gateway]
  │  1) identify channel/chat/thread
  │  2) find/create session
  │  3) run agent turn (LLM)
  ▼
[Agent]
  │  decides: reply / tool call / spawn
  ▼
[Gateway tools runtime]
  │  may call: message / sessions_send / cron / ...
  ▼
[Channel plugin]
  │  send outbound message
  ▼
[Telegram]
```

### 3.1 Channel plugin 的責任

- 與平台 API 互動（webhook、長輪詢、WS…）
- 把 inbound 轉成 Gateway 可理解的事件格式
- 把 Gateway 的 outbound 請求轉成平台 API 呼叫
- 處理平台限制（速率、長度、附件、thread/topic）

### 3.2 Gateway 的責任

- 路由：inbound → session
- session 狀態：歷史、工具權限、工作目錄
- policy：允許/阻擋危險工具、是否需要人類確認
- 統一 observability（log、run status、errors）

---

## 4. `message` tool vs `sessions_send`

這是很多人會混淆的點：

### 4.1 `message` tool：對外發送（Outbound to Channel）

用途：把訊息送到 Telegram/Discord/Signal 等外部平台。

特性：
- 會真的「對外」產生副作用（發出訊息）
- 通常需要更嚴格的安全政策
- 需要指定 target（chat id / channel id / user id）

適用：
- 主動推播提醒
- 從 cron 發提醒到 Telegram
- sub-agent 完成任務後主動通知

### 4.2 `sessions_send`：對內送訊息（Intra-OpenClaw）

用途：把一段文字送到另一個 session（通常是 main session 或某個 subagent）作為「新的輸入」。

特性：
- 不直接對外（仍會走 Gateway/agent）
- 常用於「控制 sub-agent」或「把結果交回主會話」

適用：
- 你想讓 main session 看到某個 sub-agent 的結果
- 你要 steer 某個 sub-agent（追加指令）

### 4.3 最佳實踐（簡化選擇）

- 你要「回覆/通知人類」→ 優先用 **message tool**（但要小心 target）
- 你要「把結果交給另一個 agent/會話繼續處理」→ 用 **sessions_send**

---

## 5. Reply tags（引用回覆）與對話一致性

在支援 reply 的平台上（例如 Telegram），OpenClaw 允許你在文字最開頭加 reply tag：

- `[[reply_to_current]]`：回覆當前觸發訊息
- `[[reply_to:<id>]]`：回覆指定訊息 id

目的：
- 讓對話更清晰，避免在群組中「不知道回誰」
- 讓使用者更容易追溯上下文

最佳實踐：
- 在群組/多線程中，優先用 `[[reply_to_current]]`
- 對外主動推播（非回覆）就不要用 reply tag

---

## 6. Threads / Topics

不同平台的 thread 模型不同：

- Telegram：可能有群組「topics」與 threadId
- Discord：threads / channels

原則：
- **同一個 chat 裡的不同 thread，應視為不同上下文**（至少要在路由鍵層面保留 thread id）
- 若你忽略 thread id，回覆就可能跑到錯的討論串

---

## 7. Delivery modes（輸出策略）

你可以把輸出策略分為三種：

1) **同步回覆**：收到 inbound 後立即回覆（最常見）
2) **非同步回覆**：先 ack「我收到」，然後 spawn sub-agent，完成後再 message 通知
3) **定時推播**：cron 觸發，message tool 送出

建議：
- 任何可能超過數十秒的工作（查很多網頁、跑重計算）→ 用非同步：spawn sub-agent。

---

## 8. 安全 / 安全邊界（Security notes）

### 8.1 把 inbound 當不可信

- email/web/page/聊天內容都可能包含 prompt injection
- 不要讓 channel plugin 的文字內容直接變成 `exec` 或 `message` 的參數

### 8.2 避免送錯 target

- 在群組中發敏感資訊是最常見事故
- 實作上建議：
  - 對外 message 時，明確帶上 `chat_id` 與 threadId
  - 對敏感動作（發到非當前 chat）要求額外確認

### 8.3 對外訊息屬於高風險工具

- message tool 應被視為「外部副作用」
- 建議在 policy 層設 gate：
  - 需要使用者明確指示
  - 或僅允許特定 cron/job 使用

---

## 9. 常見 workflows（Recipes）

### 9.1 「收到訊息 → 交給 sub-agent 跑 → 回報結果」

- main session：接收到需求後 spawn sub-agent
- sub-agent：產出結果（不直接對外發）
- main session：整理後用 reply tag 回覆人類

### 9.2 「每日摘要推播」

- cron：每天/每小時觸發
- payload：isolated agentTurn 產生摘要
- delivery：announce（或 webhook）

---

## 10. Failure modes & troubleshooting

### 10.1 收不到訊息

- 檢查 bot token / webhook / long poll 是否正常
- 檢查 Gateway 是否在跑、channel plugin 是否連線

### 10.2 收到但不回覆

- 看是否被 policy 擋掉（message tool 被拒）
- 看是否卡在 tool call（例如 browser 沒 attach tab）

### 10.3 回覆到錯地方

- 檢查 chat_id / threadId
- 檢查你是否用了跨 chat 的 message target

### 10.4 sub-agent 做完但人類沒看到

- sub-agent 結果如果只回到 isolated session，需要用 sessions_send 交回 main 或 message 推播

---

## 11. Open questions

- 是否要提供「路由視覺化」：顯示 inbound → session mapping
- 是否要提供「安全模式」：禁止跨 chat message，除非 explicit allowlist

