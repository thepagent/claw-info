# Agent 專用 GitHub 帳號與備份策略（預設私有）

## TL;DR

- **預設私有**：能私有就私有；公開 repo 只放「確定可公開」的內容。
- **MUST NOT（公開 repo 禁止）**：`MEMORY.md`、`memory/`、任何 token/憑證、聊天紀錄、可能含個資的 session/state/cache。
- **推送前必檢查**：push 前先提供「將推送的檔案清單 + diff 摘要」，再由人 approve。
- **分離倉庫**：把「可公開的工具/技能」與「使用者私密記憶」拆開存。
- **最小權限**：能只給 read 就不要給 write；需要 write 時也要配合 approval-first。

## 使用情境

你可能會讓 agent：
- 用自己的 GitHub 帳號開 PR、回 issue
- 維護自己的 workspace repo（備份設定/文件）

問題是：agent 的工作區常包含大量私密資料；一旦推到公開 repo 就是安全事故。

## 核心概念：哪些能備份、哪些不能

### MUST NOT：禁止推到公開 repo（視為安全事故）

以下內容通常包含高度個人化資料或憑證，**不得推到公開 repo**：

- `MEMORY.md`
- `memory/`（每日記憶）
- 任何 token / refresh token / API keys / cookies
- 聊天紀錄、轉錄檔（transcripts）
- 可能含 session 狀態的檔案，例如：
  - `memory-state.json`（若存在）
  - `.openclaw/**`（cache、session、profiles 等）
  - 其他工具產生的 state/cache 目錄

> 原則：只要可能包含「誰說了什麼/你的偏好/你的憑證」，就當成敏感。

### 通常可備份（仍建議私有 repo）

- 不含秘密的範本（prompt templates）
- 可重用的技能/腳本（不含 token）
- 文件與 checklists
- 專案程式碼（若原本就打算公開）

## How-to：一個安全、可操作的備份流程

### 1) 建議的 repo 拆分

- **Private repo（私有）**：workspace/設定/任何可能含個資的內容
- **Public repo（公開，可選）**：可公開的技能、範本、文件（嚴格排除敏感檔）

### 2) 用 `.gitignore` 排除敏感路徑

（示意）

```gitignore
# memory
MEMORY.md
memory/

# agent runtime/cache/state (names may vary)
.openclaw/
**/*token*
**/*secret*
```

> 注意：`.gitignore` 只能避免「新檔」被加入；已被 commit 的敏感檔還是會留在歷史。

### 3) Push 前的「檔案清單 + 摘要」批准

在 push 前固定跑：

```bash
# 檔案清單（有哪些檔案會被推）
git status

# 變更摘要
git diff --stat

# 需要時看完整 diff
git diff
```

把上述輸出（遮罩敏感資訊）貼給人看，**人類 approve 後**才做：

```bash
git push
```

## Examples

### 範例：只備份「可公開」的模板

- 把模板放到 `templates/`
- 確保不包含任何個資、token
- 推到 public repo

### 範例：把私密記憶放到私有儲存

- `MEMORY.md` / `memory/` 永遠只存在私有 repo 或私有磁碟/加密備份
- 不要跟可公開的內容混在同一個 git repo

## Anti-patterns

- 用公開 repo 備份整個工作區
- 只靠 `.gitignore` 就覺得安全（忽略已 commit 歷史）
- 沒有 push 前檢查就讓 agent 自動 push

## Troubleshooting

- **症狀**：不小心把敏感檔案 push 出去了
  - **可能原因**：敏感檔案未被 ignore / 已存在於 git 歷史
  - **處理**：立刻視為事故處理（撤銷 token、清理 repo 歷史、通知相關人）

- **症狀**：agent 自動開 PR/留言造成外部影響
  - **可能原因**：沒有 approval-first gate
  - **處理**：把「對外發送」列為必須 approve 的硬規則（見 approval-first workflow）

- **症狀**：不知道哪些檔案算敏感
  - **可能原因**：沒有敏感分類準則
  - **處理**：採用「可能含個資/憑證/對話」即敏感的保守原則，寧可不備份也不要外洩

## Security notes

- 公開 repo 的風險是「不可逆」：即使刪檔，歷史與 fork 可能仍存在。
- 建議把「禁止推送敏感檔」做成自動檢查（pre-commit / CI）+ 人工批准雙層。

## See also

- `../core/approval-first-workflow.md`（#297）
- `../core/workspace-role-separation.md`（#299）
- `../STYLE_GUIDE.md`
