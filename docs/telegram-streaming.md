# Telegram 串流輸出機制

> OpenClaw 如何實現 Telegram Bot 的動態回覆體驗

> **注意**：本文程式碼片段為行為示意，非逐字引用原始碼。實際實作可能隨版本變動，請以 OpenClaw 主專案原始碼為準。

## TL;DR

- Telegram Bot 透過**編輯同一則訊息**實現串流效果，而非發送多則訊息
- 三層機制：Typing Indicator（打字指示）、Draft Stream（內容串流）、Lane Delivery（多軌道輸出）
- 節流控制（1 秒 1 次）+ 最小字數門檻（30 字）避免 API Rate Limit
- 支援 Answer 與 Reasoning 雙軌道並行輸出
- 內建錯誤處理與自動退避機制

## 解決的問題

**傳統 Bot 的痛點：**
- 使用者發送訊息後，需等待數秒才看到完整回覆
- 無法得知 Bot 是否正在處理
- 長回覆時體驗不佳

**串流輸出的優勢：**
- 即時顯示「正在輸入...」狀態
- 回覆內容逐步顯示，類似真人打字
- 使用者可提前看到部分答案，減少等待焦慮

## 核心概念

### 編輯訊息 vs 發送新訊息

關鍵技術：使用 Telegram Bot API 的 `editMessageText` 方法，不斷更新同一則訊息。

```
傳統模式：
使用者: 你好
Bot: [等待 5 秒...]
Bot: 你好！我是 AI 助手，很高興為你服務。

串流模式：
使用者: 你好
Bot: 💬 正在輸入...
Bot: 你好！                              ← 編輯訊息
Bot: 你好！我是                          ← 編輯訊息
Bot: 你好！我是 AI 助手                  ← 編輯訊息
Bot: 你好！我是 AI 助手，很高興為你服務。← 編輯訊息
```

### 三層架構

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram Bot API                        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌─────▼─────┐        ┌─────▼─────┐
   │ Typing  │          │   Draft   │        │   Lane    │
   │Indicator│          │  Stream   │        │ Delivery  │
   └─────────┘          └───────────┘        └───────────┘
   每 3 秒發送            編輯同一則訊息         多軌道並行
   "typing"              節流 1000ms           (答案+推理)
```

## 操作指引

### 配置串流模式

在 `openclaw.json` 中設定：

```json
{
  "channels": {
    "telegram": {
      "streaming": "block"
    }
  }
}
```

**參數說明：**
- `streaming`: 串流模式
  - `"off"` - 關閉串流，等全部生成完才發送
  - `"partial"` - 僅串流答案
  - `"block"` - 完整串流（答案 + 推理）
  - `"progress"` - 進度條模式（在 Telegram 上等同於 `"partial"`）

**注意**：以下參數為內部實作細節，無法透過配置修改：
- `throttleMs`: 節流間隔固定為 1000ms
- `minInitialChars`: 最小字數門檻固定為 30 字

## 實作細節

### 第一層：Typing Indicator

**功能**：顯示「正在輸入...」狀態

**實作位置**：`src/channels/typing.ts`

```typescript
const keepaliveLoop = createTypingKeepaliveLoop({
  intervalMs: 3_000,  // 每 3 秒重發一次
  onTick: async () => {
    await bot.api.sendChatAction(chatId, "typing");
  }
});

keepaliveLoop.start();  // 開始回覆時啟動
keepaliveLoop.stop();   // 回覆完成時停止
```

**為什麼每 3 秒？**
- Telegram 的 typing 狀態只維持 5 秒
- 每 3 秒重發可確保持續顯示

**生命週期：**

```
時間軸 ────────────────────────────────────────────────────▶

使用者發送訊息
    │
    ▼
┌───────┐  3s   ┌───────┐  3s   ┌───────┐  3s   ┌───────┐
│typing │ ────▶ │typing │ ────▶ │typing │ ────▶ │typing │
└───────┘       └───────┘       └───────┘       └───────┘
                                                    │
                                                    ▼
                                              回覆完成，停止
```

**安全機制：**
- TTL 60 秒自動停止
- 401 錯誤自動退避（避免 token 失效時無限重試）

### 第二層：Draft Stream

**功能**：動態更新訊息內容

**實作位置**：`src/telegram/draft-stream.ts`

**核心邏輯：**

```typescript
let streamMessageId: number | undefined;
let lastSentText = "";

const sendOrEditStreamMessage = async (text: string): Promise<boolean> => {
  const trimmed = text.trimEnd();
  if (!trimmed) return false;
  
  const rendered = renderTelegramHtmlText(trimmed);
  
  // 檢查長度限制
  if (rendered.length > 4096) {
    console.warn("訊息過長，停止串流");
    return false;
  }
  
  // 避免重複發送
  if (rendered === lastSentText) return true;
  lastSentText = rendered;
  
  // 第一次發送 vs 後續編輯
  if (typeof streamMessageId === "number") {
    await api.editMessageText(chatId, streamMessageId, rendered, {
      parse_mode: "HTML"
    });
  } else {
    const sent = await api.sendMessage(chatId, rendered);
    streamMessageId = sent.message_id;
  }
  
  return true;
};
```

**節流機制：**

```typescript
const throttleMs = 1000;  // 最快每秒更新一次
let pendingText = "";
let throttleTimer: NodeJS.Timeout | undefined;

const update = (text: string) => {
  pendingText = text;
  
  if (throttleTimer) return;  // 已有排程，等待
  
  throttleTimer = setTimeout(async () => {
    await sendOrEditStreamMessage(pendingText);
    throttleTimer = undefined;
  }, throttleMs);
};
```

**流程：**

```
AI 生成文字流
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  update("Hello")                                         │
│  update("Hello world")                                   │
│  update("Hello world! How")                              │
│  update("Hello world! How can I help?")                  │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│              節流控制（Throttle）                         │
│  ┌──────┐  1s   ┌──────┐  1s   ┌──────┐  1s   ┌──────┐ │
│  │ 批次1 │ ────▶ │ 批次2 │ ────▶ │ 批次3 │ ────▶ │ 批次4 │ │
│  └──────┘       └──────┘       └──────┘       └──────┘ │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│              Telegram API                                │
│  sendMessage(...)        → message_id = 12345            │
│  editMessageText(12345)  → "Hello world"                 │
│  editMessageText(12345)  → "Hello world! How"            │
│  editMessageText(12345)  → "Hello world! How can I help?"│
└─────────────────────────────────────────────────────────┘
```

**最小字數門檻：**

```typescript
const minInitialChars = 30;

if (typeof streamMessageId !== "number") {
  if (text.length < minInitialChars) {
    return false;  // 累積更多內容再發
  }
}
```

原因：避免推播通知只顯示「你」、「你好」等不完整內容。

### 第三層：Lane Delivery

**功能**：支援同時串流兩個獨立訊息

**實作位置**：`src/telegram/lane-delivery.ts`

**觸發條件**：
- AI 回覆包含 `<thinking>` 或 `<thought>` 等推理標籤時自動啟用
- 配置為 `streaming: "block"` 模式
- 支援的標籤：`<think>`, `<thinking>`, `<thought>`, `<antthinking>`

**兩種軌道：**
1. **Answer Lane** - 主要回答內容
2. **Reasoning Lane** - AI 推理過程（類似 ChatGPT 的 "Thinking..."）

**架構：**

```
┌─────────────────────────────────────────────────────────┐
│                    AI 生成內容                           │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
            ┌───────────┴───────────┐
            │                       │
            ▼                       ▼
    ┌───────────────┐       ┌───────────────┐
    │ Reasoning Lane│       │  Answer Lane  │
    │  (推理過程)    │       │   (最終答案)   │
    └───────────────┘       └───────────────┘
            │                       │
            ▼                       ▼
    ┌───────────────┐       ┌───────────────┐
    │  Message #1   │       │  Message #2   │
    │  (獨立訊息)    │       │  (獨立訊息)    │
    └───────────────┘       └───────────────┘
```

**使用者看到的效果：**

```
┌─────────────────────────────────────┐
│ 🤔 推理過程                          │
│ 正在分析問題...找到關鍵字             │
│ 查詢資料庫...找到 3 筆相關資料        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 💡 答案                              │
│ 根據你的問題，答案是...               │
└─────────────────────────────────────┘
```

## 範例

### 範例 1：長文章生成

```
使用者: 寫一篇關於 AI 的文章

Bot: 💬 正在輸入...

Bot: # AI 的未來
     人工智慧（AI）是...

Bot: # AI 的未來
     人工智慧（AI）是當今最熱門的技術之一。
     從自動駕駛到...

Bot: # AI 的未來
     人工智慧（AI）是當今最熱門的技術之一。
     從自動駕駛到醫療診斷，AI 正在改變我們的生活。
     
     ## 應用領域
     1. 自然語言處理
     2. 電腦視覺
     ...
```

### 範例 2：程式碼生成

```
使用者: 寫一個 Python 排序函式

Bot: 💬 正在輸入...

Bot: ```python
     def sort_list(arr):

Bot: ```python
     def sort_list(arr):
         return sorted(arr)

Bot: ```python
     def sort_list(arr):
         """排序列表"""
         return sorted(arr)
     
     # 使用範例
     numbers = [3, 1, 4, 1, 5]
     print(sort_list(numbers))
     ```
```

## 最佳實務

**建議：**
- 使用 `streaming: "block"` 獲得最佳體驗（包含推理過程）
- 節流間隔固定為 1000ms，避免 Rate Limit
- 最小字數門檻固定為 30 字，改善推播通知品質

**避免：**
- 不要在高頻場景（如群組）關閉串流

## Troubleshooting

### 症狀：訊息不會動態更新，只在最後一次性顯示

**可能原因：**
1. `streaming` 設定為 `"off"`

**處理方式：**
```bash
# 檢查設定檔
cat ~/.openclaw/openclaw.json | grep -A 5 "telegram"

# 確認 streaming 為 "block" 或 "partial"
```

### 症狀：Bot 顯示「正在輸入...」但沒有訊息出現

**可能原因：**
1. 內容未達最小字數門檻（固定 30 字）
2. AI 生成速度過慢

**處理方式：**
- 這是正常行為，等待內容累積到 30 字後會自動發送
- 無法透過配置調整此門檻

### 症狀：收到錯誤 "message is not modified"

**可能原因：**
- 連續兩次編輯內容完全相同

**處理方式：**
- 這是正常行為，OpenClaw 會自動忽略此錯誤
- 無需處理

### 症狀：收到錯誤 "message to edit not found"

**可能原因：**
- 使用者刪除了正在編輯的訊息

**處理方式：**
- OpenClaw 會自動停止串流
- 無需處理

### 症狀：Bot 停止回應，log 顯示 "CRITICAL: Bot token 可能失效"

**可能原因：**
- Bot token 過期或被撤銷
- 連續 10 次收到 401 錯誤

**處理方式：**
```bash
# 1. 檢查 token 是否有效
curl -X GET "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"

# 2. 重新設定 token
openclaw config set telegram.botToken <YOUR_BOT_TOKEN>

# 3. 重啟 gateway
openclaw gateway restart
```

**安全提醒**：請將 `<YOUR_BOT_TOKEN>` 替換為實際 token，避免外洩。

### 症狀：訊息超過 4096 字後被截斷

**可能原因：**
- Telegram 單則訊息上限為 4096 字元

**處理方式：**
- OpenClaw 會自動停止串流，避免 API 錯誤
- 完整內容會在串流結束後分段發送
- 這是預期行為

**技術細節：**
```typescript
// src/telegram/draft-stream.ts
const TELEGRAM_STREAM_MAX_CHARS = 4096;

if (renderedText.length > maxChars) {
  streamState.stopped = true;
  // 停止串流，後續分段發送完整內容
  return false;
}
```

## 安全注意事項

**錯誤處理與退避機制：**

實作位置：`src/telegram/sendchataction-401-backoff.ts`

```typescript
let consecutive401Failures = 0;

try {
  await sendChatAction(chatId, "typing");
  consecutive401Failures = 0;
} catch (error) {
  if (is401Error(error)) {
    consecutive401Failures++;
    
    if (consecutive401Failures >= 10) {
      suspended = true;  // 暫停所有請求
    } else {
      // 指數退避：1s → 2s → 4s → 8s → ...
      await sleep(Math.pow(2, consecutive401Failures) * 1000);
    }
  }
}
```

**保護機制：**
- 自動偵測 401 錯誤（token 失效）
- 指數退避避免被 Telegram 封禁
- 達到閾值後自動暫停所有請求

## 效能優化

### 節流控制

```
無節流：
AI 生成 → 立即發送 → API 請求 (100 次/秒) ❌ Rate Limit

有節流：
AI 生成 → 累積 1 秒 → 批次發送 (1 次/秒) ✅
```

### 去重

```typescript
if (rendered === lastSentText) {
  return true;  // 內容相同，跳過
}
```

### 最小字數門檻

```
無門檻：
推播通知：「你」 → 「你好」 → 「你好！」 ❌ 體驗差

有門檻（30 字）：
推播通知：「你好！我是 AI 助手，很高興為你服務。」 ✅
```

## 版本相依

- OpenClaw 2026.2+
- Telegram Bot API 支援 `editMessageText` 方法
- 支援平台：macOS、Linux、iOS

## See also

- `./cli.md` - CLI 指令參考
- `./troubleshooting.md` - 通用排錯指南
- `./nodes.md` - 裝置配對與通知
- [Telegram Bot API 文件](https://core.telegram.org/bots/api)

**OpenClaw 主專案原始碼位置：**
- `src/telegram/draft-stream.ts` - 核心串流邏輯
- `src/channels/typing.ts` - 打字指示器
- `src/telegram/sendchataction-401-backoff.ts` - 錯誤處理
- `src/telegram/lane-delivery.ts` - 多軌道輸出
- `src/telegram/reasoning-lane-coordinator.ts` - 推理軌道協調器
