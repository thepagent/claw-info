---
last_validated: 2026-04-05
validated_by: thepagent
---

# CLI Quick Reference（指令速查）

> 目標：把最常用的 OpenClaw 指令整理成「抄得到就能用」的速查表。

---

## 0) 基本

```bash
openclaw --version
openclaw help
```

---

## 1) Gateway（daemon）

```bash
openclaw gateway status
openclaw gateway restart
openclaw gateway start
openclaw gateway stop
```

---

## 2) Onboarding

```bash
openclaw onboard
openclaw onboard --install-daemon
```

---

## 3) Sessions / Agents

```bash
openclaw sessions list
openclaw sessions history <sessionKey>
openclaw agent --message "hi"
openclaw agents list
```

---

## 4) ACP / MCP

```bash
openclaw acp                    # 啟動 ACP bridge（IDE 連 OpenClaw）
openclaw mcp serve              # 啟動 MCP server（外部 MCP client 連 OpenClaw）
```

> `openclaw acp` 是 Gateway-backed ACP bridge，不是 ACP harness。
> 若要讓 OpenClaw 啟動外部 CLI（Codex/Claude/Gemini），用 ACP Agents（`/acp spawn`）。

---

## 5) Cron / Flows / Tasks

```bash
openclaw cron list
openclaw cron add
openclaw cron run <jobId>
openclaw cron runs
openclaw flows list             # ClawFlow 工作流
openclaw tasks list             # 任務管理
```

---

## 6) Nodes / Devices

```bash
openclaw nodes status
openclaw nodes describe --node <id>
openclaw devices list
openclaw devices approve <requestId>
```

（配對流程與能力請看 `docs/nodes.md`）

---

## 7) 管理工具

```bash
openclaw doctor                 # 診斷 + 修復
openclaw dashboard              # Web dashboard
openclaw backup                 # 備份設定
openclaw models list            # 模型清單
openclaw memory search <query>  # 記憶搜尋
openclaw plugins list           # 插件管理
openclaw secrets list           # Secrets 管理
openclaw skills list            # Skills 管理
openclaw pairing list           # 配對管理
openclaw channels list          # Channel 管理
openclaw approvals list         # 審批管理
openclaw sandbox status         # Sandbox 狀態
openclaw browser                # 瀏覽器工具
openclaw hooks list             # Hook 管理
openclaw webhooks list          # Webhook 管理
openclaw logs                   # 查看日誌
openclaw system info            # 系統資訊
```

---

## 8) 常用除錯

```bash
openclaw status
openclaw health
openclaw gateway status
openclaw doctor --fix
```

---

## 9) 常見工作流（例）

### 9.1 「我想確認 bot 還活著」

```bash
openclaw gateway status
```

### 9.2 「我想重啟所有東西」

```bash
openclaw gateway restart
```

---

更多排錯見：`docs/troubleshooting.md`
