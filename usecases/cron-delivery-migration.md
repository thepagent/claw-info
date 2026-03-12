# Cron Delivery 遷移指南（v2026.3.11 Breaking Change）

## 背景

v2026.3.11 收緊了 isolated cron job 的通知路徑（[#40998](https://github.com/openclaw/openclaw/pull/40998)）。

**Breaking Change 核心：**
Isolated session 的 cron job **不再能**透過以下方式發送通知：
- Ad hoc agent send（直接在 isolated session 裡呼叫 `message` tool 發送）
- Fallback main-session summary（讓 main session 代為彙總）

**影響對象：** 升級前有使用 isolated cron job 且依賴上述通知方式的所有部署。

---

## 如何確認是否受影響

### 方法一：`openclaw doctor --fix`（推薦）

```bash
openclaw doctor --fix
```

若有需要遷移的 legacy cron storage 或 notify/webhook delivery metadata，doctor 會自動偵測並修復。

**實際執行範例（Linux VPS, v2026.3.11）：**

無舊版 cron 需要遷移時輸出：

```
┌  OpenClaw doctor
│
◇  Doctor warnings
│  - channels.telegram.groupPolicy is "allowlist" but groupAllowFrom is empty
│    — all group messages will be silently dropped.
└  Done
```

若有 legacy cron 需要遷移，doctor 會在 State integrity 段落列出偵測結果，例如：

```
◇  State integrity
│  - Legacy cron job storage detected at ~/.openclaw/cron/jobs.json.
│  - 1 job still uses legacy `jobId`
│  - 1 job still uses `schedule.cron`
│  - 1 job still uses top-level payload fields
│  - 1 job still uses top-level delivery fields
│  Repair with openclaw doctor --fix to normalize the store before the
│  next scheduler run.
```

doctor 會靜默地將 jobs.json 改寫為新格式（`id`、`schedule.expr`、嵌套 `payload`/`delivery`），無需手動介入。

執行後重新確認：
```bash
openclaw cron list
```

### 方法二：手動檢查 cron 配置

```bash
openclaw cron list
```

若有 job 的 `session` 為 `isolated` 且依賴通知，需要確認 delivery 方式是否正確。

---

## 遷移後正確的 Delivery 配置

v2026.3.11 起，isolated cron job 的通知必須透過 `--announce` 旗標明確宣告，並指定 delivery 目標。

### ✅ 正確：明確宣告 announce + channel

```bash
openclaw cron add \
  --name "daily-check" \
  --every 24h \
  --session isolated \
  --message "執行每日檢查並回報結果" \
  --announce \
  --channel telegram
```

### ✅ 正確：不需要通知的靜默 job

```bash
openclaw cron add \
  --name "silent-cleanup" \
  --every 6h \
  --session isolated \
  --message "清理暫存檔案" \
  --no-deliver
```

### ❌ 舊版：依賴 fallback（v2026.3.11 起無效）

```bash
# 以下設定升級後不會送出通知，也不會報錯
# —— job 會執行，但結果靜默丟失
openclaw cron add \
  --name "old-style-job" \
  --every 6h \
  --session isolated \
  --message "檢查..."
  # 沒有 --announce，依賴舊版 fallback summary
```

---

## `--session` 的選擇邏輯

| 情境 | 建議 session | 說明 |
|------|-------------|------|
| 需要讀取 MEMORY.md / AGENTS.md | `main` | main session 有完整 workspace context |
| 需要隔離 context，不污染對話歷史 | `isolated` | 加 `--announce` 明確指定通知路徑 |
| 定期靜默清理（不需通知） | `isolated` | 加 `--no-deliver` |
| 一次性提醒（+duration） | `main` 或 `isolated` + `--delete-after-run` | |

---

## 快速驗證遷移結果

```bash
# 列出所有 cron job，確認 delivery 設定
openclaw cron list

# 立即執行一次測試
openclaw cron run <job-id>

# 查看最近執行記錄
openclaw cron runs
```

---

## 常見問題

**Q：升級後 cron job 還在跑，但 Telegram 沒收到通知？**

大概率是舊版 fallback 路徑被移除了。檢查 job 是否有 `--announce --channel telegram`，沒有就補上並重新建立。

**Q：`openclaw doctor --fix` 說沒有問題，但通知還是沒來？**

doctor 只遷移 storage 格式，不會自動補 `--announce`。需要手動確認每個 isolated job 的通知方式。

**Q：想讓 cron job 結果出現在 main session 的對話裡？**

改用 `--session main`，main session job 的輸出直接呈現在對話歷史中。

---

## 延伸閱讀

- [OpenClaw cron 文件](https://docs.openclaw.ai/cli/cron)（文件站上線後生效）
- [cron-automated-workflows.md](./cron-automated-workflows.md) — 定期任務設定參考
- 原始 PR：[#40998](https://github.com/openclaw/openclaw/pull/40998)
