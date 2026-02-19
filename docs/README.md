# OpenClaw 文件索引（docs/）

本目錄收錄 `claw-info` 專案中與 OpenClaw 使用、部署與核心概念相關的文件。

- 寫作規約：[`STYLE_GUIDE.md`](./STYLE_GUIDE.md)

## Start here

- [`install.md`](./install.md) — 安裝（macOS/Linux，常見安裝坑）
- [`start.md`](./start.md) — 最小可行 Start / Onboarding（daemon、channel、pairing、驗證清單）
- [`cli.md`](./cli.md) — CLI 指令速查
- [`troubleshooting.md`](./troubleshooting.md) — 常見故障排除（不回覆/收不到訊息/browser/cron/SSO…）

## 快速導覽

- **架構**
  - [`ios_arch.md`](./ios_arch.md) — iOS 架構：Gateway 模式、Apple Watch 整合、Bridge 命令

- **Linux / systemd（運維）**
  - [`linux_systemd.md`](./linux_systemd.md) — Linux（systemd）上 gateway 重啟、port 衝突與 model 設定踩坑

- **Bedrock**
  - [`bedrock_auth.md`](./bedrock_auth.md) — Bedrock 認證與權限設定（含常見錯誤排查）
  - [`bedrock_pricing.md`](./bedrock_pricing.md) — Bedrock 計價概念與成本拆解
  - [`pricing_howto.md`](./pricing_howto.md) — 計價/成本估算操作指引

- **排程與自動化**
  - [`cron.md`](./cron.md) — OpenClaw Cron 調度系統：一次性/週期性/cron 表達式、delivery、sessionTarget

- **裝置與節點（Nodes）**
  - [`nodes.md`](./nodes.md) — Nodes 配對、通知、相機/螢幕、location、遠端執行

- **安全與隔離**
  - [`sandbox.md`](./sandbox.md) — sandbox/host/node 的執行邊界、限制與最佳實務

- **整合**
  - [`webhook.md`](./webhook.md) — Webhook delivery 與事件回傳（適合與外部系統串接）

- **運維**
  - [`profile_rotation.md`](./profile_rotation.md) — Profile rotation（憑證/身份輪替）與操作建議

## Core 概念 Deep Dive

- `docs/core/`
  - `gateway-lifecycle.md`
  - `session-isolation.md`
  - `tooling-safety.md`
  - `messaging-routing.md`
  - `skills-system.md`
  - `memory-strategy.md`

## 貢獻方式（簡要）

- 以 **單一主題一篇文件** 為原則，避免超長雜燴文。
- 優先補齊：**概念（Why/What）→ 操作（How）→ 例外/排查（Troubleshooting）**。
- 範例指令請保持可複製，並註明前置條件（例如需要的 token、權限、或 profile）。
