# claw-info

`claw-info` 是 OpenClaw 相關資訊的記錄與實作知識庫。

## 📁 目錄結構

```
claw-info/
├── .github/workflows/
│   └── check-commit-author.yml    # 檢查 commit author 的 workflow
├── docs/
│   ├── core/
│   │   └── gateway-lifecycle.md   # Gateway 架構與生命週期（重啟/更新/排障）
│   ├── bedrock_auth.md            # AWS Bedrock 認證與配置指南
│   ├── bedrock_pricing.md         # Bedrock 模型定價與成本控制
│   ├── cron.md                    # OpenClaw Cron 調度系統深度解析
│   ├── linux_systemd.md           # Linux（systemd）上 gateway 重啟、port 衝突與 model 設定踩坑
│   ├── nodes.md                   # OpenClaw Nodes 管理與配置
│   ├── pricing_howto.md           # 定價策略與實作
│   ├── profile_rotation.md        # 同一 Provider 的 Auth Profiles 輪換（Rotation / Failover）
│   ├── sandbox.md                 # Sandbox 環境配置
│   └── webhook.md                 # Webhook（Cron delivery webhook）
├── release-notes/
│   ├── 2026-02-14.md              # 2026-02-14 發佈記錄
│   ├── 2026-02-15.md              # 2026-02-15 發佈記錄
│   ├── 2026-02-16.md              # 2026-02-16 發佈記錄
│   └── GUIDELINES.md              # Release Notes 製作規範
└── README.md
```

## 📚 主要內容

### docs/
技術文件與實作指南，包含：

- **core/gateway-lifecycle.md** - Gateway 架構與生命週期（重啟/更新/排障）
- **bedrock_auth.md** - AWS Bedrock 認證與配置指南
- **bedrock_pricing.md** - Bedrock 模型定價與成本控制
- **cron.md** - OpenClaw Cron 調度系統深度解析
- **nodes.md** - OpenClaw Nodes 管理與配置
- **pricing_howto.md** - 定價策略與實作
- **sandbox.md** - Sandbox 環境配置
- **webhook.md** - Webhook（Cron delivery webhook）

### release-notes/
發佈記錄與規範：

- **GUIDELINES.md** - Release Notes 製作規範
- **YYYY-MM-DD.md** - 每日發佈記錄（按日期組織）

### .github/workflows/
CI/CD Workflow 定義：

- **check-commit-author.yml** - 檢查 commit author 是否符合 `thepagent` 設定

## 🛠️ 使用情境

- **開發者**：查閱技術規格與實作細節
- **維護者**：Reference Release Notes 了解變更歷史
- **研究者**：學習 OpenClaw 架構與設計決策

## 📂 相關連結

- [OpenClaw 官方倉庫](https://github.com/openclaw/openclaw)
- [OpenClaw 文件](https://docs.openclaw.ai)

## 📝 如何貢獻

### 問題回報 (Issues)

若有任何問題、建議或發現錯誤，歡迎建立 Issue：

1. 檢查是否已有類似問題
2. 提供詳細描述、再現步驟與預期結果
3. 若適用，附上相關日誌或截圖

### 程式碼貢獻 (Pull Requests)

1. Fork 倉庫並建立您的分支 (`git checkout -b feature/your-feature`)
2. 提交變更 (`git commit -m "feat: add some feature"`)
3. 推送到您的分支 (`git push origin feature/your-feature`)
4. 開啟 Pull Request

**注意**：
- Commit message 格式：`type: description`（如 `feat:`, `fix:`, `docs:`, `refactor:`）
- 在 PR description 中加入 `Fixes: #issue_number`（若為 issue 修復）

---

*Maintained by thepagent*
