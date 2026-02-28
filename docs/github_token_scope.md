# GitHub Token Scope Troubleshooting（跨倉庫互動）

當你能讀取公開倉庫，但在建立 Issue / Fork 時遇到：

- `Resource not accessible by personal access token (createIssue)`
- `Resource not accessible by personal access token (forks)`

通常是 **Token scope 或 repository access 範圍不足**。

## 快速判斷

- `gh api user` 成功：代表 token 格式正確。
- `gh issue create -R owner/repo ...` 失敗（403）：多半是該 repo 不在 token 授權範圍，或缺少 write 權限。

## 建議設定

### Fine-grained PAT

- Repository access：包含目標 repo（或 all repos）
- Repository permissions（至少）：
  - Issues: **Read and write**
  - Contents: **Read and write**（若要推送/建立分支）
  - Pull requests: **Read and write**（若要開 PR）

> 注意：Fine-grained PAT 沒有獨立的「create issue」勾選項，對應的是 `Issues: Read and write`。

### Classic PAT（替代方案）

若 fine-grained PAT 受限於跨 owner/repo 授權，常見替代是 classic PAT + `public_repo`（僅公開倉庫場景）。

## OpenClaw 內的建議做法

- 優先把 token 放在 Secret/Env 變數（避免硬編碼）
- 讓 `GH_TOKEN` / `GITHUB_TOKEN` 指向同一個 secret
- 設定後重啟 gateway 或等待配置重載完成

