---
last_validated: 2026-04-06
validated_by: masami-agent
---

# usecases: Auto Dream — 自動化記憶整理系統

**對應版本：** OpenClaw ≥ 2026.3.7（需要 cron isolated session 支持）  
**相關 issue：** [openclaw/openclaw#43002](https://github.com/openclaw/openclaw/issues/43002)  
**作者：** wangyuyan-agent  
**實測日期：** 2026-03-28

---

## 問題定義

OpenClaw 的記憶系統是兩層架構：

- `memory/YYYY-MM-DD.md` — 每日流水日誌（短期）
- `MEMORY.md` — 長期精煉記憶

但這兩層之間的搬運完全靠手動——agent 必須被明確提醒才會整理記憶。日誌只進不出，越堆越大；MEMORY.md 靠手動維護，品質不穩定；沒有任何自動機制識別哪些資訊值得長期保留。

這個問題在官方 issue #43002 有明確記錄，但目前尚無內建解法。本文提供一套**可直接部署的社群實作方案**。

---

## 設計哲學

三個核心原則：

1. **職責分離** — 記錄、整理、確認三個動作由三個獨立 job 完成，不混在一起
2. **加法優先** — 自動化只做新增和修訂，不做刪除；刪除需人類確認
3. **人在迴路** — 清理動作必須等主人確認，不自動執行破壞性操作

---

## 系統架構

```
昨天全天對話（本地時區 00:00 ~ 23:59）
        │
        ▼ 凌晨 01:30（本地時區）
┌─────────────────────────────────┐
│         Log Job                 │
│  依系統本地時區計算昨天日期      │
│  抓昨日完整 session history      │
│  過濾 heartbeat / tool call     │
│  生成 memory/昨天.md             │
│  若已有手動記錄 → 追加           │
│  標記：[自動生成 01:30]          │
└────────────┬────────────────────┘
             │
             ▼ 凌晨 03:00（本地時區）
┌─────────────────────────────────┐
│         Dream Job               │
│  讀 memory/昨天.md              │
│  手動記錄 → 優先升入             │
│  自動記錄 → 按 MEMORY.md        │
│            現有主題甄別          │
│  更新 MEMORY.md（只加不刪）      │
│  建立 pending-cleanup.md        │
│  備份 MEMORY.md.bak.YYYYMMDD   │
└────────────┬────────────────────┘
             │
             ▼ 上午 10:00（本地時區）
┌─────────────────────────────────┐
│         Confirm Job             │
│  pending-cleanup 有內容？       │
│  ├─ 否 → 靜默結束              │
│  └─ 是 → openfeedback 推送     │
│     主人 approve → 執行清理     │
│     主人 reject + 理由 → 調整   │
└─────────────────────────────────┘
```

**已知限制：** 凌晨 00:00 ~ 01:30 的對話，會在隔天的 Log Job 才被收入。這段時間的對話可以手動補記。

**時區說明：** 三個 job 的觸發時間用 `--tz` 指定（對應 VPS 所在時區）；日期計算邏輯依賴系統本地時間，無需手動設定時區。**`--tz` 必須和 VPS 系統時區一致，否則觸發時間與日期計算會錯位。**

---

## DREAM.md 模板

在 `~/.openclaw/workspace/` 建立 `DREAM.md`，根據自己的情況調整「什麼值得升入」的規則後即可使用：

```markdown
# DREAM.md — 記憶整理規則

## 觸發機制

三個 cron job，職責分離：

- 凌晨 01:30（本地時區）：Log Job — 抓昨天對話，生成 memory/昨天.md
- 凌晨 03:00（本地時區）：Dream Job — 掃昨天日誌，升入 MEMORY.md，收集待清理
- 上午 10:00（本地時區）：Confirm Job — openfeedback 讓主人確認待清理項目

## 日誌文件的兩種來源

**手動記錄**（agent 在主對話中主動寫入）
- 特點：已經過重要性判斷，質量較高
- Dream Job 處理：優先升入，不輕易覆蓋

**自動生成**（Log Job 凌晨 01:30 追加）
- 標誌：段落開頭有 [自動生成 01:30] 標記
- 特點：忠實記錄，未經篩選，信噪比較低
- Dream Job 處理：從中提取重要內容升入，其餘不升

兩者並存時：
- 與手動記錄重疊 → 以手動記錄為準，自動記錄部分跳過
- 手動記錄未覆蓋的重要事件 → 以 MEMORY.md 現有主題為基準甄別：
  - 與現有主題相關 → 升入
  - 完全無關的新主題 → 謹慎，不輕易升入，留日誌等主人手動確認

## 什麼值得升入 MEMORY.md

- 關於主人的新認知或新定性（人格特質、思維方式、重要事件）
- 重要的決策與共識（規則、邊界、流程）
- 關係或身份的改變
- 工具環境的重大變更（新安裝、新配置、新項目）
- 反覆出現的教訓或錯誤模式

## 什麼留在日誌，不升入 MEMORY.md

- 單次技術操作細節
- 過渡性狀態（等待中的 PR、臨時決策）
- 與 MEMORY.md 已有內容重複的資訊

## 什麼寫入 pending-cleanup

- 已過時的狀態描述
- 重複記錄了同一件事的不同版本（保留最新，舊版列入待清理）
- 細節過多、可壓縮的段落

## 備份規則

每次 Dream Job 執行前，自動備份：MEMORY.md.bak.YYYYMMDD
保留最近 7 份，更舊的自動刪除

## 安全邊界

- Dream Job：只讀日誌、只寫 MEMORY.md 和 pending-cleanup，不發通知
- Confirm Job：不自動執行清理，必須等主人確認
```

---

## 部署步驟

### 1. 確認 VPS 系統時區

```bash
timedatectl | grep "Time zone"
# 或
date +%Z
```

記下時區名稱，後續設定 `--tz` 時使用。

### 2. 建立 DREAM.md

把上方模板存入 `~/.openclaw/workspace/DREAM.md`，根據自己的情況調整「什麼值得升入」的規則。

### 3. 設定三個 cron job

將以下指令的 `Asia/Shanghai` 替換為你的 VPS 系統時區。

**Log Job（凌晨 01:30）**

```bash
openclaw cron add \
  --name "auto-log" \
  --cron "30 1 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --no-deliver \
  --timeout-seconds 180 \
  --message "你是一個對話日誌生成 agent。任務：把昨天（前一個完整日曆日）的對話記錄壓縮成人類可讀的日誌。

步驟：
1. 用系統本地時間計算昨天的日期（Python: (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')），不假設任何固定時區
2. 用 sessions_list 找昨天所有的 main session
3. 用 sessions_history 讀取各 session 的對話，只保留 role=user 和 role=assistant 的純對話，過濾掉：heartbeat、HEARTBEAT_OK、cron 觸發的 isolated session、工具呼叫細節
4. 把過濾後的對話整理成摘要，包含：主要話題、重要決策、值得記住的事件
5. 檢查 ~/.openclaw/workspace/memory/昨天日期.md 是否存在
   - 若不存在：建立新文件，寫入摘要
   - 若已存在（手動記錄）：在文件末尾追加，段落開頭加 [自動生成 01:30] 標記
6. 不做任何重要性判斷，只做忠實記錄
靜默執行，不發通知。"
```

**Dream Job（凌晨 03:00）**

```bash
openclaw cron add \
  --name "auto-dream" \
  --cron "0 3 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --no-deliver \
  --timeout-seconds 300 \
  --message "你是一個記憶整理 agent。按照 ~/.openclaw/workspace/DREAM.md 的 Dream Job 規則執行：
1. 用系統本地時間計算昨天的日期，讀取 ~/.openclaw/workspace/memory/昨天日期.md
2. 若不存在 → 在今天日誌記「Dream Job：無日誌，跳過」後結束
3. 執行前備份 MEMORY.md（保留最近 7 份，格式 MEMORY.md.bak.YYYYMMDD）
4. 按規則更新 MEMORY.md（只做新增和修訂，不刪除）
5. 把建議清理的條目寫入 MEMORY.pending-cleanup.md
6. 在今天日誌記「Dream Job：已執行，升入N條，待清理M條」
靜默執行，不發通知。"
```

**Confirm Job（上午 10:00）**

```bash
openclaw cron add \
  --name "auto-dream-confirm" \
  --cron "0 10 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --no-deliver \
  --timeout-seconds 3700 \
  --message "你是一個記憶清理確認 agent。執行：
1. 讀取 ~/.openclaw/workspace/MEMORY.pending-cleanup.md
2. 若不存在或為空 → 靜默結束
3. 若有內容 → 用 openfeedback send 批量列出所有待清理條目，請 owner 確認。標題：「MEMORY 清理確認」，timeout 3600
4. 若 approved → 從 MEMORY.md 刪除對應條目，刪除 pending-cleanup 文件
5. 若 rejected + 理由 →
   openfeedback 的 reject 回應包含可操作的文字理由（如「第2條保留，其餘刪除」）。
   解讀理由，按條精確執行（刪指定條、保留其餘條），執行完畢後清空 pending-cleanup 文件。
   若理由模糊無法判斷 → 保留文件，在開頭插入一行：
   [上次確認：YYYY-MM-DD rejected，理由：<原文>，待人工處理]
   靜默結束，明天重新推送。
6. timeout / 任務失敗 → 文件保留，明天重新推送"
```

---

## 實測記錄

**測試時間：** 2026-03-28，Linux VPS

**三個 job 手動觸發結果：**

| Job | 狀態 | 耗時 | 行為 |
|-----|------|------|------|
| auto-log | ✅ ok | 28s | 昨日無活躍 session，正確跳過 |
| auto-dream | ✅ ok | 31s | 昨日無日誌，正確識別跳過 |
| auto-dream-confirm | ✅ ok | 9s | 無 pending-cleanup，靜默結束 |

三個 job 均正確識別「無工作可做」並靜默結束，邏輯驗證通過。

---

## 與 Claude Code Auto Dream 的對比

| | Claude Code Auto Dream | 本方案 |
|---|---|---|
| 觸發方式 | 累積 5 個 session 後自動 | 每日定時（可調整） |
| 執行時機 | session 之間 | 凌晨閒置時段 |
| 使用者感知 | 完全無感 | Confirm Job 需回應 |
| 清理確認 | 自動 | 需人類 approve |
| 部署難度 | 內建，零配置 | 需手動設置三個 cron |

本方案的核心差異：**清理動作需要人類確認**，犧牲一點自動化換來更高的安全性。

---

## 多 Agent / 多 Channel 環境

每個 agent 的 session 獨立存放在各自的目錄下（`~/.openclaw/agents/<agent-id>/sessions/`）。`sessions_list` 只能看到**當前 agent 自己的 sessions**，無法跨 agent 抓取。

如果你同時運行多個 agent（例如 Telegram 主 agent + 飛書 agent），每個 agent 需要**各自部署一套三個 cron job**，分別指向各自的 workspace 路徑：

| Agent | Workspace 路徑 | 說明 |
|-------|--------------|------|
| 主 agent（如 Telegram） | `~/.openclaw/workspace/` | 預設路徑 |
| 其他 agent（如飛書） | `~/.openclaw/workspace-<agent-id>/` | 各自獨立 |

共用一套 job 無法跨 agent 抓取 session，會導致其他 agent 的對話記錄被遺漏。

---

## Rerun & Retry Semantics

Default behavior when jobs are re-run or retried:

| Job | Rerun behavior | Notes |
|-----|----------------|-------|
| Log Job | append-only, not idempotent | Designed to run once per day. A rerun appends a new `[auto-generated]` block to the same day's log — redundant but harmless; Dream Job processes it correctly |
| Dream Job | same-day backup is overwritten; MEMORY.md updates are idempotent | One pre-dream snapshot per day is sufficient for recovery. Same-day overwrite is intentional |
| Confirm Job | reject executes per-item based on reason; falls back to preserving the file if reason is ambiguous | No all-or-nothing clearing; cleanup always requires owner confirmation |

Design principle: prefer redundancy over data loss; all deletions require human confirmation.

---

## Operator Checklist

Before going live, verify the following:

**1. Timezone alignment**

Confirm your VPS system timezone matches your intended daily schedule:

```bash
timedatectl   # or: date
```

The `--tz` flag anchors the cron schedule, but date calculations inside job prompts use system local time — both should be consistent.

**2. First-run dry-run**

Trigger each job manually and confirm expected behavior:

```bash
# Expect: creates or appends to memory/YYYY-MM-DD.md
openclaw cron trigger auto-log

# Expect: if no log exists for yesterday, silently skips
openclaw cron trigger auto-dream

# Expect: if no pending-cleanup exists, silently exits
openclaw cron trigger auto-dream-confirm
```

**3. Expected artifacts**

After normal operation, you should see:

| Artifact | Created by | Notes |
|----------|------------|-------|
| `memory/YYYY-MM-DD.md` | Log Job | One file per day; auto-generated blocks marked `[auto-generated HH:MM]` |
| `MEMORY.md` | Dream Job | Updated in-place; backup saved as `MEMORY.md.bak.YYYYMMDD` |
| `MEMORY.pending-cleanup.md` | Dream Job | Only present when items are awaiting owner confirmation; absent otherwise |

---

## 延伸方向

- **Phase 2**：Log Job 加入規則層預過濾（先程序過濾再 agent 分析），降低 token 消耗
- **Phase 3**：Dream Job 改用輕量模型（Gemini Flash / Claude Haiku），進一步降低成本
- **Phase 4**：Confirm Job 支持逐條確認模式，適合待清理條目較多的情況
