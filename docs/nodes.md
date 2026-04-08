---
last_validated: 2026-04-09
validated_by: masami-agent
---

# OpenClaw Nodes 深度解析

## 概述

OpenClaw Nodes 是一個分散式設備協作系統，允許 AI Agent 透過 Gateway WebSocket 協議控制遠端設備（macOS/iOS/Android/Headless Linux），執行本地操作如相機拍照、螢幕錄製、系統指令等。

首次引入版本： 2026.1.x

## 解決的問題

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        沒有 Nodes 的限制                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User: "幫我拍張照片"                                                      │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────┐    ┌─────────────────────────────────────────────────┐   │
│   │   Gateway   │───▶│  ❌ Gateway 在 Linux VPS，沒有相機              │   │
│   │  (Linux)    │    └─────────────────────────────────────────────────┘   │
│                                       │                                     │
│                                       ▼                                     │
│                              💥 無法執行設備操作                            │
│                                                                             │
│   限制來源：                                                                │
│   • Gateway 可能在無頭伺服器 - 沒有相機/螢幕/麥克風                        │
│   • 跨設備操作 - Agent 需要控制手機拍照、Mac 執行指令                      │
│   • 權限隔離 - 不同設備有不同的 TCC 權限                                   │
│   • 地理分散 - Gateway 在雲端，設備在本地                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 架構

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenClaw Nodes 架構                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐                                                           │
│   │   Agent     │                                                           │
│   │  (Gateway)  │                                                           │
│   └──────┬──────┘                                                           │
│          │ nodes tool call                                                  │
│          ▼                                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                    Gateway WebSocket Server                       │      │
│   │                    ws://127.0.0.1:18789                           │      │
│   │  • node.list      → 列出已配對節點                               │      │
│   │  • node.describe  → 查詢節點能力                                 │      │
│   │  • node.invoke    → 遠端執行指令                                 │      │
│   │  • node.pair.*    → 配對管理                                     │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│          │                                                                  │
│          │ WebSocket (role: "node")                                         │
│          ▼                                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                    Node Devices                                   │      │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │      │
│   │  │  macOS App │  │  iOS App   │  │ Android App│                  │      │
│   │  │            │  │            │  │            │                  │      │
│   │  │ • canvas   │  │ • canvas   │  │ • canvas   │                  │      │
│   │  │ • camera   │  │ • camera   │  │ • camera   │                  │      │
│   │  │ • screen   │  │ • screen   │  │ • screen   │                  │      │
│   │  │ • system   │  │ • location │  │ • sms      │                  │      │
│   │  │ • location │  │            │  │ • location │                  │      │
│   │  └────────────┘  └────────────┘  └────────────┘                  │      │
│   │                                                                   │      │
│   │  ┌────────────────────────────────────────────────────────────┐  │      │
│   │  │  Headless Node Host (Linux/Windows/macOS)                  │  │      │
│   │  │  • system.run    → 執行 shell 指令                         │  │      │
│   │  │  • system.which  → 查詢指令路徑                            │  │      │
│   │  │  • system.execApprovals.get/set → 權限管理                 │  │      │
│   │  └────────────────────────────────────────────────────────────┘  │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 執行位置分離

```
────────────┬───────────────────────────────────┬──────────────────────────────────────
執行位置    │說明                               │範例
────────────┼───────────────────────────────────┼──────────────────────────────────────
Gateway Host│接收訊息、執行 LLM、路由 tool calls│exec (預設)、browser
────────────┼───────────────────────────────────┼──────────────────────────────────────
Node Host   │執行設備本地操作                   │system.run、camera.snap、screen.record
────────────┴───────────────────────────────────┴──────────────────────────────────────
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         執行流程                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User: "用我的 iPhone 拍張照片"                                            │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  1. Gateway 收到訊息，LLM 決定呼叫 nodes tool                   │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  2. nodes tool 解析 action=camera_snap, node="iPhone"           │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  3. Gateway 透過 WS 發送 node.invoke → camera.snap              │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  4. iPhone App 執行拍照，回傳 base64 圖片                       │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  5. Gateway 收到結果，寫入暫存檔，回傳 MEDIA:<path>             │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Node 能力對照表

```
─────────────┬─────────┬───────┬───────────┬─────────────
能力         │macOS App│iOS App│Android App│Headless Host
─────────────┼─────────┼───────┼───────────┼─────────────
canvas.*     │✅       │✅     │✅         │❌
─────────────┼─────────┼───────┼───────────┼─────────────
camera.snap  │✅       │✅     │✅         │❌
─────────────┼─────────┼───────┼───────────┼─────────────
camera.clip  │✅       │✅     │✅         │❌
─────────────┼─────────┼───────┼───────────┼─────────────
screen.record│✅       │✅     │✅         │❌
─────────────┼─────────┼───────┼───────────┼─────────────
location.get │✅       │✅     │✅         │❌
─────────────┼─────────┼───────┼───────────┼─────────────
system.run   │✅       │❌     │❌         │✅
─────────────┼─────────┼───────┼───────────┼─────────────
system.notify│✅       │❌     │❌         │❌
─────────────┼─────────┼───────┼───────────┼─────────────
sms.send     │❌       │❌     │✅         │❌
─────────────┴─────────┴───────┴───────────┴─────────────
```

## Node 認證機制

OpenClaw Nodes 採用 Ed25519 公鑰密碼學進行設備認證，配合 Gateway Token 作為傳輸層認證。

### 認證流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Ed25519 Challenge-Response                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐                              ┌─────────────┐              │
│   │    Node     │                              │   Gateway   │              │
│   └──────┬──────┘                              └──────┬──────┘              │
│          │                                            │                     │
│          │  1. WS Connect + publicKey                 │                     │
│          │  (role: "node", clientMode: "node")        │                     │
│          │───────────────────────────────────────────▶│                     │
│          │                                            │                     │
│          │  2. Challenge (random nonce)               │                     │
│          │◀───────────────────────────────────────────│                     │
│          │                                            │                     │
│          │  3. Signature = Ed25519.sign(nonce, privKey)                     │
│          │───────────────────────────────────────────▶│                     │
│          │                                            │                     │
│          │  4. Gateway 驗證:                          │                     │
│          │     Ed25519.verify(nonce, signature, pubKey)                     │
│          │                                            │                     │
│          │  5a. 已配對 → Connected ✓                  │                     │
│          │  5b. 未配對 → 1008 "pairing required"      │                     │
│          │◀───────────────────────────────────────────│                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 兩層認證

```
──────┬─────────────┬────────────────────────────
層級  │機制         │用途
──────┼─────────────┼────────────────────────────
傳輸層│Gateway Token│驗證 WS 連線有權存取 Gateway
──────┼─────────────┼────────────────────────────
設備層│Ed25519 公鑰 │驗證設備身份，防止冒充
──────┴─────────────┴────────────────────────────
```

### 金鑰儲存位置

Node 端 (私鑰):

```
~/.openclaw/node.json
```

```json
{
  "nodeId": "60c3e1e0...",
  "privateKey": "base64...",
  "publicKey": "base64...",
  "displayName": "My Mac",
  "gateway": { "host": "...", "port": 18789 }
}
```

Gateway 端 (已配對設備):

```
~/.openclaw/devices/paired.json
```

```json
{
  "60c3e1e0...": {
    "publicKey": "base64...",
    "displayName": "My Mac",
    "roles": ["node"],
    "pairedAt": "2026-02-15T..."
  }
}
```

### Gateway Token 認證

Node 連線時需提供 Gateway Token：

```sh
# 環境變數
export OPENCLAW_GATEWAY_TOKEN="<token>"
openclaw node run --host <gateway-ip> --port 18789

# 或在 node.json 中
```

```json
{
  "gateway": {
    "token": "<token>"
  }
}
```

Token 來源為 Gateway 設定：

```json
// ~/.openclaw/openclaw.json (Gateway 端)
{
  "gateway": {
    "auth": {
      "mode": "token",
      "token": "<token>"
    }
  }
}
```

### 本地自動信任

若 Node 從 127.0.0.1 連線，Gateway 會自動批准配對（silent: true），無需手動 approve。

### 安全特性

* **私鑰永不離開設備** — 只傳輸公鑰
* **每次連線重新驗證** — Challenge 為隨機 nonce
* **配對可撤銷** — `openclaw devices revoke`
* **Token 可輪換** — 修改 Gateway config 後重啟

## 配對流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Node 配對流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐          │
│   │   Node App  │         │   Gateway   │         │    User     │          │
│   └──────┬──────┘         └──────┬──────┘         └──────┬──────┘          │
│          │                       │                       │                  │
│          │  1. WS connect        │                       │                  │
│          │  (role: "node")       │                       │                  │
│          │──────────────────────▶│                       │                  │
│          │                       │                       │                  │
│          │  2. Ed25519 pubkey    │                       │                  │
│          │  challenge-response   │                       │                  │
│          │◀─────────────────────▶│                       │                  │
│          │                       │                       │                  │
│          │  3. 1008 "pairing     │                       │                  │
│          │     required"         │                       │                  │
│          │◀──────────────────────│                       │                  │
│          │                       │                       │                  │
│          │                       │  4. openclaw nodes    │                  │
│          │                       │     pending           │                  │
│          │                       │◀──────────────────────│                  │
│          │                       │                       │                  │
│          │                       │  5. openclaw nodes    │                  │
│          │                       │     approve <id>      │                  │
│          │                       │◀──────────────────────│                  │
│          │                       │                       │                  │
│          │  6. WS reconnect      │                       │                  │
│          │  (paired)             │                       │                  │
│          │──────────────────────▶│                       │                  │
│          │                       │                       │                  │
│          │  7. Connected ✓       │                       │                  │
│          │◀──────────────────────│                       │                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. macOS/iOS/Android App 配對

```sh
# 在 Gateway 端查看待配對請求
openclaw nodes pending

# 批准配對
openclaw nodes approve <requestId>

# 確認狀態
openclaw nodes status
```

App 端會自動透過 Bonjour/mDNS 發現 Gateway，或手動輸入 Gateway URL。

### 2. Headless Node Host 配對（Linux/Windows）

```sh
# 在 Node 機器上啟動 node host
openclaw node run --host <gateway-ip> --port 18789 --display-name "Build Server"

# 或安裝為服務
openclaw node install --host <gateway-ip> --port 18789 --display-name "Build Server"
openclaw node restart
```

然後在 Gateway 端批准：

```sh
openclaw nodes pending
openclaw nodes approve <requestId>
```

### 3. 透過 SSH Tunnel 配對（Gateway 綁定 loopback）

若 Gateway 只綁定 127.0.0.1：

```sh
# Terminal A: 建立 SSH tunnel
ssh -N -L 18790:127.0.0.1:18789 user@gateway-host

# Terminal B: 連接 node
export OPENCLAW_GATEWAY_TOKEN="<gateway-token>"
openclaw node run --host 127.0.0.1 --port 18790 --display-name "Remote Node"
```

### 4. 遠端模式配對（onboard wizard）

```sh
openclaw onboard --mode remote \
  --remote-url "ws://<gateway-ip>:18789" \
  --remote-token "<token>"
```

### 配對狀態查詢

```sh
openclaw nodes status

# Known: 2 · Paired: 2 · Connected: 1
# ┌──────────────┬────────────┬──────────────────────┐
# │ Node         │ IP         │ Status               │
# ├──────────────┼────────────┼──────────────────────┤
# │ iPhone       │ 192.168.1.5│ paired · connected   │
# │ Build Server │ 10.0.0.100 │ paired · disconnected│
# └──────────────┴────────────┴──────────────────────┘
```

### 常見問題

若 `nodes pending` 為空但 Node 連不上，可能是 device-pairing 與 node-pairing 兩套系統不同步（[#6836](https://github.com/openclaw/openclaw/issues/6836)）。此時需檢查 `~/.openclaw/devices/pending.json`。

## CLI 指令

```bash
# 查看節點狀態
openclaw nodes status

# 查看待配對請求
openclaw nodes pending

# 批准配對
openclaw nodes approve <id>

# 查看節點詳情
openclaw nodes describe --node <name>

# 拍照
openclaw nodes camera snap --node <name> --facing front

# 螢幕錄製
openclaw nodes screen record --node <name> --duration 10s

# 執行指令 (需要 system.run 能力)
openclaw nodes run --node <name> -- echo "Hello"

# 發送通知 (macOS only)
openclaw nodes notify --node <name> --title "Ping" --body "Ready"

# 取得位置
openclaw nodes location get --node <name>
```

## 設定範例

```json
{
  "tools": {
    "exec": {
      "host": "node",
      "security": "allowlist",
      "node": "my-mac-mini"
    }
  },
  "gateway": {
    "nodes": {
      "allowCommands": ["camera.snap", "camera.clip", "screen.record"],
      "denyCommands": ["sms.send"]
    }
  }
}
```

## 核心問題與解法

```
──────────┬─────────────────────────────┬────────────────────────────────
問題      │說明                         │Nodes 解法
──────────┼─────────────────────────────┼────────────────────────────────
無頭伺服器│Gateway 在 VPS，沒有相機/螢幕│透過 Node 執行設備操作
──────────┼─────────────────────────────┼────────────────────────────────
跨設備控制│需要控制多台設備             │多 Node 配對 + 路由
──────────┼─────────────────────────────┼────────────────────────────────
權限隔離  │不同設備有不同權限           │每個 Node 獨立權限管理
──────────┼─────────────────────────────┼────────────────────────────────
地理分散  │Gateway 在雲端，設備在本地   │WS 長連接 + Tailscale/SSH tunnel
──────────┼─────────────────────────────┼────────────────────────────────
安全執行  │防止惡意指令                 │exec-approvals allowlist
──────────┴─────────────────────────────┴────────────────────────────────
```

> **Nodes = 讓 Gateway 的手伸到你的設備上，遠端執行本地操作。**

## 當前狀態（2026.2.15）

### 最新版本更新

```
─────────┬─────────────────────────────────────────
版本     │重點更新
─────────┼─────────────────────────────────────────
2026.2.14│Node pairing 改進、exec approval 流程優化
─────────┼─────────────────────────────────────────
2026.2.13│gateway.nodes.denyCommands 設定、安全強化
─────────┼─────────────────────────────────────────
2026.2.12│Headless node host 支援、SSH tunnel 文件
─────────┴─────────────────────────────────────────
```

### 已知問題（Open Issues）

#### 🔴 Critical

| Issue | 標題 | 說明 |
|-------|------|------|
| [#17322](https://github.com/openclaw/openclaw/issues/17322) | nodes run / system.run hangs on headless gateway | Headless Linux 上 exec approval 流程卡住 |

#### 🟠 Bugs

| Issue | 標題 | 說明 |
|-------|------|------|
| [#17443](https://github.com/openclaw/openclaw/issues/17443) | Node pairing request invisible to gateway | nodes pending 永遠為空 |
| [#17356](https://github.com/openclaw/openclaw/issues/17356) | node.invoke intermittent 30s timeout | 間歇性 30 秒超時 |
| [#8465](https://github.com/openclaw/openclaw/issues/8465) | nodes screen_record fails on macOS 15.1.1 | macOS 螢幕錄製失敗 |
| [#8463](https://github.com/openclaw/openclaw/issues/8463) | nodes run returns timeout even when command completes | 指令完成但回傳超時 |
| [#6836](https://github.com/openclaw/openclaw/issues/6836) | device-pairing and node-pairing stores disconnected | 兩套配對系統不同步 |
| [#16508](https://github.com/openclaw/openclaw/issues/16508) | denyCommands silently ineffective | 指令名稱不匹配導致 deny 無效 |

#### 🟢 Feature Requests

| Issue | 標題 | 說明 |
|-------|------|------|
| [#12429](https://github.com/openclaw/openclaw/issues/12429) | K8s Service Account Trust for worker nodes | K8s 自動配對 worker nodes |

## 參考資料

* [OpenClaw Nodes Docs](https://docs.openclaw.ai/nodes)
* [Node Troubleshooting](https://docs.openclaw.ai/nodes/troubleshooting)
* [Exec Approvals](https://docs.openclaw.ai/tools/exec-approvals)
* [Original Gist](https://gist.github.com/pahud/879f6fc07a1e4e086af0f51eae8a4b7f)
