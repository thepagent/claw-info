# Approval-First Workflow：個人 Agent 的審批優先設計

> 讓 agent 自主讀、分析、起草，但在任何改變狀態的操作前先取得人類許可。

---

## TL;DR

- **核心原則**：read freely, change only with approval
- **問題根源**：agent 太自主 → 做了難回頭的事；太被動 → 每步都問，用起來痛苦
- **解法**：在 `AGENTS.md` 明確劃定邊界，state-changing 操作插審批閘門
- **執行工具**：`openfeedback`——自動化腳本暫停、發 Telegram 請示、exit code 決定繼續或中止
- **關鍵設計**：審批訊息要帶足夠的上下文，不是「繼續？」而是「做什麼、影響什麼、有沒有退路」

---

## 兩個失敗極端

```
太自主                                          太被動
   │                                              │
   ▼                                              ▼
agent 自行 push commit                      agent 每次讀檔案
agent 自行發 Telegram 訊息                  都要問「可以嗎？」
agent 自行刪改 memory 檔案
   │                                              │
   ▼                                              ▼
出錯難撤銷                                  體驗極差，棄用
```

approval-first 是中間路徑：agent 在安全範圍內自主運作，在邊界處停下來問。

---

## 邊界劃定：哪些可以自主，哪些需要審批

### ✅ 無需審批（read-only / 低風險）

- 讀取本地檔案、workspace 內容
- 分析、摘要、翻譯、起草文字
- 搜尋網路、查詢文件
- 讀取 GitHub issues / PR（不寫入）
- 查看 calendar、通知（不回覆）

### 🔐 需要審批（state-changing）

| 類別 | 操作範例 |
|------|---------|
| 檔案系統 | 新增 / 修改 / 刪除檔案，寫入 memory |
| Shell 指令 | 任何有副作用的指令（deploy、rm、push）|
| Git / GitHub | commit、push、開 PR、留 issue 留言 |
| 外部訊息 | 發 Telegram / Email / 任何對外發送 |
| 排程 | 新增 / 修改 cron 任務 |
| 設定 / 憑證 | 改 config、secrets、API keys |

---

## 在 AGENTS.md 中表達這個 Policy

在 `AGENTS.md` 的 Safety 區塊加入明確邊界：

```markdown
## Safety

**可自主執行：**
- 讀取檔案、搜尋、分析、起草

**必須先取得許可：**
- 任何寫入操作（檔案、memory、git）
- 任何對外發送（訊息、API 呼叫）
- 任何排程變更

遇到邊界操作：暫停、說明意圖、等待確認後再執行。
```

---

## 執行層：接入 openfeedback

[openfeedback](https://github.com/antx-code/openfeedback) 是一個 CLI 工具，讓自動化腳本在執行前發 Telegram 審批請求，根據 exit code 決定繼續（0）或中止（1）。

### 工作流程

```
agent / 自動化腳本
        │
        │ 抵達 state-changing 操作
        ▼
┌───────────────────────────────┐
│  openfeedback "操作說明"       │
│  → 發 Telegram 審批訊息        │
│  → 等待回應（預設 60 秒）      │
└──────────┬────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
  核准           拒絕 / 超時
  exit 0         exit 1
    │             │
    ▼             ▼
繼續執行        中止操作
```

### 在 cron payload 中使用

isolated session 不繼承 `AGENTS.md`，必須在 payload 裡顯式說明邊界，再搭配 openfeedback 作為執行閘門：

```
# cron payload 範例（財務分析 agent）
你是一個財務分析 agent。

可自主執行：
- 讀取 workspace 內的 market-data/ 檔案
- 分析數據、生成摘要

需要審批（使用 openfeedback）：
- 寫入任何檔案
- 發送任何外部訊息

完成分析後，執行以下指令請示是否寫入 memory：
openfeedback "Agent 準備更新 memory/today.md
內容：今日市場分析摘要（約 500 字）
影響：覆蓋既有當日記錄
是否核准？" && echo "${SUMMARY}" >> memory/today.md
```

### 在 coding agent 流程中使用

```bash
# agent 完成實作後，準備開 PR

openfeedback "Coding agent 準備開 PR
標題：${PR_TITLE}
分支：${BRANCH}
變更：${CHANGED_FILES} 個檔案
Repo：${REPO}
是否核准？" && \
  gh pr create --title "${PR_TITLE}" --body "${PR_BODY}"
```

### 審批訊息的關鍵原則

```
# ❌ 沒用——不知道在問什麼
openfeedback "繼續？"

# ✅ 有用——做什麼、影響什麼、有無退路
openfeedback "準備 git push origin main
包含 3 個 commit，最後一個是 feat: 新增付款流程
此操作 push 後需另開 PR 才能撤銷
是否核准？"
```

### 設定要點

```toml
# ~/.config/openfeedback/config.toml
bot_token = "<YOUR_BOT_TOKEN>"
chat_id = <YOUR_CHAT_ID>
trusted_user_ids = [<YOUR_CHAT_ID>]   # 只允許你自己審批
default_timeout = 60                   # 超時視為拒絕（安全預設）
```

> **Timeout 配置說明**
>
> `default_timeout` 是本地自訂版本的配置項。若使用 upstream 版本（`cargo install --git ...`），目前主審批流程的 timeout 無法透過 config 直接設定，建議在腳本層控制：
>
> ```bash
> # 對不可逆操作，透過 --timeout 延長等待時間（若 CLI 支援）
> # 或將任務排在有人值守時段，避免因超時導致中止
> openfeedback --timeout 300 "準備 git push origin main ..."
> ```
>
> v0.2.0 新增的 `reject_feedback_timeout` 是「拒絕後等待理由」的時間窗，與主審批 timeout 是不同的配置。

詳細安裝請見 [openfeedback README](https://github.com/antx-code/openfeedback)。

---

## 取捨設計

| 場景 | 建議策略 |
|------|---------|
| 完全自動化的低風險任務（純讀取、分析） | 無需審批，讓 agent 自主跑 |
| 有寫入但影響可逆（如更新 memory） | 審批一次，批准後自動執行 |
| 高風險不可逆（push、deploy、發訊息） | 每次都審批，不設豁免 |
| 批次操作（10 個檔案逐一確認） | 審批整個計劃，不逐項問 |
| 無人值守 cron（深夜跑） | 純讀取任務不插審批；寫入任務改在有人值守時段執行 |

---

## Anti-patterns

**在無人值守 cron 裡插審批**

深夜的 cron 任務要寫入 memory，發了 Telegram 沒人看——60 秒後超時、任務中止、隔天才發現。解法：分離任務，純分析放無人值守，需審批的操作排在清醒時段。

**審批粒度太細**

agent 每寫一行都問一次，體驗比沒有 agent 更差。審批應該在「計劃」層級，不是「操作」層級。

**AGENTS.md 寫了邊界但 cron payload 沒寫**

isolated session 不讀 AGENTS.md。邊界 policy 必須在 payload 裡重複說明。

---

## Troubleshooting

**症狀**：openfeedback 發出訊息但沒有收到
- 確認 bot 已對話過（先對 bot 發 `/start`）
- 確認 `chat_id` 正確

**症狀**：cron 任務因審批超時而中止
- 檢查任務是否在無人值守時段執行
- 調整 `--timeout` 或改在有人值守時段排程

**症狀**：agent 跳過審批直接執行
- isolated session 的 payload 沒有說明邊界——補上 approval-first 指示

---

## 相關連結

- `docs/cron.md`：OpenClaw Cron 系統
- `usecases/cron-automated-workflows.md`：自動化工作流設計
- Issue #297：本文件的提案來源
