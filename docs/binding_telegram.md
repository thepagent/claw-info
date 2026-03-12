# Telegram Binding 指南

openclaw 的 `bindings` 設定支援兩種 Telegram 綁定模式：

| 模式 | 說明 | `match` 欄位 |
|---|---|---|
| **DM Binding** | 將特定 bot 帳號的私訊（DM）路由到指定 agent | 僅含 `channel` + `accountId`，無 `peer` |
| **Thread/Topic Binding** | 將群組中特定 Topic 的訊息路由到指定 agent | 含 `peer.kind: "group"` + `peer.id: "<groupId>:topic:<threadId>"` |

---

## DM Binding

DM Binding 將某個 Telegram bot 帳號收到的所有私訊，路由到指定的 agent。

### 設定範例

```json
{
  "bindings": [
    {
      "agentId": "main",
      "match": {
        "channel": "telegram",
        "accountId": "kong-ming"
      }
    }
  ]
}
```

- `accountId`：對應的 Telegram bot 帳號 ID（在 `channels.telegram.accounts` 中定義）
- 無 `peer` 欄位：匹配該帳號下所有私訊
- 路由優先順序：`binding.peer` > `binding.account`，即若同一帳號同時有 DM binding 與 Topic binding，Topic binding 優先

> **注意：binding 與 agent runtime 是正交的。**
> `bindings` 決定「哪些訊息路由給哪個 `agentId`」，而該 agent 是本地 LLM 還是外部 ACP，取決於 `agents[].runtime.type`。
> DM Binding 同樣可以路由到 `type: "acp"` 的 agent，並非只有 Topic Binding 才能接 ACP。
>
> ```
> binding (match 條件)  ──▶  agentId  ──▶  runtime.type
>                                          ├─ local  → 本地 LLM
>                                          └─ acp    → 外部 ACP agent (Codex / Kiro / Gemini)
> ```

### 什麼時候不需要 DM Binding？

若只有一個 agent 對應一個 Telegram 帳號，**binding 可以省略**。OpenClaw 路由找不到匹配的 binding 時，會自動 fallback 到 `defaultAgent`：

```
無 binding 命中 ──▶ resolveDefaultAgentId(cfg) ──▶ 預設 agent 處理
```

需要明確設定 binding 的情況：

| 情境 | 需要 binding？ |
|---|---|
| 單一帳號、單一 agent，純路由 | ❌ default fallback 即可 |
| 多個 TG 帳號各自對應不同 agent | ✅ |
| 同帳號下不同 topic 路由不同 agent | ✅ |
| 需指定 ACP `cwd` / `mode` 等參數 | ✅（`type: "acp"` binding 才能攜帶這些） |

---

## Thread/Topic Binding

## 什麼是 Thread/Topic ACP Binding？

Telegram 論壇群組（Forum Group）支援將對話分成多個獨立的 **Topic（討論串）**，每個 Topic 有自己的 `message_thread_id`。

**Thread/Topic ACP Binding** 是 openclaw 的一項功能，允許將特定 Topic 的所有訊息直接路由到外部 ACP 代理（如 Codex CLI、Kiro），完全繞過本地 LLM，由外部代理負責回覆。

## 使用情境

- **專屬 AI 頻道**：在群組中開一個 `#codex-general` topic，所有訊息自動由 Codex 回應，無需每次 @bot
- **多 AI 共存**：不同 topic 綁定不同 AI（`#codex-general` → Codex、`#kiro-general` → Kiro），各司其職互不干擾
- **角色扮演 / 專屬助理**：搭配 `SOUL.md` 讓 ACP 代理在特定 topic 中維持固定人格與長期記憶

## 為什麼重要？

- **無需 @mention**：綁定後使用者直接在 topic 中發訊息即可，體驗更自然
- **不觸發本地 LLM**：訊息直接轉發至外部 ACP session，節省本地資源
- **Topic = ACP Session**：每個 topic 永久對應一個獨立的 ACP session，多個 topic 即可同時管理多個 ACP session，彼此上下文完全隔離
- **精確隔離**：`requireMention` 可精確到 topic 層級，避免多 bot 在同群組互相搶答

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

## Kiro ACP 綁定範例

以下示範將 `#kiro-general`（topic:72）綁定到 Kiro CLI ACP。

### acpx 設定

`~/.acpx/config.json`：

```json
{
  "agents": {
    "codex": { "command": "/path/to/codex-acp" },
    "kiro":  { "command": "/path/to/kiro-cli-chat acp" }
  }
}
```

> 注意：Kiro 使用 `kiro-cli-chat acp` 作為 ACP 入口，不需要額外的 daemon 或 adapter。

### openclaw.json 設定

```json
{
  "agents": {
    "list": [
      {
        "id": "klaw",
        "runtime": {
          "type": "acp",
          "acp": { "agent": "kiro" }
        }
      }
    ]
  },
  "bindings": [
    {
      "type": "acp",
      "agentId": "klaw",
      "match": {
        "channel": "telegram",
        "accountId": "klaw",
        "peer": { "kind": "group", "id": "-100xxxxxxxxxx:topic:72" }
      },
      "acp": {
        "mode": "persistent",
        "cwd": "~/.openclaw/workspace-klaw"
      }
    }
  ]
}
```

### per-topic requireMention

```json
{
  "channels": {
    "telegram": {
      "accounts": {
        "klaw": {
          "groups": {
            "-100xxxxxxxxxx": {
              "requireMention": true,
              "topics": {
                "72": { "requireMention": false }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Gemini ACP 綁定範例

以下示範將 `#gemini`（topic:101）綁定到 Gemini CLI ACP。

### acpx 設定

`~/.acpx/config.json`：

```json
{
  "agents": {
    "gemini": { "command": "/path/to/gemini --experimental-acp" }
  }
}
```

> 注意：Gemini CLI 使用 `--experimental-acp` flag 啟動 ACP 模式。

### openclaw.json 設定

```json
{
  "acp": {
    "allowedAgents": ["codex", "kiro", "gemini"]
  },
  "agents": {
    "list": [
      {
        "id": "gemini-saga",
        "runtime": {
          "type": "acp",
          "acp": { "agent": "gemini" }
        }
      }
    ]
  },
  "bindings": [
    {
      "type": "acp",
      "agentId": "gemini-saga",
      "match": {
        "channel": "telegram",
        "accountId": "gemini-saga",
        "peer": { "kind": "group", "id": "-100xxxxxxxxxx:topic:101" }
      },
      "acp": {
        "mode": "persistent",
        "cwd": "~/.openclaw/workspace-gemini-saga"
      }
    }
  ]
}
```

> 注意：新增 ACP agent 時，務必將其加入 `acp.allowedAgents`，否則會收到 `ACP_SESSION_INIT_FAILED: ACP agent is not allowed by policy` 錯誤。

### per-topic requireMention

```json
{
  "channels": {
    "telegram": {
      "accounts": {
        "gemini-saga": {
          "groups": {
            "-100xxxxxxxxxx": {
              "requireMention": false,
              "topics": {
                "101": { "requireMention": false }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 常見問題（FAQ）

**Q：我已經在 openclaw 設定了 OpenAI LLM，為什麼還需要 Codex ACP？**

兩者解決的是不同層次的問題：

| | openclaw 內建 LLM（含 OpenAI） | Codex ACP |
|---|---|---|
| 執行位置 | openclaw 程序內 | 獨立外部程序 |
| 工具使用 | 依 openclaw 插件 | Codex 原生（讀寫檔案、執行 shell） |
| Session 狀態 | 依 openclaw 記憶設定 | Codex 自身的 persistent session |
| 模型設定 | openclaw config | Codex CLI 自身設定 |

簡單說：openclaw 內建 LLM 負責「對話」，Codex ACP 負責「代理執行任務」。  
如果你希望在 Telegram topic 中讓 Codex **直接操作檔案、執行指令、完成多步驟任務**，就需要 ACP binding，而不是讓 openclaw 的 LLM 代為轉發。

**Q：ACP binding 和 hook relay 有什麼差別？**

- **Hook relay**：訊息先進入 openclaw LLM，再由 hook 腳本轉發給外部代理，會觸發本地 LLM 一次
- **ACP binding**：訊息直接路由到 ACP session，完全跳過本地 LLM，延遲更低、不消耗本地模型資源
