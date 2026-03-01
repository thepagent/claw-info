# OpenClaw × Codex CLI 整合指南

讓 OpenClaw agent（如 guan-yu）透過 `codex exec` 呼叫 Codex，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────────┐     ┌───────────────┐
│ Telegram │────▶│ guan-yu agent           │────▶│ codex-relay.sh   │────▶│ codex exec    │
│          │     │ (openclaw)              │     │                  │     │ (OpenAI Codex)│
│ 用戶訊息 │     │ 1. exec codex-relay.sh  │     │ session persist  │     │               │
│          │     │ 2. 回傳 codex 回應      │     │ ~/.codex/sessions│     │ JSONL output  │
└──────────┘     └─────────────────────────┘     └──────────────────┘     └───────────────┘
```

---

## 與 kiro ACP 整合的差異

| 項目 | kiro (ACP) | codex CLI |
|------|-----------|-----------|
| 協定 | ACP JSON-RPC over stdio | 無標準協定，直接 CLI |
| Session 管理 | `acpx kiro sessions ensure --name` | UUID 存檔，`codex exec resume <id>` |
| 非互動執行 | `acpx kiro prompt -s <name>` | `codex exec --json --dangerously-bypass-approvals-and-sandbox` |
| 輸出格式 | ACP `session/update` JSON-RPC | JSONL events (`item.completed`) |
| 需要 patch | 是（acpx 需加入 kiro registry） | 否，直接可用 |

---

## 前置需求

- `codex` CLI 已安裝並授權（`codex --version` 可執行）
- OpenClaw 已運行（`openclaw status`）
- guan-yu agent workspace 存在（`~/.openclaw/workspace-guan-yu/`）

---

## 核心腳本：codex-relay.sh

存放於 `~/.openclaw/workspace-guan-yu/codex-relay.sh`

```bash
#!/bin/bash
# Usage: codex-relay.sh <session-name> <prompt>
#        codex-relay.sh --new <session-name>   (reset session)

CODEX=/home/pahud/.npm-global/bin/codex
SESSION_DIR=/home/pahud/.openclaw/workspace-guan-yu/codex-sessions
mkdir -p "$SESSION_DIR"

SESSION_NAME="${1}"
PROMPT="${2}"
SESSION_FILE="$SESSION_DIR/${SESSION_NAME}.id"

# --new: reset session
if [ "$SESSION_NAME" = "--new" ]; then
  rm -f "$SESSION_DIR/${2}.id"
  echo "【Session reset: ${2}】"
  exit 0
fi

extract_reply() {
  python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        if d.get('type') == 'item.completed' and d.get('item', {}).get('type') == 'agent_message':
            print(d['item']['text'])
    except: pass
"
}

extract_session_id() {
  python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        if d.get('type') == 'thread.started':
            print(d['thread_id'])
    except: pass
"
}

if [ -f "$SESSION_FILE" ]; then
  SESSION_ID=$(cat "$SESSION_FILE")
  $CODEX exec resume "$SESSION_ID" \
    --json --dangerously-bypass-approvals-and-sandbox \
    "$PROMPT" 2>/dev/null | extract_reply
else
  OUTPUT=$($CODEX exec \
    --json --dangerously-bypass-approvals-and-sandbox \
    "$PROMPT" 2>/dev/null)
  echo "$OUTPUT" | extract_session_id > "$SESSION_FILE"
  echo "$OUTPUT" | extract_reply
fi
```

```bash
chmod +x ~/.openclaw/workspace-guan-yu/codex-relay.sh
```

---

## Session 持久化原理

codex 每次 `exec` 會產生一個 UUID session，存於 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`。

`codex exec resume <UUID>` 可恢復對話歷史。

`codex-relay.sh` 將 UUID 存於 `codex-sessions/<name>.id`，實現跨呼叫持久化。

```
~/.openclaw/workspace-guan-yu/
  codex-relay.sh
  codex-sessions/
    guan-yu-tg.id      ← 存 UUID，如 019cab64-eea5-7f81-b258-b14d6a6533b5
```

---

## SOUL.md 整合（guan-yu agent）

在 guan-yu 的 SOUL.md 加入 codex relay 指令段：

```markdown
## /codex 指令

收到 `/codex <prompt>` 時：
1. 呼叫 `exec`：`bash ~/.openclaw/workspace-guan-yu/codex-relay.sh guan-yu-tg "<prompt>"`
2. 回傳 exec 輸出。

收到 `/codex-new` 時：
1. 呼叫 `exec`：`bash ~/.openclaw/workspace-guan-yu/codex-relay.sh --new guan-yu-tg`
2. 回傳【Session 已重置】。
```

---

## JSONL 輸出格式

`codex exec --json` 輸出 JSONL，關鍵事件：

```jsonl
{"type":"thread.started","thread_id":"019cab64-..."}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"回應內容"}}
{"type":"turn.completed","usage":{"input_tokens":7501,"output_tokens":19}}
```

只需擷取 `type=item.completed` 且 `item.type=agent_message` 的 `text`。

---

## 測試

```bash
# 新 session
~/.openclaw/workspace-guan-yu/codex-relay.sh "test" "My name is Guan Yu. Say READY."
# → READY

# 恢復 session（記憶測試）
~/.openclaw/workspace-guan-yu/codex-relay.sh "test" "What is my name?"
# → Your name is Guan Yu.

# 重置 session
~/.openclaw/workspace-guan-yu/codex-relay.sh --new "test"
# → 【Session reset: test】
```

---

## 常見問題

| 問題 | 原因 | 解法 |
|------|------|------|
| 無輸出 | codex 未授權 | `codex login` |
| session 遺失 | `.id` 檔被刪 | 重新建立（自動） |
| 回應過慢 | codex 推理中 | 正常，約 5-15 秒 |

---

## 檔案清單

```
~/.openclaw/workspace-guan-yu/
  codex-relay.sh                  ← relay 腳本
  codex-sessions/
    <session-name>.id             ← codex session UUID
```
