# OpenClaw × ACP × Kiro 整合指南

讓你的 OpenClaw agent 透過 Telegram 轉接 Kiro，實現對話持久化。

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

原版 acpx 不支援 kiro-cli，需要三處修改後重新 build 並部署。

### 原因

kiro-cli 與 acpx 都實作 ACP（Agent Client Protocol）`protocolVersion: 1`，協議版本相同。但 kiro-cli 在串流回應時，輸出的是**非標準的裸 JSON 格式**：

```json
{"content":"回應文字","type":"text"}
```

而 ACP 標準要求的是完整的 JSON-RPC 2.0 notification：

```json
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "...",
    "update": {
      "sessionUpdate": "agent_message_chunk",
      "content": {"type": "text", "text": "回應文字"}
    }
  }
}
```

acpx 只能解析標準格式，收到裸 JSON 時直接忽略，導致 kiro 的回應全部消失。

此外，acpx 的 agent registry 沒有內建 kiro，無法用 `acpx kiro` 指令。

patch 的作用：
1. 在 registry 加入 `kiro: "kiro-cli acp"`
2. 在 client 加入 `normalizeAgentOutput()` TransformStream，即時將裸 JSON 轉換成標準 ACP envelope

> **Bug report**：[kirodotdev/Kiro#6131](https://github.com/kirodotdev/Kiro/issues/6131)
> 若 kiro-cli 官方修正此問題，步驟零可省略。

### 修改內容

**1. `src/agent-registry.ts` — 註冊 kiro agent**
```typescript
kiro: "kiro-cli acp",
```

**2. `src/cli-core.ts` — 加入版本號（openclaw health check 需要）**
```typescript
.version("0.1.13", "--version", "Print version")
```

**3. `src/client.ts` — 加入 `normalizeAgentOutput()` TransformStream**

將 kiro 的裸輸出包裝成標準 ACP `session/update` envelope：
```typescript
// 偵測 {"content":"...","type":"text"} 格式
// 包裝成 {"jsonrpc":"2.0","method":"session/update","params":{...}}
```
完整實作見：https://github.com/thepagent/acpx/tree/feat/kiro-agent

### Build 與部署

```bash
git clone https://github.com/thepagent/acpx.git ~/repo/acpx
cd ~/repo/acpx
git checkout feat/kiro-agent

npm install
npm run build

# 找到 openclaw 內建的 acpx dist 路徑
ACPX_DIST=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/acpx/dist/cli.js" | head -1)
cp dist/cli.js "$ACPX_DIST"
```

### 驗證

```bash
ACPX=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/.bin/acpx" | head -1)
$ACPX --version          # 應顯示 0.1.13
$ACPX kiro sessions new --name test 2>&1 | tail -2
systemctl --user restart openclaw-gateway.service
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
$ACPX kiro sessions ensure --name my-tg 2>/dev/null
$ACPX kiro prompt -s my-tg "$1" 2>/dev/null | grep -v '^\[' | grep -v '^$' | head -50
```

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

openclaw PR [#28817](https://github.com/openclaw/openclaw/pull/28817) / [#29547](https://github.com/openclaw/openclaw/pull/29547) 將 ACP client 內建進 openclaw。若 kiro-cli 官方修正裸 JSON 問題，合併後可直接用 `sessions_spawn(runtime:"acp-standard", agentId:"kiro")` 取代 relay.sh，不再需要 acpx patch。

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

---

## 檔案清單

```
~/.openclaw/openclaw.json                          # agent/binding/channel 設定
~/.openclaw/workspace-my-relay/AGENTS.md
~/.openclaw/workspace-my-relay/SOUL.md             # relay 指令
~/.openclaw/workspace-my-relay/relay.sh            # acpx 呼叫腳本
~/.openclaw/agents/my-relay/agent/auth-profiles.json
```
