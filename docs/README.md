# OpenClaw 文件索引（docs/）

本目錄收錄 `claw-info` 專案中與 OpenClaw 使用、部署與核心概念相關的文件。

- 寫作規約：[`STYLE_GUIDE.md`](./STYLE_GUIDE.md)

## 快速導覽

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

## 即將補齊：核心概念 Deep Dive

以下主題會以「核心概念」角度補上更完整的脈絡、設計取捨與最佳實務（見 issue/PR 追蹤）：

- Tooling 契約與安全邊界：#31（PR #37）
- Session 模型與隔離（main vs isolated）：#30（PR #36）
- Gateway 架構與生命週期：#29（PR #35）
- 訊息路由與 channel plugins：#32（PR #38）
- Skills 系統（封裝/版本/測試）：#33（PR #39）
- Memory 系統（files-as-memory）策略：#34（PR #40）

> 註：若要認領撰寫或提出補充，直接在對應 issue/PR 留言即可。

## 貢獻方式（簡要）

- 以 **單一主題一篇文件** 為原則，避免超長雜燴文。
- 優先補齊：**概念（Why/What）→ 操作（How）→ 例外/排查（Troubleshooting）**。
- 範例指令請保持可複製，並註明前置條件（例如需要的 token、權限、或 profile）。
