# Approval-first 工作流（個人 OpenClaw Agent）

## TL;DR

- **原則**：讀取（read）通常可先做；**任何會改變狀態**的行為必須先取得使用者 approve。
- **read-only 的邊界**：預設只把「工作區（workspace）」內的讀取視為低風險；超出工作區的讀取要當成敏感。
- **批准要可檢視**：在執行前先列出將做什麼（plan），並明確列出會改動的檔案/資源。
- **原子性（Atomic）**：批准後若條件變了（目標、分支、檔案清單、外部狀態），應暫停並重新請求批准。
- **可中止/可回退**：至少提供停手與復原的最小指引（不要「做完才說」）。

## 這份文件要解決的問題

個人 agent 常見失誤：
- 在未經同意下跑指令、改檔、對外發言
- 以為「讀檔」永遠安全，結果讀到私密資料或系統設定

Approval-first 的目標：**降低風險，同時維持可用性**。

## 核心概念

### 什麼算「read-only」？

通常可先做（但仍要注意隱私）：
- 讀取工作區內檔案、列目錄、分析程式碼
- 撰寫草稿（但不送出）

仍可能需要先問（敏感讀取）：
- 讀取工作區以外路徑（例如 `/etc/*`、家目錄私密檔）
- 讀取含憑證/token 的設定
- 讀取聊天紀錄/個資

> 建議：把「允許 read-only 的範圍」明確寫在 AGENTS.md。

### 什麼算「state-changing」？

必須先 approve：
- 新增/修改/刪除檔案
- 執行會改系統狀態的指令（安裝套件、改設定、重啟服務）
- 任何對外發送（email、社群、GitHub comment/PR、排程 cron）
- 任何會花錢/下單/付款

### 原子性（Atomic execution）

批准通常是對「一組特定行為」的授權：
- 目標 repo、分支
- 將改哪些檔案
- 將發送哪些對外訊息

若執行途中上述任何一項改變，應：
1) 暫停
2) 回報變更點
3) 重新請求批准

## How-to：建議流程（可直接照做）

### 1) 先提出計畫（Plan）

格式建議：
- 目的（1 句）
- 將做的步驟（3～7 點）
- 會改動/對外影響（檔案、訊息、服務）

### 2) 等待 approve

使用者若要改方案，先改 plan，再次取得同意。

### 3) 執行（Execute）

- 嚴格照 plan 做
- 每個風險點前再提醒一次（例如「即將 push」）

### 4) 回報（Report）

回報至少包含：
- 做了什麼
- 改了哪些檔案/資源
- 如有對外發送：附上連結或內容摘要

## Examples

### 範例 1：只讀檢查（不需要 approve）

```bash
# 檢查 repo 狀態（不改檔）
git status

# 讀檔分析（不寫入）
sed -n '1,120p' AGENTS.md
```

### 範例 2：改檔 + 開 PR（需要 approve）

> 在執行前先給使用者看到將改哪些檔案與摘要。

```bash
# 1) 建分支
git checkout -b fix/issue-123

# 2) 改檔（示意）
$EDITOR docs/core/example.md

# 3) 顯示變更摘要，等待 approve
git diff --stat

git diff

# 4) commit/push/開 PR（使用者 approve 後才做）
```

## Anti-patterns

- 「我先做了再說」
- 在未列出檔案清單/摘要的情況下直接 push
- 把工作區以外的讀取當成無風險

## Troubleshooting

- **症狀**：使用者說「我沒同意你怎麼就做了」
  - **可能原因**：你把 state-changing 行為誤判成 read-only
  - **處理**：把需要 approve 的行為清單寫進 AGENTS.md，並在工具層做硬性 gate

- **症狀**：批准後執行到一半才發現目標不同
  - **可能原因**：plan 不夠具體（沒鎖 repo/分支/檔案清單）
  - **處理**：在 plan 明確列出「repo/branch/files」，條件變了就停下來再問

- **症狀**：需要緊急停手
  - **可能原因**：執行風險超出預期
  - **處理**：立刻停止後續操作；若已修改，優先回到可回復狀態（例如 revert commit、停止排程、撤回訊息）並回報

## Security notes

- Approval-first 不是「永遠安全」：它是降低失誤風險的 default。
- 若你讓 agent 具備對外權限（GitHub、Email、付款），務必把 approve gate 做成硬規則。

## See also

- `./workspace-role-separation.md`（#299）
- `../howto/agent-owned-github-repo.md`（#298）
- `../STYLE_GUIDE.md`
