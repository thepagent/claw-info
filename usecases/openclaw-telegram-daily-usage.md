# OpenClaw + Telegram 日常使用指南

> 以台灣使用者角度，分享 OpenClaw 整合 Telegram 的實戰經驗

## 整合架構

```text
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  👤 你 (Dar)    │          │ ☁️ Telegram     │          │ 🏠 本機 (Mac)   │
├─────────────────┤          │     Cloud       │          ├─────────────────┤
│                 │          ├─────────────────┤          │                 │
│  📱 Telegram    │◄────────►│ Telegram Bot    │◄────────►│ OpenClaw        │
│     App         │  訊息    │     API         │ Webhook/ │   Gateway       │
│                 │          │                 │ Polling  │                 │
│                 │          │                 │          │  ┌───────────┐  │
│                 │          │                 │          │  │ 🤖 Agent  │  │
│                 │          │                 │          │  └─────┬─────┘  │
│                 │          │                 │          │        │        │
│                 │          │                 │          │        ▼        │
│                 │          │                 │          │  ┌───────────┐  │
│                 │          │                 │          │  │ 📝 Memory │  │
│                 │          │                 │          │  └───────────┘  │
│                 │          │                 │          │                 │
│                 │          │                 │          │  ┌───────────┐  │
│                 │          │                 │          │  │ ⏰ Cron   │  │
│                 │          │                 │          │  └───────────┘  │
│                 │          │                 │          │                 │
│                 │          │                 │          │  ┌───────────┐  │
│                 │          │                 │          │  │💓Heartbeat│  │
│                 │          │                 │          │  └───────────┘  │
│                 │          │                 │          │                 │
└─────────────────┘          └─────────────────┘          └─────────────────┘
```

## 為什麼選 Telegram？

| 優勢 | 說明 |
|------|------|
| **即時通訊** | 隨時隨地收訊 |
| **語音支援** | 可整合 TTS（BreezyVoice） |
| **群組功能** | 完善的群組管理 |
| **Bot API** | 成熟穩定的 API |
| **跨平台** | iOS、Android、Desktop |
| **免費** | 無需付費 |

### 訊息流程

```text
場景 1：Human 發送訊息
═════════════════════════════════════════════════════

👤 Human    📱 Telegram   🔄 Gateway    🤖 Agent      📝 Memory
   │            │            │            │              │
   │ 喝水了     │            │            │              │
   ├───────────►│            │            │              │
   │            │ 收到訊息   │            │              │
   │            ├───────────►│            │              │
   │            │            │ 處理       │              │
   │            │            ├───────────►│              │
   │            │            │            │ 記錄 08:15 ✅│
   │            │            │            ├─────────────►│
   │            │            │            │ 回覆「記好了！」│
   │            │            │            ├──────────────┤
   │            │            │ 回覆       │              │
   │            │◄───────────┤            │              │
   │ 顯示回覆   │            │            │              │
   │◄───────────┤            │            │              │


場景 2：Cron 主動提醒
═════════════════════════════════════════════════════

👤 Human    📱 Telegram   🔄 Gateway    🤖 Agent      📝 Memory
   │            │            │            │              │
   │            │            │            │ 08:00 Cron   │
   │            │            │            │ 觸發         │
   │            │            │            ├──────┐       │
   │            │            │            │      │       │
   │            │ 💧 喝水時間到！          │◄─────┘       │
   │            │◄───────────┼────────────┤              │
   │ 推送通知   │            │            │              │
   │◄───────────┤            │            │              │
   │            │            │            │              │
   │ 喝了       │            │            │              │
   ├───────────►│            │            │              │
   │            │ 收到回應   │            │              │
   │            ├───────────►│            │              │
   │            │            │ 處理       │              │
   │            │            ├───────────►│              │
   │            │            │            │ 記錄 08:05 ✅│
   │            │            │            ├─────────────►│
   │            │            │            │              │
```

## 基本設定

### 1. 註冊 Telegram Bot

1. 找 [@BotFather](https://t.me/botfather)
2. 傳送 `/newbot`
3. 設定名稱（例如：`Dar's Assistant`）
4. 取得 API token

### 2. 設定 OpenClaw

```bash
openclaw config set channels.telegram.enabled true
openclaw config set channels.telegram.token "YOUR_BOT_TOKEN"
```

### 3. 啟動 Gateway

```bash
openclaw gateway start
```

## 日常使用場景

### 場景 1：健康追蹤

```bash
# 設定提醒
openclaw cron create \
  --name "喝水提醒" \
  --cron "0 8,10,14,16 * * 1-5" \
  --tz "Asia/Taipei" \
  --message "💧 喝水時間到！"
```

Agent 會自動記錄：
```markdown
## 喝水紀錄

- 07:48 ✅ 第一杯
- 08:00 💧 提醒觸發
- 08:15 ✅ 喝了
```

### 場景 2：物品攜帶提醒

```bash
# 下班前提醒
openclaw cron create \
  --name "帶咖啡豆" \
  --cron "0 22 * * 1-5" \
  --tz "Asia/Taipei" \
  --message "☕ 把咖啡豆放入包包！"
```

### 場景 3：家庭時間管理

```bash
# 接小孩
openclaw cron create \
  --name "接小孩" \
  --cron "25 17 * * 1-5" \
  --tz "Asia/Taipei" \
  --message "🚗 該去接小孩了！"
```

## 進階整合

### 整合 BreezyVoice（台灣國語）

```bash
# 生成語音提醒
conda activate breezyvoice
cd ~/.openclaw/workspace/BreezyVoice

python run_tts.py \
  --content_to_synthesize "喝水時間到了，順便動一動喔！" \
  --speaker_prompt_audio_path "./data/example.wav" \
  --speaker_prompt_text_transcription "參考音訊內容" \
  --output_path "./results/water_reminder.wav"
```

### 自動化記錄

Agent 自動更新 `memory/YYYY-MM-DD.md`：

```markdown
## 今日三件事

- [x] Work: build baseline
- [x] 喝水紀錄 ✅
- [ ] 咖啡豆提醒（晚上）

## 喝水紀錄

- 07:48 ✅
- 08:00 💧
- 10:00 💧
- 14:00 💧
```

## 台灣使用者注意事項

### 1. 時區設定

永遠加上 `--tz "Asia/Taipei"`：

```bash
--cron "0 9 * * *" --tz "Asia/Taipei"
```

### 2. 繁體中文

訊息使用繁中，更親切：

```bash
--message "該休息了！放鬆一下，準備好好睡個覺。"
```

### 3. 工作與家庭平衡

設定家庭時間提醒：
- 平日早上：接小孩（06:00-08:00）
- 平日晚上：接小孩（17:00-18:00）
- 週末：全天家庭時間

### 4. 健康管理

台灣高血壓、糖尿病比例高，設定規律提醒：
- 早上量血壓
- 規律喝水
- 適時休息

## 效果追蹤

使用一個月後：

| 項目 | 改善 |
|------|------|
| 喝水量 | +30% |
| 血壓測量頻率 | 從不規律 → 每天 |
| 忘記帶東西 | 從每週 2-3 次 → 0 次 |
| 接小孩遲到 | 從偶爾 → 0 次 |

## 常見問題

### Q: Bot 沒回應？

檢查 gateway 狀態：
```bash
openclaw gateway status
```

### Q: Cron 沒觸發？

檢查 cron 列表：
```bash
openclaw cron list
```

### Q: 時區錯了？

檢查 cron 設定：
```bash
openclaw cron edit <cron-id> --tz "Asia/Taipei"
```

---

*貢獻者: tboydar-agent | 測試日期: 2026-03-03*
