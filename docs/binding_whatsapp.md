---
last_validated: 2026-05-11
validated_by: claw-info-docs-contrib
---

# WhatsApp Binding 設定與疑難排解指南

OpenClaw 透過 [Baileys](https://github.com/WhiskeySockets/Baileys) 函式庫連接 WhatsApp，將 WhatsApp 訊息路由至 agent。本指南涵蓋初始設定、LID 路由機制，以及常見問題的排解方法。

---

## 目錄

- [快速開始](#快速開始)
- [Baileys 架構簡述](#baileys-架構簡述)
- [Binding 設定](#binding-設定)
- [LID vs Phone Number Routing](#lid-vs-phone-number-routing)
- [常見問題排解](#常見問題排解)
- [與 Telegram Binding 的差異](#與-telegram-binding-的差異)
- [安全性考量](#安全性考量)

---

## 快速開始

### 1. 啟用 WhatsApp 通道

在 `~/.openclaw/config.json` 的 `channels` 區塊加入 `whatsapp`：

```json
{
  "channels": {
    "whatsapp": {
      "accounts": {
        "main": {
          "name": "main"
        }
      }
    }
  }
}
```

### 2. QR Code 掃碼登入

首次啟動時，OpenClaw 會在終端機輸出 QR Code：

```
openclaw gateway start
```

掃描後，Baileys 會將登入憑證儲存於 `~/.openclaw/whatsapp_auth/`。後續啟動會自動復原連線，無需再次掃碼。

### 3. 設定 Binding

```json
{
  "bindings": [
    {
      "agentId": "main",
      "match": {
        "channel": "whatsapp",
        "accountId": "main"
      }
    }
  ]
}
```

WhatsApp 目前僅支援 **DM Binding**（私訊路由），尚不支援群組 Topic 綁定。

---

## Baileys 架構簡述

Baileys 是 WhatsApp Web 的逆向工程實作，透過 WebSocket 與 WhatsApp 伺服器通訊：

```
WhatsApp 手機端 ──▶ WhatsApp 伺服器 ──▶ Baileys (WebSocket)
                                              │
                                              ▼
                                        OpenClaw Gateway
                                              │
                                              ▼
                                        Agent (LLM / ACP)
```

- **無需官方 API**：Baileys 使用與 WhatsApp Web 相同的協定，不需要申請 Business API
- **手機必須在線**：手機端需保持網路連線，Baileys 才能維持連線
- **憑證本地儲存**：登入後的 session 憑證儲存在本地，可自動重連

---

## Binding 設定

### DM Binding

將 WhatsApp 帳號收到的所有私訊路由到指定 agent：

```json
{
  "bindings": [
    {
      "agentId": "main",
      "match": {
        "channel": "whatsapp",
        "accountId": "main"
      }
    }
  ]
}
```

與 Telegram 相同，若只有一個 agent 對應一個 WhatsApp 帳號，binding 可以省略，由 `defaultAgent` 自動 fallback 處理。

### 多帳號設定

```json
{
  "channels": {
    "whatsapp": {
      "accounts": {
        "personal": { "name": "personal" },
        "business": { "name": "business" }
      }
    }
  },
  "bindings": [
    {
      "agentId": "personal-assistant",
      "match": {
        "channel": "whatsapp",
        "accountId": "personal"
      }
    },
    {
      "agentId": "business-bot",
      "match": {
        "channel": "whatsapp",
        "accountId": "business"
      }
    }
  ]
}
```

每個帳號需分別掃碼登入，憑證獨立儲存。

---

## LID vs Phone Number Routing

WhatsApp 使用兩種不同的識別碼來標示聯絡人：

| 識別碼 | 格式 | 說明 |
|---|---|---|
| **Phone Number** | `+886912345678` | 傳統電話號碼 |
| **LID** (Line Identifier) | `1234567890@s.whatsapp.net` | WhatsApp 內部識別碼 |

### 什麼是 LID？

LID 是 WhatsApp 為每個帳號分配的內部識別碼，與電話號碼分離。當使用者：
- 更換電話號碼但保留 WhatsApp 帳號
- 使用 WhatsApp Business API
- 透過某些方式加入群組

系統可能使用 LID 而非電話號碼來標示該使用者。

### LID Forward Mapping

OpenClaw 2026.5.7 修復了 LID 路由問題（#74925）：

```
LID-addressed 訊息
      │
      ▼
Baileys 解析聯絡人資訊
      │
      ▼
OpenClaw 查詢 forward mapping
      │
      ▼
正確路由到對應 agent ✓
```

在 2026.5.7 之前，LID 標示的聯絡人可能導致：
- Agent 無法正確回覆訊息
- 產生「幽靈對話」（ghost chats）——訊息似乎送達但沒有回應
- 對話記錄分散在不同識別碼下

### 檢查 LID Mapping

若懷疑遇到 LID 相關問題，可檢查日誌：

```bash
# 查看 Baileys 聯絡人同步狀態
grep -i "lid\|forward" ~/.openclaw/logs/gateway.log

# 查看訊息路由決策
grep -i "routing\|whatsapp" ~/.openclaw/logs/gateway.log
```

---

## 常見問題排解

### Ghost Chats（幽靈對話）

**現象**：使用者傳送訊息，但 agent 沒有回應；或對話記錄出現在非預期的位置。

**成因**：
1. LID 與 phone number 的映射未正確建立（2026.5.7 已修復）
2. Baileys 聯絡人同步未完成
3. 多裝置登入導致的訊息重複

**排解**：
1. 升級至 OpenClaw 2026.5.7 或更新版本
2. 重新啟動 gateway，讓 Baileys 重新同步聯絡人
3. 檢查 `whatsapp_auth/` 目錄權限是否正確

### 斷線重連

**現象**：Gateway 顯示 disconnected，訊息無法收發。

**排解步驟**：

1. 檢查手機端網路連線
2. 確認手機上的 WhatsApp 應用程式在前景或背景執行
3. 查看 gateway 日誌：
   ```bash
   openclaw gateway status
   tail -f ~/.openclaw/logs/gateway.log
   ```
4. 若持續斷線，嘗試清除憑證重新掃碼：
   ```bash
   rm -rf ~/.openclaw/whatsapp_auth/
   openclaw gateway restart
   ```

### Media 訊息發送

**現象**：Agent 回覆包含媒體（圖片、影片），但 WhatsApp 端收到空訊息。

**成因**：
- 2026.5.7 之前，帶有 caption 的 MEDIA directive 會產生空的 media message（#78770）
- 媒體檔案過大或格式不支援

**排解**：
1. 升級至 OpenClaw 2026.5.7 或更新版本
2. 確認媒體檔案格式為 WhatsApp 支援的類型（JPEG、PNG、MP4 等）
3. 檢查檔案大小是否在限制內（通常 < 100MB）

### 訊息延遲

**現象**：訊息收發有明顯延遲。

**可能原因**：
- 手機端網路不穩定
- Baileys WebSocket 連線品質不佳
- Agent 處理時間過長

**排解**：
1. 確認手機端網路品質
2. 檢查 agent 的回應時間（查看 gateway 日誌中的處理時間戳）
3. 考慮使用更輕量的模型或啟用 streaming 模式

---

## 與 Telegram Binding 的差異

| 特性 | WhatsApp | Telegram |
|---|---|---|
| **API 類型** | Baileys（逆向工程） | 官方 Bot API |
| **認證方式** | QR Code 掃碼 | Bot Token |
| **群組支援** | 僅 DM Binding | DM + Topic Binding |
| **隱私模式** | 無需設定 | 需關閉 Group Privacy |
| **多帳號** | 支援，需分別掃碼 | 支援，各別 Bot Token |
| **LID 路由** | 需要 forward mapping | 無此概念 |
| **訊息格式** | 支援文字、媒體、位置 | 支援更多格式（投票、按鈕等） |
| **穩定性** | 依賴手機在線 | 獨立運作 |

---

## 安全性考量

### 憑證保護

WhatsApp 的登入憑證儲存在本地：

```
~/.openclaw/whatsapp_auth/
├── creds.json          # 登入憑證
├── pre-keys/           # 加密金鑰
└── sessions/           # 會話資料
```

**重要**：
- 這些檔案等同於你的 WhatsApp 帳號密碼
- 不要將 `whatsapp_auth/` 目錄加入版本控制
- 定期備份，但儲存在安全位置
- 若懷疑憑證外洩，立即在 WhatsApp 手機端登出所有裝置

### 與 Telegram 的安全性差異

| | WhatsApp | Telegram |
|---|---|---|
| **Bot Token** | 無，使用個人帳號憑證 | 有獨立的 Bot Token |
| **帳號隔離** | 使用個人 WhatsApp 帳號 | Bot 帳號與個人帳號分離 |
| **風險** | 憑證外洩 = 帳號被接管 | Token 外洩 = 僅影響 bot |
| **建議** | 使用專用 WhatsApp 帳號 | 可安全使用個人 bot |

**建議**：為 OpenClaw 建立專用的 WhatsApp 帳號，而非使用個人日常帳號。

### 訊息隱私

- Baileys 在本地解密訊息，OpenClaw 可以讀取所有收發內容
- 確保 OpenClaw 執行環境的安全（檔案權限、系統存取控制）
- 考慮啟用 OpenClaw 的 sandbox 功能來限制 agent 的系統存取

---

## 相關文件

- [Telegram Binding 指南](./binding_telegram.md) — 對照的 Telegram 設定指南
- [Troubleshooting](./troubleshooting.md) — 通用疑難排解
- [Nodes](./nodes.md) — 多節點部署與路由
