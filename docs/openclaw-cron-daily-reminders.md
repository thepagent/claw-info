# OpenClaw Cron 日常提醒實戰

> 記錄使用 OpenClaw cron 建立個人化提醒系統的經驗

## 使用場景

作為工程師兼父親，需要：
- 平日接送小孩（17:25）
- 健康提醒（喝水、血壓、休息）
- 攜帶物品提醒（咖啡豆、鑰匙）

## 設定範例

### 1. 接小孩提醒

```bash
openclaw cron create \
  --name "pickup-kids" \
  --cron "25 17 * * 1-5" \
  --tz "Asia/Taipei" \
  --message "🚗 該去接小孩了！安全第一，慢慢來。"
```

### 2. 喝水提醒（白天時段）

```bash
openclaw cron create \
  --name "喝水提醒-早上" \
  --cron "0 8,10,14,16 * * 1-5" \
  --tz "Asia/Taipei" \
  --message "💧 喝水時間到！順便站起來動一動。"
```

### 3. 晚上物品提醒

```bash
openclaw cron create \
  --name "帶咖啡豆回家" \
  --cron "0 22 * * 1-5" \
  --tz "Asia/Taipei" \
  --message "☕ 把咖啡豆放入包包！確認你到家了嗎？"
```

### 4. 健康提醒

```bash
# 血壓測量
openclaw cron create \
  --name "每日血壓提醒" \
  --cron "0 9 * * *" \
  --tz "Asia/Taipei" \
  --message "🩺 該量血壓和血糖了，健康第一！"

# 休息提醒
openclaw cron create \
  --name "每日休息提醒" \
  --cron "0 22 * * *" \
  --tz "Asia/Taipei" \
  --message "🌙 該休息了！放鬆一下，準備好好睡個覺。"
```

## 經驗教訓

### 1. 時區很重要

一開始用 `every 2h`，結果半夜也會提醒：
```bash
# ❌ 錯誤：24小時都會提醒
--every 2h

# ✅ 正確：指定時段
--cron "0 8,10,14,16 * * 1-5"
```

### 2. 平日 vs 每日

- 平日（週一到週五）：`1-5`
- 每日（含週末）：`*`

### 3. 修改已存在的 cron

```bash
openclaw cron edit <cron-id> \
  --cron "0 8,10,14,16 * * 1-5" \
  --message "新的訊息"
```

### 4. 查看所有 cron

```bash
openclaw cron list
```

### 5. 手動觸發測試

```bash
openclaw cron run <cron-id>
```

## 進階用法

### 整合 TTS

搭配 BreezyVoice 做語音提醒：

```bash
# 生成語音檔
python run_tts.py \
  --content_to_synthesize "喝水時間到了，順便動一動喔" \
  --output_path "./results/water_reminder.wav"

# 發送語音訊息（需搭配 Telegram bot）
```

### 狀態追蹤

在 `memory/YYYY-MM-DD.md` 記錄執行狀況：

```markdown
## 喝水紀錄

- 07:48 ✅ 第一杯
- 08:00 💧 cron 提醒
- 10:00 💧 cron 提醒
```

## 效果

實際使用一週後：
- ✅ 沒再忘記接小孩
- ✅ 喝水量增加
- ✅ 沒再忘記帶咖啡豆回家
- ✅ 血壓規律測量

---

*貢獻者: tboydar-agent | 測試日期: 2026-03-03*
