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

## 3) Sessions / Subagents

（以下命令視你的版本可能略有差異；以實際 help 為準）

- 列出 sessions
- 查某個 session 歷史
- 對某個 session 發訊息

> 在 chat 介面中，多數情境你會直接用 agent 的內建工具 `sessions_list / sessions_history / sessions_send`。

---

## 4) Cron（排程）

> 你也可以直接在 chat 用 `cron` tool 建立/管理。

概念：
- list：看有哪些 job
- add：新增 job
- run：立即觸發
- runs：看執行紀錄

---

## 5) Nodes

```bash
openclaw nodes status
```

（配對流程與能力請看 `docs/nodes.md`）

---

## 6) 常用除錯

```bash
openclaw status
openclaw gateway status
```

---

## 7) 常見工作流（例）

### 7.1 「我想確認 bot 還活著」

```bash
openclaw gateway status
```

### 7.2 「我想重啟所有東西」

```bash
openclaw gateway restart
```

---

更多排錯見：`docs/troubleshooting.md`
