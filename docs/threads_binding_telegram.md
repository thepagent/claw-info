# Telegram 討論串（Topic）綁定 ACP 代理

說明如何將 Telegram 論壇群組的特定 Topic 直接綁定到外部 ACP 代理（如 Codex、Kiro），讓訊息繞過本地 LLM，直接轉發至 ACP session。

## 架構圖

```
Telegram 群組：支持Topic的群組
┌─────────────────────────────────────────────────────┐
│  Topic: #codex-general          Topic: #general     │
│  ┌─────────────────────┐        ┌─────────────────┐ │
│  │ 你好，請自我介紹     │        │ 大家好          │ │
│  └─────────────────────┘        └─────────────────┘ │
└──────────────┬──────────────────────────┬───────────┘
               │                          │
               │ requireMention: false     │ requireMention: true
               │（符合 ACP binding 條件）  │（其他 bot 保持靜默）
               ▼                          ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   @guanyu                │    │  @klaw / @kongming       │
│   帳號：guan-yu          │    │  丟棄：未被提及           │
└──────────────┬───────────┘    └──────────────────────────┘
               │
               │ bindings[type=acp]
               │ peer.id = <groupId>:topic:<threadId>
               │ ✗ 本地 LLM 不會被呼叫
               ▼
┌─────────────────────────────────────────────────────┐
│   openclaw ACP 控制層                               │
│                                                     │
│   agentId:  guan-yu                                 │
│   runtime:  acpx                                    │
│   agent:    codex                                   │
│   cwd:      workspace-guan-yu/                      │
│   mode:     persistent                              │
└──────────────────────────┬──────────────────────────┘
                           │ acpx 啟動／重用 session
                           ▼
┌─────────────────────────────────────────────────────┐
│   codex-acp 外部程序                                │
│                                                     │
│   讀取：workspace-guan-yu/SOUL.md                   │
│         workspace-guan-yu/memory/                   │
│   模型：Codex CLI 自身的模型設定                    │
│   session：persistent（同一 topic 共用上下文）      │
└──────────────────────────┬──────────────────────────┘
                           │ 回覆文字
                           ▼
┌─────────────────────────────────────────────────────┐
│   Telegram Bot API                                  │
│   sendMessage                                       │
│   chat_id:           <groupId>                      │
│   message_thread_id: <threadId>                     │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
              #codex-general ← guan-yu 回覆
```

## 運作原理

openclaw 的 `bindings` 設定支援 `"acp"` 類型，可攔截符合條件的入站訊息，直接路由到 ACP session，而不觸發本地代理的 LLM。

Telegram 論壇 Topic 的 peer id 格式為 `<groupId>:topic:<threadId>`。

## 設定範例

```json
{
  "agents": {
    "list": [
      {
        "id": "guan-yu",
        "runtime": {
          "type": "acp",
          "acp": {
            "agent": "codex"
          }
        }
      }
    ]
  },
  "bindings": [
    {
      "type": "acp",
      "agentId": "guan-yu",
      "comment": "將 #codex-general topic 綁定到 Codex ACP session",
      "match": {
        "channel": "telegram",
        "accountId": "guan-yu",
        "peer": {
          "kind": "group",
          "id": "-100xxxxxxxxxx:topic:2"
        }
      },
      "acp": {
        "mode": "persistent",
        "cwd": "~/.openclaw/workspace-guan-yu"
      }
    }
  ]
}
```

欄位說明：

| 欄位 | 說明 |
|---|---|
| `type: "acp"` | 必填，區別於一般路由 binding |
| `agentId` | 擁有此 binding 的 openclaw 代理（決定由哪個 bot 回覆） |
| `match.accountId` | 對應的 Telegram bot 帳號 |
| `match.peer.kind` | 超級群組 topic 填 `"group"` |
| `match.peer.id` | `"<groupId>:topic:<threadId>"` |
| `agents[].runtime.acp.agent` | acpx harness ID（須存在於 `~/.acpx/config.json`） |
| `acp.cwd` | ACP 代理的工作目錄，決定其讀取的 SOUL.md 與記憶檔 |
| `acp.mode` | `"persistent"` 讓同一 topic 的訊息共用同一 ACP session |

## 前置條件

### 1. 關閉 Bot 隱私模式

預設情況下 Telegram bot 在群組中只能收到被 @ 的訊息。需透過 BotFather 關閉：

BotFather → `/mybots` → 選擇 bot → Bot Settings → Group Privacy → **Turn OFF**

關閉後須將 bot 踢出群組再重新加入才會生效。

### 2. 群組 allowlist 與 per-topic requireMention 設定

mention gating 的檢查發生在 ACP binding 路由之前。因此綁定的 bot 帳號必須對該 topic 設定 `requireMention: false`，否則訊息會在進入 ACP binding 前就被丟棄。

建議使用 per-topic 設定，而非對整個群組關閉 mention gating，避免同群組多個 bot 互相衝突：

```json
{
  "channels": {
    "telegram": {
      "groupAllowFrom": ["*"],
      "accounts": {
        "guan-yu": {
          "groups": {
            "-100xxxxxxxxxx": {
              "allowFrom": ["*"],
              "requireMention": true,
              "topics": {
                "2": { "requireMention": false }
              }
            }
          }
        },
        "klaw": {
          "groups": {
            "-100xxxxxxxxxx": {
              "allowFrom": ["*"],
              "requireMention": true,
              "topics": {
                "5": { "requireMention": false }
              }
            }
          }
        }
      }
    }
  }
}
```

如此一來，guan-yu 只在 topic:2 自動回應，klaw 只在 topic:5 自動回應，其餘 topic 均需被 @ 才會觸發。

### 3. 註冊 acpx 代理

`~/.acpx/config.json`：

```json
{
  "agents": {
    "codex": { "command": "/path/to/codex-acp" }
  }
}
```

### 4. ACP allowedAgents

```json
{
  "acp": {
    "enabled": true,
    "backend": "acpx",
    "allowedAgents": ["codex", "kiro"]
  }
}
```

## 取得 Thread ID

在 topic 中發送任意訊息，從 openclaw log 取得 threadId：

```bash
tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        msg = str(d.get('1','') or d.get('0',''))
        if 'sessionKey' in msg and 'topic' in msg:
            print(msg[:300])
    except: pass
"
```

找到類似以下的輸出：

```
sessionKey=agent:guan-yu:telegram:group:-100xxxxxxxxxx:topic:2
```

其中 `2` 即為 threadId。

## 多 Topic 多 Bot 綁定（無衝突）

同一群組可以有多個 topic 各自綁定不同 bot，只要每個 bot 僅對自己負責的 topic 設定 `requireMention: false`：

```
群組
├── topic:2  (#codex-general) → guan-yu requireMention:false → Codex ACP
├── topic:5  (#kiro-general)  → klaw    requireMention:false → Kiro ACP
└── topic:*  (其他)           → 所有 bot requireMention:true（需被 @ 才回應）
```

各 bot 的 token 獨立，Telegram 分別投遞訊息給每個 bot。每個 bot 只對自己 `requireMention: false` 的 topic 主動回應，不會互相干擾。

## 注意事項

- ACP session 預設為 persistent，同一 topic 的所有訊息共用同一 Codex/Kiro session 上下文。
- `cwd` 決定 ACP 代理讀取哪個工作區的 SOUL.md 與記憶，建議指向擁有者代理的 workspace。
- Gateway 重啟後 openclaw 會自動重新協調 ACP binding session。
- 若 hot-reload 因 secrets timeout 失敗，手動重啟：`systemctl --user restart openclaw-gateway.service`
