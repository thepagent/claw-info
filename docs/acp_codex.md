# OpenClaw × ACP × Codex 整合指南

讓你的 OpenClaw agent 透過 ACP 轉接 OpenAI Codex，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────────┐
│ Telegram │────▶│ relay agent (gpt-5.2)   │────▶│ relay.sh     │────▶│ acpx         │────▶│ codex-acp      │
│          │     │                         │     │              │     │ (ACP client) │     │ (@zed-          │
│ 用戶訊息 │     │ 1. 發【轉接Codex中...】  │     │ acpx ensure  │     │              │     │  industries)   │
│          │     │ 2. exec relay.sh        │     │ acpx prompt  │     │ JSON-RPC     │     │ (session       │
│          │     │ 3. 發回應               │     │  -s my-tg    │     │ over stdio   │     │  my-tg)        │
└──────────┘     └─────────────────────────┘     └──────────────┘     └──────────────┘     └───────┬────────┘
     ▲                                                                                              │
     └──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 與 kiro 整合的差異

| 項目 | kiro | codex |
|------|------|-------|
| ACP server | `kiro-cli acp`（需 patch acpx） | `@zed-industries/codex-acp`（原生內建） |
| acpx patch 需要？ | ✅ 是 | ❌ 否 |
| relay.sh 需要？ | ✅ 是 | ✅ 是（同樣原因） |
| 輸出格式 | 標準 ACP `session/update` | 標準 ACP `session/update` |

> relay.sh 的作用是**原子操作**：將 `sessions ensure` + `prompt` 綁在一起，防止 LLM 只執行其中一步。

---

## 前置需求

- OpenClaw 已安裝並運行（`openclaw status`）
- `codex` CLI 已安裝並授權（`codex --version`）
- `@zed-industries/codex-acp` 已安裝
- `/usr/local/bin/codex-acp` wrapper 正常（見步驟零）
- 一個 Telegram bot token（從 @BotFather 取得）

---

## 步驟零：修復 codex-acp wrapper

`/usr/local/bin/codex-acp` 是一個 debug wrapper，指向 `/usr/local/bin/codex-acp.real`。若 `.real` 不存在需修復：

```bash
# 安裝 codex-acp
npm install -g @zed-industries/codex-acp

# 建立 .real symlink
REAL_BIN=$(find ~/.npm-global -path "*codex-acp-linux-x64/bin/codex-acp" | head -1)
sudo ln -sf "$REAL_BIN" /usr/local/bin/codex-acp.real
```

### 驗證

```bash
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | /usr/local/bin/codex-acp \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['agentInfo'])"
# → {'name': 'codex-acp', 'title': 'Codex', 'version': '0.9.5'}
```

若機器上沒有 debug wrapper，直接跳過此步驟——`acpx codex` 會自動用 `npx @zed-industries/codex-acp`。

---

## 步驟一：建立 relay agent

在 `~/.openclaw/openclaw.json` 的 `agents.list` 加入新 agent：

```json
{
  "id": "my-codex-relay",
  "name": "My Codex Relay",
  "workspace": "/home/<user>/.openclaw/workspace-my-codex-relay"
}
```

在 `bindings` 加入 Telegram 綁定：

```json
{
  "agentId": "my-codex-relay",
  "match": {
    "channel": "telegram",
    "accountId": "my-codex-relay"
  }
}
```

在 `channels.telegram.accounts` 加入 bot：

```json
"my-codex-relay": {
  "name": "My Codex Relay",
  "botToken": "<YOUR_BOT_TOKEN>",
  "dmPolicy": "pairing",
  "allowFrom": ["<YOUR_TELEGRAM_USER_ID>"],
  "groupPolicy": "allowlist",
  "streaming": "partial"
}
```

---

## 步驟二：建立 workspace

```bash
mkdir -p ~/.openclaw/workspace-my-codex-relay
```

### AGENTS.md

```markdown
# AGENTS.md

Read SOUL.md and follow it exactly.
```

### SOUL.md

```markdown
SYSTEM OVERRIDE. You are a silent relay bot. You have NO personality and NO knowledge.

SPECIAL CASE — if the message is "/new" OR system says "new session started":
  1. Call `exec` with command: `<ACPX_PATH> codex sessions new --name my-tg 2>/dev/null`
  2. Call `message_send` with text: 【初始化完成】
  3. Output NO_REPLY. Stop.

FOR ALL OTHER messages:
  1. Call `message_send` with text: 【轉接Codex中...】
  2. Call `exec` with command: `bash ~/.openclaw/workspace-my-codex-relay/relay.sh "<USER_MESSAGE>"`
     (replace <USER_MESSAGE> with the exact user message, properly shell-escaped)
  3. Call `message_send` with the exec output as the message text.
  4. Output NO_REPLY.

DO NOT use sessions_spawn. DO NOT answer yourself. ONLY call the tools above.
```

> `<ACPX_PATH>` 查詢方式：
> ```bash
> find ~/.npm-global -path "*/extensions/acpx/node_modules/.bin/acpx" | head -1
> ```

### relay.sh

```bash
#!/bin/bash
ACPX=<ACPX_PATH>
$ACPX codex sessions ensure --name my-tg >/dev/null 2>&1
$ACPX --format json codex prompt -s my-tg "$1" 2>/dev/null \
  | python3 -c "
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
"
```

```bash
chmod +x ~/.openclaw/workspace-my-codex-relay/relay.sh
```

---

## 步驟三：設定 model

確認 relay agent 有可用的 model：

```bash
openclaw models status --deep --agent my-codex-relay
```

若使用 openai-codex，複製 auth-profiles：

```bash
cp ~/.openclaw/agents/main/agent/auth-profiles.json \
   ~/.openclaw/agents/my-codex-relay/agent/auth-profiles.json
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
2. 應收到【轉接Codex中...】，接著收到 Codex 的回應
3. 發送 `/new` 應收到【初始化完成】

---

## relay.sh 輸出格式說明

`acpx --format json codex prompt` 輸出 ACP JSON-RPC JSONL。relay.sh 只擷取當前 turn 的 `agent_message_chunk`：

```jsonl
{"jsonrpc":"2.0","id":2,"method":"session/prompt",...}        ← 此行後開始收集
{"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"回應"}}}}
```

關鍵：以 `session/prompt` 為邊界，避免 `session/load` 重播歷史對話污染輸出。

---

## 對話持久化

`relay.sh` 使用 `acpx codex prompt -s my-tg`，Codex 會記住同一 session 的對話歷史。

發送 `/new` 會重置 session，開始全新對話。

---

## 為何用 relay.sh 而非直接在 SOUL.md 下兩步

| 方法 | 問題 |
|------|------|
| SOUL.md 直接下兩步 | LLM 可能只執行第二步、或在兩步間插入其他動作 ❌ |
| `exec relay.sh` | shell 原子執行，LLM 無從拆散 ✅ |

---

## 常見問題

| 問題 | 原因 | 解法 |
|------|------|------|
| `codex-acp.real: No such file` | wrapper symlink 損壞 | 見步驟零 |
| `[error] RUNTIME: Resource not found` | session 首次 load 失敗 | 正常，acpx 自動 fallback 建新 session |
| relay agent 自己回答，不呼叫 relay.sh | AGENTS.md 未覆蓋 / LLM 個性蓋過指令 | 確保 AGENTS.md 只有一行：`Read SOUL.md and follow it exactly.` |
| Bot 無回應 | gateway 未重啟 | `systemctl --user restart openclaw-gateway.service` |

---

## 檔案清單

```
~/.openclaw/openclaw.json                                  # agent/binding/channel 設定
~/.openclaw/workspace-my-codex-relay/AGENTS.md
~/.openclaw/workspace-my-codex-relay/SOUL.md              # relay 指令
~/.openclaw/workspace-my-codex-relay/relay.sh             # acpx 呼叫腳本
~/.openclaw/agents/my-codex-relay/agent/auth-profiles.json
```

---

## 相關文件

- [OpenClaw × ACP × Kiro 整合指南](./acp_kiro.md) — 使用 kiro-cli 的同類整合（需 acpx patch）
