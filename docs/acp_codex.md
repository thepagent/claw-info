# OpenClaw × ACP × Codex 整合指南

讓你的 OpenClaw agent 透過 ACP 轉接 OpenAI Codex，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────────────────────────┐
│ Telegram │────▶│  openclaw gateway                           │
│          │     │                                             │
│ 用戶訊息 │     │  ① my-codex-relay-hook hook                 │
│          │     │     │  (message_received)                   │
└──────────┘     │     │                                       │
     ▲           │     │  acpx --format json codex prompt      │
     │           │     │  -s my-codex-tg -f -  (stdin)          │
     │           │     │  + python3 解析 JSON chunks            │
     │           │     ▼                                       │
     │           │  ┌──────────────────────┐                  │
     │           │  │  Codex ACP session   │                  │
     │           │  │  my-codex-tg          │                  │
     │           │  └──────────┬───────────┘                  │
     │           │             │ reply text                    │
     │           │             ▼                               │
     └───────────│  fetch api.telegram.org/sendMessage         │
                 │  (直接打 Bot API，繞過 openclaw 訊息系統)    │
                 │                                             │
                 │  ② my-codex-relay agent (SOUL: "Output NO_REPLY.") │
                 └─────────────────────────────────────────────┘
```

---

## 與 kiro / gemini 整合的差異

| 項目 | kiro | codex | gemini |
|------|------|-------|--------|
| acpx 指令 | `acpx kiro prompt` | `acpx codex prompt` | `acpx --agent "gemini --experimental-acp" prompt` |
| 輸出格式 | 純文字 | JSON（需 `--format json` + python3 解析） | 純文字（含 `[client]` 前綴行） |
| acpx patch 需要？ | ✅ 是 | ❌ 否 | ❌ 否 |

---

## 前置需求

- OpenClaw 已安裝並運行（`openclaw status`）
- `codex` CLI 已安裝並授權（`codex --version`）
- acpx extension 已啟用（`openclaw doctor --fix`）
- 一個 Telegram bot token（從 @BotFather 取得）

---

## 步驟一：建立 relay agent

在 `~/.openclaw/openclaw.json` 加入 agent、binding、Telegram account：

```json
// agents.list
{ "id": "my-codex-relay", "name": "Guan Yu", "workspace": "/home/<user>/.openclaw/workspace-my-codex-relay" }

// bindings
{ "agentId": "my-codex-relay", "match": { "channel": "telegram", "accountId": "my-codex-relay" } }

// channels.telegram.accounts
"my-codex-relay": {
  "name": "Guan Yu",
  "botToken": "<YOUR_BOT_TOKEN>",
  "dmPolicy": "pairing",
  "allowFrom": ["<YOUR_TELEGRAM_USER_ID>"],
  "groupPolicy": "allowlist"
}
```

---

## 步驟二：建立 workspace

```bash
mkdir -p ~/.openclaw/workspace-my-codex-relay
```

### SOUL.md

```
Output NO_REPLY.
```

---

## 步驟三：建立 hook

```bash
mkdir -p ~/.openclaw/hooks/my-codex-relay-hook
```

### HOOK.md

```markdown
---
name: my-codex-relay-hook
description: "Relay my-codex-relay Telegram DM messages to Codex via acpx and push reply back"
metadata:
  { "openclaw": { "emoji": "⚔️", "events": ["message:received"] } }
---
```

### handler.ts

```typescript
import { execSync, execFileSync } from "child_process";
import { writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const ACPX = "/home/<user>/.npm-global/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx";
const SESSION = "my-codex-tg";
const BOT_TOKEN = "<YOUR_BOT_TOKEN>";

// Write parse script to temp file to avoid shell quoting issues
const PARSE_SCRIPT = join(tmpdir(), "my-codex-parse.py");
writeFileSync(PARSE_SCRIPT, `
import sys, json
chunks = []
in_response = False
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        if d.get('method') == 'session/prompt':
            chunks = []
            in_response = True
            continue
        if in_response:
            u = d.get('params', {}).get('update', {})
            if u.get('sessionUpdate') == 'agent_message_chunk':
                chunks.append(u['content']['text'])
    except: pass
print(''.join(chunks))
`);

async function sendTelegram(chatId: string, text: string) {
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

const handler = async (event) => {
  if (event.type !== "message" || event.action !== "received") return;
  if (!event.sessionKey?.startsWith("agent:my-codex-relay:telegram:direct:")) return;

  const content = event.context?.content;
  if (!content) return;

  if (content.trim() === "/new") {
    execSync(`${ACPX} codex sessions close ${SESSION} 2>/dev/null`,
      { encoding: "utf8", cwd: process.env.HOME });
    return;
  }

  const chatId = event.sessionKey.split(":").pop();
  if (!chatId) return;

  try {
    execSync(`${ACPX} codex sessions ensure --name ${SESSION}`,
      { encoding: "utf8", cwd: process.env.HOME });
    const json_output = execSync(
      `${ACPX} --format json codex prompt -s ${SESSION} -f -`,
      { input: content, timeout: 120000, encoding: "utf8", cwd: process.env.HOME }
    );
    const reply = execFileSync("python3", [PARSE_SCRIPT], {
      input: json_output, encoding: "utf8"
    }).trim();
    if (reply) await sendTelegram(chatId, reply);
  } catch (err) {
    // silent fail
  }
};

export default handler;
```

> **為何 codex 需要 `--format json` + python3？**
> `acpx codex prompt` 預設輸出含 `[client]`、`[error]` 等人類可讀格式，無法直接取得純文字回應。`--format json` 輸出標準 ACP JSON-RPC，python3 從中提取 `agent_message_chunk`。

在 `openclaw.json` 啟用 hook：

```json
"hooks": {
  "internal": {
    "enabled": true,
    "entries": {
      "my-codex-relay-hook": { "enabled": true }
    }
  }
}
```

---

## 步驟四：重啟 gateway

```bash
systemctl --user restart openclaw-gateway.service
sleep 3
openclaw hooks list  # 確認 my-codex-relay-hook ✓ ready
```

---

## 常見問題

### Bot 無回應
```bash
journalctl --user -u openclaw-gateway.service --since "5 min ago" --no-pager | tail -20
```

### Codex session 壞掉
```bash
ACPX=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/.bin/acpx" | head -1)
cd $HOME && $ACPX codex sessions close my-codex-tg 2>/dev/null
$ACPX codex sessions new --name my-codex-tg
```

---

## 檔案清單

```
~/.openclaw/openclaw.json
~/.openclaw/workspace-my-codex-relay/SOUL.md                  # Output NO_REPLY.
~/.openclaw/hooks/my-codex-relay-hook/HOOK.md
~/.openclaw/hooks/my-codex-relay-hook/handler.ts
```

---

## 相關文件

- [OpenClaw × ACP × Kiro 整合指南](./acp_kiro.md)
- [OpenClaw × ACP × Gemini 整合指南](./acp_gemini.md)
