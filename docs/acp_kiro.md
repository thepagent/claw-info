# OpenClaw × ACP × Kiro 整合指南

讓你的 OpenClaw 透過 ACP 轉接 Kiro，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────────────────────────┐
│ Telegram │────▶│  openclaw gateway                           │
│          │     │                                             │
│ 用戶訊息 │     │  ① <agent>-relay hook (message_received)    │
│          │     │     │                                       │
└──────────┘     │     │  acpx kiro prompt -s my-kiro-tg -f -     │
     ▲           │     │  (stdin，無 shell quoting 問題)        │
     │           │     ▼                                       │
     │           │  ┌──────────────────────┐                  │
     │           │  │  Kiro ACP session    │                  │
     │           │  │  my-kiro-tg             │                  │
     │           │  └──────────┬───────────┘                  │
     │           │             │ reply text                    │
     │           │             ▼                               │
     └───────────│  fetch api.telegram.org/sendMessage         │
                 │  (直接打 Bot API，繞過 openclaw 訊息系統)    │
                 │                                             │
                 │  ② my-kiro-relay agent (SOUL: "Output NO_REPLY.")    │
                 │     └▶ 偶爾輸出 NO（閃一下即刪，可接受）    │
                 └─────────────────────────────────────────────┘
```

---

## 前置需求

- OpenClaw 已安裝並運行（`openclaw status`）
- `kiro-cli` 已安裝（`kiro-cli --version`）
- acpx extension 已啟用（`openclaw doctor --fix`）
- 一個 Telegram bot token（從 @BotFather 取得）
- acpx 已套用 kiro patch（見下方步驟零）

---

## 步驟零：為 acpx 套用 kiro patch

原版 acpx 不支援 kiro-cli，需要修改後重新 build 並部署。

> **Upstream fix pending**：[openclaw/acpx#42](https://github.com/openclaw/acpx/pull/42) 正在 review 中，合併後官方 acpx 即內建 kiro 且修復 process leak，步驟零可省略。

### Build 與部署

```bash
git clone https://github.com/thepagent/acpx.git ~/repo/acpx
cd ~/repo/acpx
git checkout fix/kill-agent-on-queue-owner-exit

npm install && npm run build

ACPX_DIST=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/acpx/dist/cli.js" | head -1)
cp dist/cli.js "$ACPX_DIST"
```

---

## 步驟一：建立 relay agent

在 `~/.openclaw/openclaw.json` 加入 agent、binding、Telegram account：

```json
// agents.list
{ "id": "my-kiro-relay", "name": "Klaw", "workspace": "/home/<user>/.openclaw/workspace-my-kiro-relay" }

// bindings
{ "agentId": "my-kiro-relay", "match": { "channel": "telegram", "accountId": "my-kiro-relay" } }

// channels.telegram.accounts
"my-kiro-relay": {
  "name": "Klaw",
  "botToken": "<YOUR_BOT_TOKEN>",
  "dmPolicy": "pairing",
  "allowFrom": ["<YOUR_TELEGRAM_USER_ID>"],
  "groupPolicy": "allowlist"
}
```

---

## 步驟二：建立 workspace

```bash
mkdir -p ~/.openclaw/workspace-my-kiro-relay
```

### SOUL.md

```
Output NO_REPLY.
```

> SOUL.md 只需一行。真正的 relay 由 hook 處理。
> LLM 偶爾輸出 `NO` 而非 `NO_REPLY`，Telegram 短暫顯示後自動刪除，屬正常現象。

---

## 步驟三：建立 hook

```bash
mkdir -p ~/.openclaw/hooks/my-kiro-relay-hook
```

### HOOK.md

```markdown
---
name: my-kiro-relay-hook
description: "Relay Klaw Telegram DM messages to Kiro via acpx and push reply back"
metadata:
  { "openclaw": { "emoji": "🔀", "events": ["message:received"] } }
---
```

### handler.ts

```typescript
import { execSync } from "child_process";

const ACPX = "/home/<user>/.npm-global/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx";
const SESSION = "my-kiro-tg";
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
  if (!event.sessionKey?.startsWith("agent:my-kiro-relay:telegram:direct:")) return;

  const content = event.context?.content;
  if (!content) return;

  // /new: reset Kiro ACP session (openclaw resets LLM session separately)
  if (content.trim() === "/new") {
    execSync(`${ACPX} kiro sessions close ${SESSION} 2>/dev/null`, { encoding: "utf8" });
    return;
  }

  const chatId = event.sessionKey.split(":").pop();
  if (!chatId) return;

  try {
    execSync(`${ACPX} kiro sessions ensure --name ${SESSION}`, { encoding: "utf8" });
    const result = execSync(
      `${ACPX} kiro prompt -s ${SESSION} -f -`,
      { input: content, timeout: 60000, encoding: "utf8" }
    );
    const reply = result.trim().split("\n").filter(l => l && !l.startsWith("[")).join("\n");
    if (reply) await sendTelegram(chatId, reply);
  } catch (err) {
    // silent fail
  }
};

export default handler;
```

> **為何用 stdin（`-f -`）？**
> Telegram 訊息含 JSON metadata（sender info 等），直接嵌入 shell 指令會導致 quoting 破壞，出現 `json: command not found`。stdin 完全繞開此問題。

> **為何 `/new` 要 close session？**
> openclaw 的 `/new` 只重置 LLM session，不影響 Kiro 的 ACP session。hook 裡手動 close 確保兩邊都重置。

在 `openclaw.json` 啟用 hook：

```json
"hooks": {
  "internal": {
    "enabled": true,
    "entries": {
      "my-kiro-relay-hook": { "enabled": true }
    }
  }
}
```

---

## 步驟四：重啟 gateway

```bash
systemctl --user restart openclaw-gateway.service
sleep 3
openclaw hooks list  # 確認 my-kiro-relay-hook ✓ ready
```

---

## 步驟五：測試

1. 在 Telegram 發送任意訊息 → 直接收到 Kiro 回應
2. 發送 `/new` → openclaw 重置 LLM session，hook 重置 Kiro ACP session

---

## 為何用 hook 而非 SOUL relay

| 方法 | 問題 |
|------|------|
| SOUL + `exec relay.sh "$1"` | JSON metadata 破壞 shell quoting |
| SOUL + `KLAW_MSG='...' relay.sh` | LLM 不可靠，偶爾不遵守指令 |
| hook + Bot API | ✅ 完全繞過 LLM，穩定可靠 |

> `message_received` 是 void hook（fire-and-forget），`event.messages.push` 無效。
> 因此 hook 直接呼叫 Telegram Bot API，不依賴 openclaw 訊息系統。

---

## 常見問題

### Bot 無回應
```bash
journalctl --user -u openclaw-gateway.service --since "5 min ago" --no-pager | tail -20
```

### hook 未載入
```bash
openclaw hooks list  # 確認 ✓ ready
```

### ACP 模式下 MCP tools 無法使用

**症狀：**
- MCP servers 在`~/.kiro/settings/mcp.json` 中已配置
- `kiro-cli mcp list` 顯示 servers 正常
- 但 ACP 模式下agent 只能看到基本工具（read, write, shell 等）
- 無法使用 web-search、fetch 等 MCP 工具

**原因：**
`~/.kiro/settings/mcp.json` 的配置只載入到 default profile（`kiro_default`），不會自動繼承到 ACP agent。

**解決方案：**

1. **將 MCP servers 複製到 agent 配置：**

編輯 `~/.kiro/agents/<agent-name>.json`：

```json
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "env": {},
      "disabled": false,
      "autoApprove": []
    },
    "Context7": {
      "command": "npx-for-claude",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {},
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```

2. **添加內建工具和 allowedTools：**

```json
{
  "tools": [
    "read", "write", "shell", "report", "introspect",
    "knowledge", "thinking", "grep", "glob",
    "web_search", "use_subagent", "todo_list"
  ],
  "allowedTools": [
    "@fetch", "@Context7", "@web-search"
  ]
}
```

`@{MCP_SERVER_NAME}` 語法會白名單該 MCP server 的所有工具。

3. **在 relay.sh 中添加 `-a` flag：**

```bash
kiro-cli acp --agent <name> --model <model> -a
```

`-a` (trust-all-tools) 讓 shell 指令無需互動批准，ACP 模式必備。

**已知限制：**
- Skills (`~/.kiro/skills/`) 在 ACP 模式不作用（依賴 IDE-only 的`discloseContext`）
- Agent 的 `prompt` 欄位在 ACP 模式會被忽略（workaround：透過 relay.sh 注入或 `.kiro/steering/` 檔案）
- `useLegacyMcpJson` 設定不影響行為，MCP servers 必須在 agent 的 `mcpServers` 欄位

---

## 檔案清單

```
~/.openclaw/openclaw.json
~/.openclaw/workspace-my-kiro-relay/SOUL.md                 # Output NO_REPLY.
~/.openclaw/hooks/my-kiro-relay-hook/HOOK.md
~/.openclaw/hooks/my-kiro-relay-hook/handler.ts
```

---

## 相關文件

- [OpenClaw × ACP × Codex 整合指南](./acp_codex.md)
- [OpenClaw × ACP × Gemini 整合指南](./acp_gemini.md)
