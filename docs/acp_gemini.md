---
last_validated: 2026-04-03
---

# OpenClaw × ACP × Gemini 整合指南

讓你的 OpenClaw agent 透過 ACP 轉接 Google Gemini CLI，實現對話持久化。

---

## 重要更新 (2026.04)

### 1. Flag 變更
- **Gemini CLI 0.33.0+**：正式使用 `--acp`。
- **舊版 (0.31.x - 0.32.x)**：需使用 `--experimental-acp`。
- 本指南預設以 **0.33.x+** 為準。

### 2. Model Capacity 與 CWD
- **Capacity**：預設的 `gemini-3.1-pro-preview` 經常額度不足，建議設定 `GEMINI_MODEL=gemini-3-flash-preview`。
- **效能**：`cwd` 若設為 `~` 等大目錄會導致初始化極慢，建議固定在專案根目錄或 `/tmp`。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────────────────────────┐
│ Telegram │────▶│  openclaw gateway                           │
│          │     │                                             │
│ 用戶訊息 │     │  ① my-gemini-relay-hook hook                 │
│          │     │     │  (message_received)                   │
└──────────┘     │     │                                       │
     ▲           │     │  acpx --agent "gemini --acp" prompt   │
     │           │     │  -s my-gemini-tg -f - (stdin)         │
     │           │     ▼                                       │
     │           │  ┌──────────────────────┐                  │
     │           │  │  Gemini ACP session  │                  │
     │           │  │  my-gemini-tg           │                  │
     │           │  └──────────┬───────────┘                  │
     │           │             │ reply text                    │
     │           │             ▼                               │
     └───────────│  fetch api.telegram.org/sendMessage         │
                 │  (直接打 Bot API，繞過 openclaw 訊息系統)    │
                 │                                             │
                 │  ② my-gemini-relay agent (SOUL: "Output NO_REPLY.")  │
                 └─────────────────────────────────────────────┘
```

---

## 與 kiro / codex 整合的差異

| 項目 | kiro | codex | gemini |
|------|------|-------|--------|
| acpx 指令 | `acpx kiro prompt` | `acpx codex prompt` | `acpx --agent "gemini --acp" prompt` |
| 輸出格式 | 純文字 | JSON | 純文字 |

> **關鍵**：Gemini CLI 0.33.x 已將 `--experimental-acp` 改為 `--acp`。若你使用的版本低於 0.33.0，請改回舊 flag。

---

## 前置需求

- OpenClaw 已安裝並運行（`openclaw status`）
- `gemini` CLI 已安裝（`gemini --version`，建議 0.33.0+）
- acpx extension 已啟用（`openclaw doctor --fix`）
- 一個 Telegram bot token（從 @BotFather 取得）

```bash
# 建議更新至最新版以支援 --acp flag
npm install -g @google/gemini-cli@latest
```

---

## 步驟一：建立 relay agent

在 `~/.openclaw/openclaw.json` 加入 agent、binding、Telegram account：

```json
// agents.list
{ "id": "my-gemini-relay", "name": "Keroro", "workspace": "/home/<user>/.openclaw/workspace-my-gemini-relay" }

// bindings
{ "agentId": "my-gemini-relay", "match": { "channel": "telegram", "accountId": "my-gemini-relay" } }

// channels.telegram.accounts
"my-gemini-relay": {
  "name": "Keroro",
  "botToken": "<YOUR_BOT_TOKEN>",
  "dmPolicy": "pairing",
  "allowFrom": ["<YOUR_TELEGRAM_USER_ID>"],
  "groupPolicy": "allowlist"
}
```

---

## 步驟二：建立 workspace

```bash
mkdir -p ~/.openclaw/workspace-my-gemini-relay
```

### SOUL.md

```
Output NO_REPLY.
```

---

## 步驟三：建立 hook

```bash
mkdir -p ~/.openclaw/hooks/my-gemini-relay-hook
```

### HOOK.md

```markdown
---
name: my-gemini-relay-hook
description: "Relay my-gemini-relay Telegram DM messages to Gemini via acpx and push reply back"
metadata:
  { "openclaw": { "emoji": "🐸", "events": ["message:received"] } }
---
```

### handler.ts

```typescript
import { execSync } from "child_process";

const ACPX = "/home/<user>/.npm-global/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx";
const AGENT = "gemini --acp"; // Gemini CLI 0.33.x+
// 注意：環境變數需包含 GEMINI_MODEL=gemini-3-flash-preview 以避免 capacity 報錯
const SESSION = "my-gemini-tg";
const BOT_TOKEN = "<YOUR_BOT_TOKEN>";

async function sendTelegram(chatId: string, text: string) {
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

const handler = async (event) => {
  if (event.type !== "message" || event.action !== "received") return;
  if (!event.sessionKey?.startsWith("agent:my-gemini-relay:telegram:direct:")) return;

  const content = event.context?.content;
  if (!content) return;

  if (content.trim() === "/new") {
    execSync(`${ACPX} --agent "${AGENT}" sessions close ${SESSION} 2>/dev/null`,
      { encoding: "utf8", cwd: process.env.HOME });
    return;
  }

  const chatId = event.sessionKey.split(":").pop();
  if (!chatId) return;

  try {
    execSync(`${ACPX} --agent "${AGENT}" sessions ensure --name ${SESSION}`,
      { encoding: "utf8", cwd: process.env.HOME });
    const result = execSync(
      `${ACPX} --agent "${AGENT}" prompt -s ${SESSION} -f -`,
      { input: content, timeout: 120000, encoding: "utf8", cwd: process.env.HOME }
    );
    const reply = result.trim().split("\n")
      .filter(l => l && !l.startsWith("["))
      .join("\n");
    if (reply) await sendTelegram(chatId, reply);
  } catch (err) {
    // silent fail
  }
};

export default handler;
```

在 `openclaw.json` 啟用 hook：

```json
"hooks": {
  "internal": {
    "enabled": true,
    "entries": {
      "my-gemini-relay-hook": { "enabled": true }
    }
  }
}
```

---

## 步驟四：重啟 gateway

```bash
systemctl --user restart openclaw-gateway.service
sleep 3
openclaw hooks list  # 確認 my-gemini-relay-hook ✓ ready
```

---

## 常見問題

### Bot 無回應
```bash
journalctl --user -u openclaw-gateway.service --since "5 min ago" --no-pager | tail -20
```

### Gemini session 壞掉
```bash
# 根據版本選擇 --acp 或 --experimental-acp
AGENT_FLAG="--acp"
ACPX=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/.bin/acpx" | head -1)
cd $HOME && $ACPX --agent "gemini ${AGENT_FLAG}" sessions close my-gemini-tg 2>/dev/null
$ACPX --agent "gemini ${AGENT_FLAG}" sessions new --name my-gemini-tg
```

---

## 檔案清單

```
~/.openclaw/openclaw.json
~/.openclaw/workspace-my-gemini-relay/SOUL.md                   # Output NO_REPLY.
~/.openclaw/hooks/my-gemini-relay-hook/HOOK.md
~/.openclaw/hooks/my-gemini-relay-hook/handler.ts
```

---

## 相關文件

- [OpenClaw × ACP × Kiro 整合指南](./acp_kiro.md)
- [OpenClaw × ACP × Codex 整合指南](./acp_codex.md)
- [ACPX Harness 架構與演進史](../acpx-harness.md)
