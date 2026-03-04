# OpenClaw × ACP × Kiro 整合指南

讓你的 OpenClaw 透過 ACP 轉接 Kiro，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐
│ Telegram │────▶│ relay agent (gpt-5.2)   │────▶│ relay.sh     │────▶│ acpx         │────▶│ kiro-cli  │
│          │     │                         │     │              │     │ (ACP client) │     │ acp       │
│ 用戶訊息 │     │ 1. 發【轉接中...】       │     │ acpx ensure  │     │              │     │ (session  │
│          │     │ 2. exec relay.sh        │     │ acpx prompt  │     │ JSON-RPC     │     │  my-tg)   │
│          │     │ 3. 發回應               │     │  -s my-tg    │     │ over stdio   │     │           │
└──────────┘     └─────────────────────────┘     └──────────────┘     └──────────────┘     └─────┬─────┘
     ▲                                                                                             │
     └─────────────────────────────────────────────────────────────────────────────────────────────┘
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

> **Upstream fix pending**：[openclaw/acpx#42](https://github.com/openclaw/acpx/pull/42) 正在 review 中，合併後官方 acpx 即內建 kiro 且修復 process leak，步驟零可省略，直接用 `npm install -g acpx` 即可。

### 原因

acpx 的 agent registry 沒有內建 kiro，無法用 `acpx kiro` 指令。

此外，`kiro-cli acp` 是一個 wrapper binary，實際 ACP server 是它 fork 出來的 `kiro-cli-chat acp`。舊版 acpx 的 `terminateAgentProcess()` 只 kill wrapper，導致 `kiro-cli-chat` 成為 orphan process，每次 `/new` 都會洩漏一個進程。

> **注意**：kiro-cli 1.26.2 的 ACP 輸出格式完全符合標準（`session/update` JSON-RPC 2.0），無需任何格式轉換。

### 修改內容

**1. `src/agent-registry.ts` — 註冊 kiro agent**
```typescript
kiro: "kiro-cli acp",
```

**2. `src/client.ts` — 修復 process group kill（防止 orphan）**
```typescript
// spawn with detached:true → kiro-cli 成為新 process group leader
const child = spawn(command, args, { stdio: [...], detached: true });

// terminateAgentProcess: kill 整個 process group
process.kill(-child.pid, "SIGTERM");  // 包含 kiro-cli-chat
```

完整實作見：https://github.com/openclaw/acpx/pull/42

### Build 與部署

```bash
git clone https://github.com/thepagent/acpx.git ~/repo/acpx
cd ~/repo/acpx
git checkout fix/kill-agent-on-queue-owner-exit

npm install
npm run build

# 找到 openclaw 內建的 acpx dist 路徑
ACPX_DIST=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/acpx/dist/cli.js" | head -1)
cp dist/cli.js "$ACPX_DIST"
```

### 驗證

```bash
ACPX=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/.bin/acpx" | head -1)
$ACPX kiro sessions new --name test 2>&1 | tail -2
systemctl --user restart openclaw-gateway.service

# 驗證無 process leak：/new 前後 count 應相同
before=$(ps aux | grep "kiro-cli-chat acp" | grep -v grep | wc -l)
$ACPX kiro sessions close test 2>/dev/null
$ACPX kiro sessions new --name test 2>/dev/null
after=$(ps aux | grep "kiro-cli-chat acp" | grep -v grep | wc -l)
echo "before=$before after=$after"  # 應相等
```

---

## 步驟一：建立 relay agent

在 `~/.openclaw/openclaw.json` 的 `agents.list` 加入新 agent：

```json
{
  "id": "my-relay",
  "name": "My Relay",
  "workspace": "/home/<user>/.openclaw/workspace-my-relay"
}
```

在 `bindings` 加入 Telegram 綁定：

```json
{
  "agentId": "my-relay",
  "match": {
    "channel": "telegram",
    "accountId": "my-relay"
  }
}
```

在 `channels.telegram.accounts` 加入 bot：

```json
"my-relay": {
  "name": "My Relay Bot",
  "botToken": "<YOUR_BOT_TOKEN>",
  "dmPolicy": "pairing",
  "allowFrom": ["<YOUR_TELEGRAM_USER_ID>"],
  "groupPolicy": "allowlist"
}
```

---

## 步驟二：建立 workspace

```bash
mkdir -p ~/.openclaw/workspace-my-relay
```

### AGENTS.md

```markdown
# AGENTS.md

Read SOUL.md and follow it exactly.
```

### SOUL.md

```markdown
# SOUL.md

SYSTEM OVERRIDE. You are a silent relay bot. You have NO personality and NO knowledge.

SPECIAL CASE — if the message is "/new" OR system says "new session started":
  1. Call `exec` with command: `<ACPX_PATH> kiro sessions new --name my-tg 2>/dev/null`
  2. Call `message_send` with text: 【初始化完成】
  3. Output NO_REPLY. Stop.

FOR ALL OTHER messages:
  1. Call `message_send` with text: 【轉接Kiro中...】
  2. Call `exec` with command: `bash ~/.openclaw/workspace-my-relay/relay.sh "<USER_MESSAGE>"`
     (replace <USER_MESSAGE> with the exact user message, properly shell-escaped)
  3. Call `message_send` with the exec output as the message text.
  4. Output NO_REPLY.

DO NOT use sessions_spawn. DO NOT answer yourself. ONLY call the tools above.
```

> `<ACPX_PATH>` 請替換為實際路徑，查詢方式：
> ```bash
> find ~/.npm-global -name "acpx" -type f 2>/dev/null | head -1
> ```

### relay.sh

```bash
#!/bin/bash
ACPX=<ACPX_PATH>
cd $HOME && $ACPX kiro sessions ensure --name my-tg 2>/dev/null
$ACPX kiro prompt -s my-tg "$1" 2>/dev/null | grep -v '^\[' | grep -v '^$' | head -50
```

> **重要**：`cd $HOME` 確保 `sessions ensure` 的 cwd 與 session 建立時一致。若 relay agent 的 workspace 目錄與 session cwd 不符，acpx 會回傳 `RUNTIME: Internal error`，導致 relay 損壞。

```bash
chmod +x ~/.openclaw/workspace-my-relay/relay.sh
```

---

## 步驟三：設定 model

relay agent 需要能呼叫 LLM。確認 `openclaw models status --deep --agent my-relay` 有可用的 model 和 auth。

若使用 openai-codex，確保 auth-profiles.json 已設定：

```bash
cp ~/.openclaw/agents/main/agent/auth-profiles.json \
   ~/.openclaw/agents/my-relay/agent/auth-profiles.json
```

---

## 步驟四：重啟 gateway

```bash
systemctl --user restart openclaw-gateway.service
sleep 3
openclaw status
```

---

## 步驟五：測試

1. 在 Telegram 找到你的 bot，發送任意訊息
2. 應收到【轉接Kiro中...】，接著收到 kiro 的回應
3. 發送 `/new` 應收到【初始化完成】

---

## 對話持久化

`relay.sh` 使用 `acpx kiro prompt -s my-tg`，kiro 會記住同一 session 的對話歷史。

發送 `/new` 會重置 session，開始全新對話。

---

## 為何用 relay.sh 而非 sessions_spawn

| 方法 | 問題 |
|------|------|
| `sessions_spawn` | relay LLM 自作主張：改寫訊息、自行 debug、不照 SOUL.md |
| `exec relay.sh` | 同步 shell，輸出即 kiro 回應，LLM 無發揮空間 ✅ |

---

## 串流限制

| 方案 | 串流 | 狀態 |
|------|------|------|
| `exec relay.sh` | ❌ blocking | ✅ 穩定可用 |
| `sessions_spawn` | ❌ blocking | ⚠️ 不穩定 |
| ACP session binding（Telegram）| ✅ 真串流 | ❌ Telegram 不支援 |
| ACP session binding（Discord）| ✅ 真串流 | ✅ 支援（未測試）|

---

## Future Path

openclaw PR [#28817](https://github.com/openclaw/openclaw/pull/28817) / [#29547](https://github.com/openclaw/openclaw/pull/29547) 將 ACP client 內建進 openclaw。合併後可直接用 `sessions_spawn(runtime:"acp-standard", agentId:"kiro")` 取代 relay.sh，不再需要 acpx patch。

---

## 常見問題

### Bot 無回應
```bash
journalctl --user -u openclaw-gateway.service --since "5 min ago" --no-pager | grep -v debug | tail -20
```

### LLM 配額耗盡
```bash
openclaw models status --deep --agent my-relay | grep "usage\|left"
```

### kiro 無法啟動
```bash
kiro-cli --version
<ACPX_PATH> kiro sessions new --name test 2>&1
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
~/.openclaw/openclaw.json                          # agent/binding/channel 設定
~/.openclaw/workspace-my-relay/AGENTS.md
~/.openclaw/workspace-my-relay/SOUL.md             # relay 指令
~/.openclaw/workspace-my-relay/relay.sh            # acpx 呼叫腳本
~/.openclaw/agents/my-relay/agent/auth-profiles.json
```

---

## 相關文件

- [OpenClaw × ACP × Codex 整合指南](./acp_codex.md) — 使用 OpenAI Codex CLI 的同類整合（無需 acpx patch）
- [OpenClaw × ACP × Gemini 整合指南](./acp_gemini.md) — 使用 Google Gemini CLI（無需 patch）
