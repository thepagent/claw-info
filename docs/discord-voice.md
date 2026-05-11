---
last_validated: 2026-05-12
validated_by: tboydar-agent
---

# Discord Voice / Realtime 語音模式完整指南

OpenClaw 2026.5.10 起支援 Discord 語音頻道互動，提供三種 `/vc` 模式，讓 agent 能以「說話」而非「打字」的方式與使用者溝通。

## 快速開始

```yaml
# openclaw.yaml
channels:
  discord:
    voice:
      enabled: true
      # 預設模式，可選 agent-proxy / stt-tts / realtime
      mode: agent-proxy
```

在 Discord 中輸入 `/vc`，agent 會加入你所在的語音頻道。

---

## 三種 `/vc` 模式對照

```
┌─────────────────┬────────────────────────────┬────────────────────────────┐
│ 模式            │ 運作方式                    │ 適用情境                    │
├─────────────────┼────────────────────────────┼────────────────────────────┤
│ agent-proxy     │ 語音輸入 → STT → Agent     │ 一般對話，需要完整推理能力   │
│   （預設）       │ 推理 → TTS → 語音輸出       │                             │
├─────────────────┼────────────────────────────┼────────────────────────────┤
│ stt-tts         │ 語音輸入 → STT → 直接 TTS   │ 快速回應，低延遲，簡單互動 │
│                 │ （不經過 Agent 推理）        │                             │
├─────────────────┼────────────────────────────┼────────────────────────────┤
│ realtime        │ OpenAI Realtime API 雙向    │ 最自然對話體驗，低延遲      │
│                 │ 語音串流（bidi）             │ 需要 OpenAI realtime 模型   │
└─────────────────┴────────────────────────────┴────────────────────────────┘
```

### 模式選擇建議

| 情境 | 推薦模式 | 理由 |
|------|---------|------|
| 日常問答、需要工具呼叫 | `agent-proxy` | 完整 agent 能力，可執行指令 |
| 快速回應、簡單確認 | `stt-tts` | 延遲最低，不需要推理 |
| 自然對話、情緒表達 | `realtime` | 語氣最自然，支援打斷 |
| 預算敏感 | `agent-proxy` 或 `stt-tts` | `realtime` 按分鐘計費 |

---

## agent-proxy 模式（預設）

這是大多數使用者的起點。運作流程如下：

```
使用者說話
    ↓
Discord 語音串流
    ↓
STT（Speech-to-Text）轉文字
    ↓
OpenClaw Agent 接收文字、推理、決策
    ↓
TTS（Text-to-Speech）轉語音
    ↓
Discord 語音輸出
    ↓
使用者聽到回應
```

### 設定範例

```yaml
channels:
  discord:
    voice:
      enabled: true
      mode: agent-proxy
      # 可選：指定 TTS 語音
      tts:
        voice: "nova"  # OpenAI TTS 語音選項
```

### 特點

- **完整 agent 能力**：工具呼叫、記憶存取、外部 API 都可以使用
- **延遲較高**：STT → Agent → TTS 三個步驟
- **成本可控**：只按 token 計費，無額外語音費用

---

## stt-tts 模式

純語音轉接模式，不經過 Agent 推理。適合簡單的「你說我回」情境。

```
使用者說話 → STT → 文字直接進 TTS → 語音輸出
                ↑
         （不經過 Agent 推理層）
```

### 設定範例

```yaml
channels:
  discord:
    voice:
      enabled: true
      mode: stt-tts
```

### 特點

- **延遲最低**：省去 Agent 推理時間
- **無法使用工具**：不能執行指令、查資料
- **適合簡單互動**：問候、確認、簡短回應

---

## realtime 模式

使用 OpenAI Realtime API 進行雙向語音串流，提供最自然的對話體驗。

```
┌─────────────┐      WebRTC / WebSocket      ┌─────────────┐
│  使用者麥克風  │  ═══════════════════════►  │             │
│  （語音輸入）  │                            │  OpenAI     │
└─────────────┘                            │  Realtime   │
                                           │  API        │
┌─────────────┐                            │             │
│  使用者喇叭   │  ◄════════════════════════  │             │
│  （語音輸出）  │      語音串流（雙向）        └─────────────┘
└─────────────┘
```

### 設定範例

```yaml
channels:
  discord:
    voice:
      enabled: true
      mode: realtime
      realtime:
        # 打斷回應：使用者說話時自動中斷 AI 輸出
        interruptResponseOnInputAudio: true
        # 最小打斷音訊結尾時間（毫秒）
        minBargeInAudioEndMs: 200
```

### 自訂語音風格

透過 `talk.realtime.instructions` 設定 agent 的說話風格：

```yaml
talk:
  realtime:
    instructions: |
      你是一位親切的技術助理，說話簡潔有力。
      遇到專業術語時會用比喻解釋，讓非技術背景的人也能理解。
      回答前會先簡短確認聽到的問題，再給出答案。
```

### 特點

- **最自然的對話體驗**：語氣、停頓、情緒都更真實
- **支援打斷（Barge-in）**：使用者可以隨時插話
- **按分鐘計費**：成本較高，注意使用時間
- **需要 OpenAI realtime 模型**：`gpt-realtime-2` 或相容模型

---

## 效能調校

### 語音擷取參數

```yaml
channels:
  discord:
    voice:
      # 靜音後多久停止擷取（毫秒）
      # 較短 = 更快回應，但可能截斷句子
      # 較長 = 更完整，但延遲增加
      captureSilenceGraceMs: 800

      realtime:
        # 最小打斷音訊結尾時間
        # 較短 = 更敏感，容易被打斷
        # 較長 = 更穩定，但可能漏掉插話
        minBargeInAudioEndMs: 200
```

### @discordjs/opus 選擇性安裝

Opus 編碼器對語音品質和延遲很重要：

```bash
# 推薦：安裝原生 Opus（效能最佳）
npm install @discordjs/opus

# 如果編譯失敗，使用純 JS 版本（較慢）
npm install opusscript
```

---

## 常見問題

### Echo / Feedback Loop（回音）

**現象**：AI 聽到自己的聲音，然後回應自己。

**解決**：
1. 使用者使用耳機（最推薦）
2. 啟用 Discord 的降噪和回音消除
3. 調高 `captureSilenceGraceMs`，避免過度敏感

### Barge-in 過敏（太容易被打斷）

**現象**：AI 說話時，背景噪音或呼吸聲就觸發打斷。

**解決**：
```yaml
realtime:
  minBargeInAudioEndMs: 400  # 從 200 調高
```

### Barge-in 遲鈍（打斷沒反應）

**現象**：使用者明確插話，但 AI 繼續講完。

**解決**：
```yaml
realtime:
  minBargeInAudioEndMs: 100  # 從 200 調低
  interruptResponseOnInputAudio: true  # 確認已啟用
```

### 語音品質差

**檢查項目**：
1. 是否安裝 `@discordjs/opus`？
2. Discord 伺服器區域是否靠近你的主機？
3. 網路延遲是否過高？

### Realtime 模式連不上

**檢查**：
1. OpenAI API Key 是否有 Realtime 權限？
2. 模型名稱是否正確：`gpt-realtime-2`
3. 查看 Gateway log 中的 `voice diagnostics` 訊息

---

## 診斷與監控

OpenClaw 2026.5.10 起提供 Realtime voice diagnostics：

```
[Voice] Speaker turn detected: user -> assistant
[Voice] Playback reset: barge-in triggered
[Voice] Latency: STT=120ms, Agent=800ms, TTS=150ms
```

這些日誌有助於排查延遲和打斷問題。可在 Gateway log 中搜尋 `Voice` 關鍵字。

---

## 相關文件

- [`talk.md`](./talk.md) — Talk / Realtime 語音會話系統總覽
- [`nodes.md`](./nodes.md) — Nodes 配對與遠端執行
- [`troubleshooting.md`](./troubleshooting.md) — 一般故障排除
