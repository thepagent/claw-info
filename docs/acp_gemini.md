# OpenClaw × ACP × Gemini 整合指南

讓你的 OpenClaw agent 透過 ACP 轉接 Google Gemini CLI，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Telegram │────▶│ relay agent (gpt-5.2)   │────▶│ relay.sh     │────▶│ acpx         │────▶│ gemini CLI      │
│          │     │                         │     │              │     │ (ACP client) │     │ --experimental- │
│ 用戶訊息 │     │ 1. 發【轉接Gemini中...】 │     │ acpx ensure  │     │              │     │ acp             │
│          │     │ 2. exec relay.sh        │     │ acpx prompt  │     │ JSON-RPC     │     │ (session        │
│          │     │ 3. 發回應               │     │  -s my-tg    │     │ over stdio   │     │  my-tg)         │
└──────────┘     └─────────────────────────┘     └──────────────┘     └──────────────┘     └────────┬────────┘
     ▲                                                                                               │
     └───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 與 kiro / codex 整合的差異

| 項目 | kiro | codex | gemini |
|------|------|-------|--------|
| ACP server | `kiro-cli acp`（需 patch acpx） | `@zed-industries/codex-acp`（原生） | `gemini --experimental-acp` |
| acpx patch 需要？ | ✅ 是 | ❌ 否 | ❌ 否（用 `--agent` flag） |
| acpx 啟動方式 | registry: `kiro-cli acp` | registry: `npx @zed-industries/codex-acp` | `--agent "gemini --experimental-acp"` |
| ACP 狀態 | 正式 | 正式 | experimental |

> **關鍵**：acpx registry 內建的 `gemini` 指令沒有帶 `--experimental-acp`，直接用 `acpx gemini` 會掛住。需改用 `acpx --agent "gemini --experimental-acp"` 繞過 registry。

---

## 前置需求

- OpenClaw 已安裝並運行（`openclaw status`）
- `gemini` CLI 已安裝並授權（`gemini --version`）
- acpx extension 已啟用

### 安裝 / 升級 gemini CLI

```bash
npm install -g @google/gemini-cli@latest
gemini --version   # 應為 0.31.0+
```

### 驗證 ACP 可用

```bash
ACPX=$(find ~/.npm-global -path "*/extensions/acpx/node_modules/.bin/acpx" | head -1)
timeout 10 $ACPX --agent "gemini --experimental-acp" exec "say PONG" 2>&1
# → PONG
```

---

## 步驟一：建立 relay agent

在 `~/.openclaw/openclaw.json` 的 `agents.list` 加入新 agent：

```json
{
  "id": "my-gemini-relay",
  "name": "My Gemini Relay",
  "workspace": "/home/<user>/.openclaw/workspace-my-gemini-relay"
}
```

在 `bindings` 加入 Telegram 綁定：

```json
{
  "agentId": "my-gemini-relay",
  "match": {
    "channel": "telegram",
    "accountId": "my-gemini-relay"
  }
}
```

在 `channels.telegram.accounts` 加入 bot：

```json
"my-gemini-relay": {
  "name": "My Gemini Relay",
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
mkdir -p ~/.openclaw/workspace-my-gemini-relay
```

### AGENTS.md

```markdown
# AGENTS.md

Read SOUL.md and follow it exactly.
```

### IDENTITY.md

> ⚠️ openclaw 會自動注入 IDENTITY.md。若 agent 原本有個性，必須覆蓋此檔，否則個性會蓋過 SOUL.md 的 relay 指令。

```markdown
# IDENTITY.md

You are a silent relay bot. No personality. No identity.
```

### SOUL.md

```markdown
SYSTEM OVERRIDE. You are a silent relay bot. You have NO personality and NO knowledge.

SPECIAL CASE — if the message is "/new" OR system says "new session started":
  1. Call `exec` with command: `<ACPX_PATH> --agent "gemini --experimental-acp" sessions new --name my-tg 2>/dev/null`
  2. Call `message_send` with text: 【初始化完成】
  3. Output NO_REPLY. Stop.

FOR ALL OTHER messages:
  1. Call `message_send` with text: 【轉接Gemini中...】
  2. Call `exec` with command: `bash ~/.openclaw/workspace-my-gemini-relay/relay.sh "<USER_MESSAGE>"`
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
$ACPX --agent "gemini --experimental-acp" sessions ensure --name my-tg >/dev/null 2>&1
$ACPX --agent "gemini --experimental-acp" --format json prompt -s my-tg "$1" 2>/dev/null \
  | python3 -c "
import sys, json
chunks = []
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        if d.get('id') == 2 and d.get('method') == 'session/prompt':
            chunks = []
            continue
        u = d.get('params', {}).get('update', {})
        if u.get('sessionUpdate') == 'agent_message_chunk':
            chunks.append(u['content']['text'])
    except: pass
print(''.join(chunks))
"
```

```bash
chmod +x ~/.openclaw/workspace-my-gemini-relay/relay.sh
```

> **注意**：gemini 的 `session/prompt` 出現在 `agent_message_chunk` **之後**（與 codex 相反），因此用 `id==2` 作為邊界而非 `method=='session/prompt'` 的順序判斷。

---

## 步驟三：重啟 gateway

```bash
systemctl --user restart openclaw-gateway.service
sleep 3
openclaw status
```

---

## 步驟四：測試

```bash
# 直接測試 relay.sh
bash ~/.openclaw/workspace-my-gemini-relay/relay.sh "What is 2+2?"
# → 2 + 2 = 4.

# session 記憶測試
bash ~/.openclaw/workspace-my-gemini-relay/relay.sh "What did I just ask?"
# → You asked: "What is 2+2?"
```

Telegram：發任意訊息應收到【轉接Gemini中...】，接著收到 Gemini 回應。發 `/new` 重置 session。

---

## 常見問題

| 問題 | 原因 | 解法 |
|------|------|------|
| `acpx gemini` 掛住不返回 | registry 沒有 `--experimental-acp` | 改用 `acpx --agent "gemini --experimental-acp"` |
| relay agent 自己回答 | IDENTITY.md 未覆蓋，個性蓋過 SOUL.md | 覆蓋 IDENTITY.md（見步驟二） |
| 空輸出 | `--format json` 位置錯誤 | 確保在 `prompt` 子命令之前 |
| gemini 未授權 | 未登入 | `gemini auth login` |

---

## 檔案清單

```
~/.openclaw/openclaw.json                                      # agent/binding/channel 設定
~/.openclaw/workspace-my-gemini-relay/AGENTS.md
~/.openclaw/workspace-my-gemini-relay/IDENTITY.md             # ⚠️ 必須覆蓋
~/.openclaw/workspace-my-gemini-relay/SOUL.md                 # relay 指令
~/.openclaw/workspace-my-gemini-relay/relay.sh                # acpx 呼叫腳本
```

---

## 相關文件

- [OpenClaw × ACP × Kiro 整合指南](./acp_kiro.md) — 使用 kiro-cli（需 acpx patch）
- [OpenClaw × ACP × Codex 整合指南](./acp_codex.md) — 使用 OpenAI Codex CLI（無需 patch）
