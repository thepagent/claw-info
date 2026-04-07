---
last_validated: 2026-04-07
validated_by: Chloe
---

# Waterfall Sub-Agent Delegation — 串接式任務委派（Task 依賴前一個結果）

## TL;DR

- **核心問題**：多個任務有先後依賴（Task 2 需要 Task 1 的產出），不能平行跑
- **解法**：用 `openclaw agent` + `&&` 串接，每步完成才觸發下一步
- **檔案交接**：每個 task 的產出存到約定路徑，下一步讀取
- **背景執行**：整個瀑布流程包在 `()&` 裡，不阻塞主對話
- **完成通知**：最後一步用 `openclaw agent --deliver` 自動回報

---

## 什麼時候該用 Waterfall？

### ✅ 適合串接

| 場景 | 為什麼不能平行 |
|------|---------------|
| 分析程式碼 → 基於分析結果重構 | 重構需要知道分析發現了什麼 |
| 研究競品 → 基於研究撰寫報告 | 報告內容取決於研究結果 |
| 生成測試資料 → 跑測試 → 修復失敗 | 每步都依賴前步產出 |
| 翻譯文件 → 審校翻譯 → 排版發布 | 審校需要翻譯完成的文件 |

### ❌ 不適合串接

| 場景 | 該怎麼做 |
|------|---------|
| 兩個任務互不依賴 | 用 [Parallel Delegation](./parallel-subagent-delegation.md) |
| 只有一個任務 | 直接 spawn 單一 sub-agent |
| 任務間只需簡單判斷 | 主 agent 自己串接即可 |

**判斷標準**：下一步是否**必須讀取**上一步的產出才能開始？是 → Waterfall。

---

## 核心機制

### `openclaw agent` 的同步特性

```text
openclaw agent -m "任務指令" --channel <ch> --to <target> --deliver --timeout 300
```

這個指令是**同步**的——它會等 agent turn 完成才返回 exit code。這是串接的基礎：

```text
Task 1 完成（exit 0）
    │
    ├── && ──→ Task 2 開始
    │
    Task 2 完成（exit 0）
    │
    ├── && ──→ Task 3 開始
    │
    ...
```

`&&` 確保前一步成功才執行下一步。任何一步失敗，後續全部跳過。

### 檔案交接協議

任務之間靠**檔案**傳遞結果，不靠 context（每個 agent turn 是獨立 session）：

```text
Task 1 ──寫入──→ /tmp/task1-output.md
                        │
Task 2 ──讀取──→ /tmp/task1-output.md
         寫入──→ /tmp/task2-output.md
                        │
Task 3 ──讀取──→ /tmp/task2-output.md
```

**關鍵**：每步的 prompt 必須明確指定「產出存到哪」和「從哪讀取上一步結果」。

---

## 操作指引

### 基本模式：兩步串接

```bash
# ⚠️ 背景子進程沒有 PATH，必須用完整路徑
(
  /opt/homebrew/bin/openclaw agent \
    -m "分析 /path/to/project 的架構，將分析報告存到 /tmp/analysis.md" \
    --channel discord --to channel:<CHANNEL_ID> --deliver --timeout 300 && \
  /opt/homebrew/bin/openclaw agent \
    -m "讀取 /tmp/analysis.md 的分析結果，基於發現進行重構，完成後回報" \
    --channel discord --to channel:<CHANNEL_ID> --deliver --timeout 300
) &
```

### 進階模式：多步瀑布 + 跨頻道 + 最終回報

```bash
(
  # Step 1：研究（在研究頻道執行）
  /opt/homebrew/bin/openclaw agent \
    -m "研究 XX 主題，將研究筆記存到 /tmp/research-notes.md" \
    --channel discord --to channel:<RESEARCH_CHANNEL> --deliver --timeout 300 && \

  # Step 2：基於研究撰寫文件（在開發頻道執行）
  /opt/homebrew/bin/openclaw agent \
    -m "讀取 /tmp/research-notes.md，撰寫技術文件，存到 /tmp/draft.md" \
    --channel discord --to channel:<DEV_CHANNEL> --deliver --timeout 300 && \

  # Step 3：最終回報（通知使用者）
  /opt/homebrew/bin/openclaw agent \
    -m "✅ 全部完成！讀取 /tmp/draft.md 總結結果回報。" \
    --channel telegram --to <USER_ID> --deliver --timeout 120
) &
```

### 搭配 `message send`：讓頻道裡有完整上下文

單用 `openclaw agent` 時，頻道裡只看到結果，看不到任務描述。搭配 `message send` 可以補上：

```text
流程（每個 Task）：
1. message send → 頻道裡顯示任務描述（人類看得到完整上下文）
2. openclaw agent → 觸發 agent 開工（執行任務 + 回報結果）
```

這樣頻道裡的時間線是完整的：任務描述 → 執行結果 → 下一個任務描述 → 執行結果。

---

## 最佳實務

### ✅ Do

| 實務 | 原因 |
|------|------|
| 每步 prompt 明確指定輸出路徑 | 下一步才知道去哪讀 |
| 用 `/tmp/` 或 workspace 內的約定路徑 | 確保所有 agent turn 都能存取 |
| 每步設合理 timeout（300-600s） | 避免單步卡住拖垮整個瀑布 |
| 最後一步回報給使用者 | 整個流程完成才通知，不中途打擾 |
| 用 `--deliver` 參數 | 確保 agent turn 被觸發 |
| 整個瀑布包在 `() &` 背景執行 | 不阻塞主對話 |

### ❌ Don't

| Anti-pattern | 問題 |
|-------------|------|
| 不指定輸出路徑，期待 agent「記住」 | 每個 agent turn 是獨立 session，沒有共享 context |
| 用 `\|\|` 替代 `&&` | 前步失敗也會繼續，產出可能不存在 |
| 把大量資料塞進 prompt 而非檔案 | prompt 有長度限制，且不如檔案可靠 |
| 不設 timeout | 單步無限等待可能凍結整個瀑布 |
| 中間步驟都通知使用者 | 使用者被中間過程轟炸，最終結果反而被淹沒 |

---

## 與 Parallel Delegation 的比較

| 維度 | Waterfall | Parallel |
|------|-----------|----------|
| 任務關係 | 有依賴（順序執行） | 無依賴（同時執行） |
| 速度 | 較慢（序列） | 較快（並行） |
| 失敗處理 | `&&` 自動中斷後續 | 需要主 agent 整合時處理 |
| 資料傳遞 | 檔案交接 | 各自獨立，主 agent 整合 |
| 適用場景 | 研究→撰寫→發布 | 同時查多個來源 |
| 實作工具 | `openclaw agent` + `&&` | `sessions_spawn` 多個 |

**可以混合使用**：瀑布中的某一步可以包含平行子任務。

---

## Troubleshooting

| 症狀 | 可能原因 | 處理方式 |
|------|---------|---------|
| 第二步說找不到檔案 | 第一步沒有正確寫入約定路徑 | 在 prompt 裡用完整絕對路徑 |
| 整個瀑布沒有開始 | 背景子進程找不到 `openclaw` | 使用完整路徑（如 `/opt/homebrew/bin/openclaw`） |
| 某步 timeout 後全部停止 | `&&` 會因非零 exit code 中斷 | 加長 timeout，或在關鍵步驟加重試邏輯 |
| 使用者在頻道看不到任務描述 | 只用 `openclaw agent`，沒搭配 `message send` | 每步前先發任務描述 |
| 步驟間的 agent 讀到過期檔案 | 路徑衝突（多個瀑布同時跑用相同路徑） | 用唯一前綴（如 timestamp）避免衝突 |
| Agent turn 沒被觸發 | 缺少 `--deliver` 參數 | 確保每步都帶 `--deliver` |

---

## 安全注意事項

- **檔案交接路徑**：避免用可預測路徑存放敏感資料（如 API 回應、credentials），用完即刪
- **Timeout 設定**：每步 timeout 應基於實際預估，過長的 timeout 會佔用資源
- **錯誤升級**：考慮在最後加一個 `||` 分支處理整體失敗的通知

```bash
(
  step1 && step2 && step3
) || /opt/homebrew/bin/openclaw agent \
  -m "⚠️ 瀑布任務失敗，請檢查" \
  --channel telegram --to <USER_ID> --deliver --timeout 60 &
```

---

## 相容性

- **OpenClaw 版本**：v2026.3.11+（需要 `openclaw agent --deliver` 支援）
- **Shell**：bash / zsh（需支援 `&&` 和 `() &` 語法）
- **平台**：macOS / Linux 均可

---

## See also

- [Sub-Agent Orchestration 實戰指南](./subagent-orchestration.md) — 完整的 sub-agent 生態
- [Parallel Sub-Agent Delegation](./parallel-subagent-delegation.md) — 無依賴任務的平行委派
- [Cron Automated Workflows](./cron-automated-workflows.md) — 定時觸發的自動化
