# OpenClaw Cron 調度系統

## 概述

OpenClaw Cron 是一個內建的強大定時任務系統，讓您能夠以宣告式方式規劃 Agent 任務的執行時間。

**首次引入版本：** `2026.1.8`

---

## 解決的問題

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       傳統定時任務的痛點                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  痛點 1：環境不一致                                                         │
│    • Crontab 在不同機器上配置分散                                           │
│    • 環境變數與路徑難以管理                                                 │
│    • 跨系統部署困难                                                         │
│                                                                             │
│  痛點 2：狀態無從追蹤                                                       │
│    • 無法得知任務是否成功執行                                               │
│    • 錯誤日誌分散在各處                                                     │
│    • 無法重試失敗任務                                                       │
│                                                                             │
│  痛點 3：缺乏 Agent 整合                                                    │
│    • Crontab 只能執行 shell 指令                                           │
│    • 無法調用 Agent 的工具與知識                                            │
│    • 難以實現複杂業務邏輯                                                   │
│                                                                             │
│  痛點 4：安全性考量                                                         │
│    • Root 權限任務風險                                                      │
│    • 敏感資料暴露於環境變數                                                 │
│    • 無法精細控制 Agent 權限                                                │
│                                                                             │
│  痛點 5：監控與排錯困難                                                     │
│    • 無法查看歷史執行記錄                                                   │
│    • 錯誤訊息難以定位                                                       │
│    • 缺乏執行時隔離                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   OpenClaw Cron 帶來的價值                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✓ 環境一致性：單一配置檔案，所有環境相同                                   │
│  ✓ 狀態追蹤：實時查看任務執行結果                                           │
│  ✓ Agent 整合：調用 Agent 的知識與工具                                      │
│  ✓ 代碼即配置：Git 維護配置，CI/CD 憑證                                     │
│  ✓ 安全隔離：可選 Sandbox 模式，權限最小化                                 │
│  ✓ 監控排錯：完整執行記錄，錯誤自動重試                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 架構

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OpenClaw Cron 架構圖                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐                                                         │
│   │   Gateway    │                                                         │
│   │  Cron Job    │                                                         │
│   │  Scheduler   │                                                         │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐      ┌─────────────────────────────────────────┐        │
│   │ Schedule     │─────▶│  job.kind = systemEvent                 │        │
│   │   Engine     │      │  - Injects text into main session       │        │
│   │              │      │  - For simple reminders/notifications   │        │
│   └──────────────┘      └─────────────────────────────────────────┘        │
│                                                                             │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐      ┌─────────────────────────────────────────┐        │
│   │  Trigger     │─────▶│  job.kind = agentTurn                   │        │
│   │              │      │  - Spawns isolated sub-agent session    │        │
│   │              │      │  - Runs with dedicated agent            │        │
│   └──────────────┘      └─────────────────────────────────────────┘        │
│                                                                             │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │   Session    │                                                         │
│   │  Delivery    │                                                         │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │   Channel    │                                                         │
│   │  Plugin      │                                                         │
│   └──────────────┘                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心概念

### 調度類型 (Schedule Types)

| 類型 | 描述 | 適用場景 |
|------|------|---------|
| `at` | 單次執行，在指定時間點執行 | 一次性任務、提醒 |
| `every` | 週期性執行，以固定間隔執行 | 定期檢查、輪詢 |
| `cron` | Cron 表達式，精確控制時間 | 複雜排程、系統任務 |

#### at - 單次執行

```yaml
schedule:
  kind: at
  at: "2026-02-20T10:00:00Z"  # ISO-8601 UTC timestamp
```

#### every - 週期性執行

```yaml
schedule:
  kind: every
  everyMs: 3600000  # 每小時 (毫秒)
  anchorMs: 1700000000000  # 可選：起始時間戳
```

#### cron - Cron 表達式

```yaml
schedule:
  kind: cron
  expr: "0 9 * * 1-5"  # 工作日早上 9 點
  tz: "America/New_York"  # 可選：時區
```

**支援的 Cron 格式：**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6, Sunday = 0)
│ │ │ │ │
* * * * *
```

### 貼 payload 類型 (Payload Types)

| 類型 | 描述 | sessionTarget |
|------|------|--------------|
| `systemEvent` | 將文字注入會話 | `main` |
| `agentTurn` | 啟動獨立 Agent 會話 | `isolated` |

#### systemEvent - 會話事件

```yaml
payload:
  kind: systemEvent
  text: "Read HEARTBEAT.md if it exists. Follow it strictly."
```

**特點：**
- 將文字作為系統訊息注入
- 適用於簡單提醒、通知
- 主要用于 `main` session

#### agentTurn - Agent 任务

```yaml
payload:
  kind: agentTurn
  message: "Please check the latest GitHub issues and summarize."
  model: "amazon-bedrock/qwen.qwen3-next-80b-a3b"
  thinking: "on"
  timeoutSeconds: 300
```

**特點：**
- 啟動獨立的 sub-agent session
- 可指定不同模型、thinking 設定
- 適用於複雜任務、隔離執行

### 傳送模式 (Delivery Modes)

只有 `isolated` session 支援 `delivery` 設定：

| 模式 | 描述 |
|------|------|
| `none` | 不傳送結果 |
| `announce` | 將結果傳送到 session 的預設頻道 |

```yaml
delivery:
  mode: announce
  channel: "telegram:176096071"
  to: "176096071"
  bestEffort: true
```

---

## 使用範例

### 範例 1：每日早晨提醒

**觸發時間：** 每个工作日早上 8:30 (EST)

```yaml
name: "每日工作開始提醒"
schedule:
  kind: cron
  expr: "30 8 * * 1-5"
  tz: "America/New_York"
payload:
  kind: systemEvent
  text: |
    主公早安！今天的工作已經準備就緒。
    
    已排程的任務：
    - 每日 GitHub issue 摘要
    - 天氣預報
    - 日曆事件提醒
```

### 範例 2：每小時 GitHub 檢查

**觸發時間：** 每小時整點

```yaml
name: "GitHub Issue 監控"
schedule:
  kind: every
  everyMs: 3600000  # 1 小時
payload:
  kind: agentTurn
  message: |
    請檢查 claw-info 倉庫的未解決 issue，
    滙總重要問題並報告狀態。
  model: "amazon-bedrock/qwen.qwen3-next-80b-a3b"
  timeoutSeconds: 120
delivery:
  mode: announce
```

### 範例 3：單次任務 - 定點執行

**觸發時間：** 2026 年 2 月 25 日下午 3 點

```yaml
name: "系統維護通知"
schedule:
  kind: at
  at: "2026-02-25T15:00:00-05:00"
payload:
  kind: systemEvent
  text: "⚠️ 系統即將進行維護，請儲存工作。"
```

### 範例 4：週末備份確認

**觸發時間：** 每週六和週日早上 10:00

```yaml
name: "週末備份確認"
schedule:
  kind: cron
  expr: "0 10 * * 0,6"
payload:
  kind: agentTurn
  message: |
    請檢查昨晚的備份狀態，確認所有重要資料已成功備份。
    報告：備份成功/失敗、 missing backups
  timeoutSeconds: 60
delivery:
  mode: announce
```

---

## 實作細節

### Cron Job 狀態

| 狀態 | 描述 |
|------|------|
| `pending` | 作業已建立，等待執行 |
| `running` | 正在執行中 |
| `completed` | 已成功完成 |
| `failed` | 執行失敗 |
| `skipped` | 被跳過（例如：上一次執行未完成） |

### 錯誤處理

Cron 作業失敗時的行為：

1. **重試機制：**
   - 作業失敗後會自動重試 3 次
   - 每次重試間隔 5 分鐘

2. **失敗通知：**
   - 可設定 `delivery` 至特定頻道
   - 包含錯誤訊息與堆疊追蹤

3. **查看記錄：**
   ```bash
   openclaw cron runs <job_id>
   ```

### 限制與最佳實踐

| 項目 | 限制 | 建議 |
|------|------|------|
| 作業超時 | 最長 1 小時 | 長時間任務使用 `timeoutSeconds` |

--- 

## 常見問題

### Q1: Cron 任務會在 Gateway 重啟後保持嗎？

**A:** 会。Cron 作業狀態會持久化到 Gateway db，重啟後繼續排程。

### Q2: 多個 Gateway 實例會重複執行嗎？

**A:** 不會。Cron Scheduler 是單例的，即使多 Gateway 實例也不會重複執行。

### Q3: 能否動態調整排程？

**A:** 可以。使用 `openclaw gateway restart` 重新加载配置。

### Q4: Cron job 找不到指令（如 `npm`、`node`）？

**A:** OpenClaw cron 的 isolated session 使用精簡的 PATH，不會繼承使用者的 shell 環境（如 fnm、nvm、pyenv 等）。

解法：在腳本或 message 中使用**絕對路徑**：

```bash
# 錯誤：依賴 PATH
LATEST=$(npm show openclaw version)

# 正確：使用絕對路徑
NPM=/home/<user>/.local/share/fnm/node-versions/<version>/installation/bin/npm

LATEST=$($NPM show openclaw version)
```

同理，若直接在 `--message` 中執行指令，也應使用絕對路徑。

### Q5: Cron job exec 一直卡在「需要批准」？

**A:** `host=gateway` 時，exec 預設需要人工批准（`tools.exec.ask=on-miss`）。建議用 allowlist 白名單腳本路徑，而非全域關閉安全機制：

**推薦做法：allowlist 白名單（較安全）**

編輯 `~/.openclaw/exec-approvals.json`，將腳本目錄加入白名單：

```json
{
  "agents": {
    "main": {
      "security": "allowlist",
      "ask": "off",
      "allowlist": [
        { "pattern": "/home/<user>/.openclaw/scripts/*" }
      ]
    }
  }
}
```

全域維持嚴格設定：

```bash
openclaw config set tools.exec.host gateway
openclaw config set tools.exec.security allowlist
openclaw config set tools.exec.ask on-miss
systemctl --user restart openclaw-gateway.service
```

這樣只有 `scripts/` 下的腳本可不經批准執行，其他指令一律拒絕。

| 設定 | 說明 |
|------|------|
| `tools.exec.host` | `gateway`：在 gateway host 執行（可存取完整 PATH） |
| `tools.exec.ask` | `off`：不要求批准；`on-miss`（預設）：allowlist 未命中時要求批准 |
| `tools.exec.security` | `allowlist`：只允許白名單內的指令；`full`：允許任意指令（不建議） |

> ⚠️ 避免使用 `security=full`，它允許 agent 執行任意指令。

### Q6: Cron job 跑完後 agent 把結果 announce 到 Telegram，但我只想讓腳本自己控制通知？

**A:** 預設 `delivery.mode=announce` 會把 agent 的執行結果推送到頻道，導致多餘訊息。改為 `none`：

```bash
openclaw cron edit <id> --no-deliver
```

這樣只有腳本內明確呼叫 `openclaw message send` 時才會送出 Telegram 訊息，agent 的執行摘要不會自動推送。

---

## 已知問題（Open Issues）

### 🔴 Bugs

| Issue | 標題 | 說明 | 狀態 |
|-------|------|------|------|
| [#18120](https://github.com/openclaw/openclaw/issues/18120) | runningAtMs 永不自動清除 | Session timeout 後 runningAtMs 未清除，導致 cron 永久停止執行 | ✅ 已修復 (2026-02-22) |
| [#17979](https://github.com/openclaw/openclaw/issues/17979) | cron tool 從 main session 呼叫超時 | cron.status WS frame 無回應，但 cron job 本身正常執行 | ✅ 已修復 (2026-02-22) |
| [#17599](https://github.com/openclaw/openclaw/issues/17599) | WhatsApp delivery 間歇性失敗 | ~20% 機率出現 `cron delivery target is missing` 錯誤 | ✅ 已關閉 (stale, 2026-02-23) |
| [#16156](https://github.com/openclaw/openclaw/issues/16156) | 週期性 cron job 不執行 | `schedule.kind: "cron"` 只更新 nextRunAtMs 但不觸發執行 | ✅ 已修復 (2026-02-20) |
| [#16054](https://github.com/openclaw/openclaw/issues/16054) | 自訂 provider 靜默重命名 | provider 名稱被改寫，導致 cron job 報 "model not allowed" | ✅ 已關閉 (stale, 2026-02-22) |
| [#14751](https://github.com/openclaw/openclaw/issues/14751) | cron list Gateway 超時 | `cron list` 回傳 60s+ 超時，但 job 正常執行 | ✅ 已修復 (2026-02-22) |
| [#12440](https://github.com/openclaw/openclaw/issues/12440) | cron list 導致排程被跳過 | 呼叫 `cron list` 後 recomputeNextRuns() 跳過未執行的 job | 🔴 仍開啟 (stale) |

### 🟢 Feature Requests

| Issue | 標題 | 說明 | 狀態 |
|-------|------|------|------|
| [#13900](https://github.com/openclaw/openclaw/issues/13900) | Ephemeral Cron Sessions | 請求 cron session 執行後自動清除，避免 token 累積 | 🟡 開啟中 |
| [#13598](https://github.com/openclaw/openclaw/issues/13598) | Cron 故障排除手冊 | 請求新增 cron troubleshooting playbook 文件 | 🟡 開啟中 |
| [#12736](https://github.com/openclaw/openclaw/issues/12736) | tools.cron.tools.deny 設定 | 請求 cron job 層級的工具限制設定 | 🟡 開啟中 |

---

## OS cron 與 OpenClaw cron 比較

### 核心差異

OS cron 直接執行 shell 指令，行為完全確定（deterministic）——腳本寫什麼就跑什麼，不受任何外部因素影響。

OpenClaw cron 本質上是**透過 prompt 驅動 agent 去做某件事**。即使 message 寫得再明確，LLM 的行為仍是非確定性的（non-deterministic）——agent 可能正確執行，也可能偏離指令、加入額外判斷、或產生非預期的副作用。這是使用 AI agent 做自動化時必須接受的根本限制。

此外，OpenClaw cron 每次執行都會消耗 LLM token；當所有 LLM provider 都失敗（quota 耗盡、API 故障、憑證過期）時，cron job 也會跟著失敗——而這往往正是你最需要自動化任務正常運作的時候。

> 因此，對於**不需要 AI 判斷、邏輯已固定**的任務，OS cron 的可靠性天生優於 OpenClaw cron。

### 比較表

| 項目 | OS cron | OpenClaw cron |
|------|---------|---------------|
| Gateway 掛掉時仍能執行 | ✅ 完全獨立於 gateway，即使 openclaw 服務掛掉仍正常執行 | ❌ scheduler 在 gateway 程序內，gateway 掛掉則排程停止 |
| 執行歷史記錄 | ❌ 需自行將 stdout/stderr 導向 log 檔，無結構化查詢 | ✅ `openclaw cron runs <id>` 可查每次執行時間、狀態、duration |
| 集中管理 / 可見性 | ❌ 分散在各機器的 crontab，需 `crontab -l` 才能查看 | ✅ `openclaw cron list` 一覽所有排程，含下次執行時間與狀態 |
| 即時觸發測試 | ❌ 需等待下一個時間點，或手動執行腳本 | ✅ `openclaw cron run <id>` 立即觸發，方便除錯 |
| Agent 整合 / 工具呼叫 | ❌ 純 shell，無法呼叫 LLM 工具、memory、browser 等 | ✅ agentTurn 可使用完整工具集，適合需要 AI 判斷的任務 |
| 直接執行 shell script | ✅ 直接執行，無中間層，行為完全可預測 | ⚠️ 透過 agent exec 間接執行，需在 message 明確指定 `and nothing else` |
| 不依賴 LLM 判斷 | ✅ 邏輯完全由 shell script 控制，不受模型行為影響 | ⚠️ agentTurn 仍由 LLM 解讀 message，有偏離指令的風險 |
| Telegram 通知整合 | ⚠️ 需在腳本內自行呼叫 `openclaw message send` | ✅ 原生支援 `--announce`，結果自動推送至指定頻道 |

### OS cron 還是 OpenClaw cron？何時用哪個

- **用 OS cron**：任務需在 gateway 掛掉時仍能執行（如 SSO refresh、gateway 健康監控）
- **用 OpenClaw cron**：任務依賴 gateway 運作（如版本檢查通知、需要 agent 判斷的任務）

### 當邏輯全在 shell script 時：OpenClaw cron + 強制執行模式

當任務邏輯完全封裝在 shell script 內，不需要 AI 判斷，只需要確實執行時，可使用 OpenClaw cron 搭配明確指令來降低 agent 偏離風險：

```bash
openclaw cron edit <id> --message "Run bash /path/to/script.sh and nothing else"
```

這樣做的好處：
- 保留 OpenClaw cron 的可見性與歷史記錄優勢
- 透過明確的 `and nothing else` 限制 agent 自由發揮空間
- 適用於：版本檢查、定期清理、狀態回報等邏輯已固定的任務

> ⚠️ 注意：agent 仍有偏離可能，若需要 100% 確實執行且不依賴 gateway，應改用 OS cron。

---

## 更新紀錄

- **2026-02-24**：新增 Q5（exec 批准問題）、Q6（delivery 亂送 TG）常見問題
- **2026-02-23**：新增「OS cron 與 OpenClaw cron 比較」章節
- **2026-02-17**：新增「已知問題」章節
- **2026-02-16**：建立文件，涵蓋核心概念與範例

---

*最後更新：2026-02-23*
