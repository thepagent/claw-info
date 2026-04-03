# Node Delegation Architecture

OpenClaw Gateway 作為控制平面，將 ACP 任務派發到遠端的 OpenClaw Node，由 Node 在本機執行 coding CLI（Claude Code、Kiro CLI 等）。

## Architecture

```
                    ┌──────────────────────────────────────┐
                    │ User (Telegram/Discord/...)           │
                    │ "Help me modify the code"             │
                    └──────────────────┬───────────────────┘
                                       │
                                       ▼
┌── OpenClaw Gateway (Control Plane) ──────────────────────────────────────┐
│ Deploy on: remote host, Amazon EKS, or any single-node K8s cluster       │
│                                                                          │
│  ┌── OpenClaw Official ───────────────────────────────────────────────┐  │
│  │ Agent, Channel Integration, Session Mgmt, Dashboard                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌── Custom Extensions ──────────────────────────────────────────────┐   │
│  │ gateway ext  - route ACP events to remote Nodes                   │   │
│  │ remote-acpx  - ACP tools for Agent (session/new, prompt, events)  │   │
│  │ ACP skill    - teach Agent to manage remote coding CLI sessions   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌── Custom Extensions ──────────────────────────────────────────────┐   │
│  │ Node Host ext - ACP event WebSocket relay                         │   │
│  └────────────────────┬─────────────────────────┬────────────────────┘   │
│                       │                         │                        │
└───────────────────────┼─────────────────────────┼────────────────────────┘
                        │ WebSocket               │ WebSocket
                        ▼ (outbound)              ▼ (outbound)
┌── Node A (Mac Mini) ──────────────┐  ┌── Node B (Mini PC) ───────────────┐
│                                    │  │                                    │
│  ┌ Official ────────────────────┐  │  │  ┌ Official ────────────────────┐  │
│  │ Node connection mgmt         │  │  │  │ Node connection mgmt         │  │
│  └──────────────────────────────┘  │  │  └──────────────────────────────┘  │
│                                    │  │                                    │
│  ┌ Custom ──────────────────────┐  │  │  ┌ Custom ──────────────────────┐  │
│  │ remote-acpx plugin-sdk       │  │  │  │ remote-acpx plugin-sdk       │  │
│  │ (ACP event send/recv)        │  │  │  │ (ACP event send/recv)        │  │
│  └──────────────────────────────┘  │  │  └──────────────────────────────┘  │
│                                    │  │                                    │
│  ┌ Claude Code ─────────────────┐  │  │  ┌ Kiro CLI ────────────────────┐  │
│  │ ~/repo/aws-cdk               │  │  │  │ ~/repo/project               │  │
│  │ stdin/stdout ACP             │  │  │  │ stdin/stdout ACP             │  │
│  └──────────────────────────────┘  │  │  └──────────────────────────────┘  │
│                                    │  │                                    │
└────────────────────────────────────┘  └────────────────────────────────────┘

Legend: "Official" = OpenClaw built-in    "Custom" = must be developed
```

## 優勢

- **不需要開 port** — Node 主動往外連 Gateway，家裡的路由器不需要任何設定
- **Agent 當 PM** — 使用者只需要說高階目標，🦞 自動拆解任務、派工、監控、回報，不需要手動操作 coding CLI
- **多 Node 支援** — 可以同時連接多台機器，不同 Node 跑不同的 coding CLI 或專案
- **程式碼留在本機** — coding CLI 在 Node 本機執行，原始碼不需要上傳到雲端
- **隨時隨地操作** — 透過 Telegram/Discord 等手機 app 就能指揮遠端機器上的 coding CLI 工作
- **斷線自動重連** — Node 的 WebSocket 連線斷開後會自動重新連線

## K8s 類比

| Kubernetes | OpenClaw |
|---|---|
| API Server (控制平面) | Gateway (遠端主機 / EKS / K3s) |
| kubelet (工作節點) | Node (Mac Mini / Mini PC / VM) |
| Scheduler | Agent 🦞 |
| Pod | ACP Session (CC / Kiro) |

## 部署範例

- **Gateway**: Amazon EKS、GKE、K3s 單節點叢集、或任何有公開端點的遠端主機
- **Node**: 家中 Mac Mini、辦公室 Mini PC、雲端 VM — 任何能跑 coding CLI 的機器

## Node 上線步驟

### 1. 安裝 OpenClaw

```bash
npm install -g openclaw@latest
```

### 2. 設定連線到遠端 Gateway

編輯 `~/.openclaw/openclaw.json`：

```json
{
  "gateway": {
    "remote": {
      "url": "wss://your-gateway.example.com",
      "token": "YOUR_GATEWAY_TOKEN"
    }
  }
}
```

`token` 必須與 Gateway 端的 `OPENCLAW_GATEWAY_TOKEN` 一致。

### 3. 啟動 Node

```bash
# 前景執行
openclaw node

# 或安裝為系統服務（開機自動啟動）
openclaw onboard --install-daemon
```

### 4. 確認連線

在 Gateway 的 Dashboard 或 log 中確認 Node 已連線，然後透過 Telegram/Discord 發送訊息測試：

```
幫我改程式碼
```

Agent 🦞 會自動在已連線的 Node 上啟動 coding CLI 開始工作。

## 需要的自訂元件

OpenClaw 官方的 `acpx` plugin 只支援**本機執行** — 在同一台機器上 spawn coding CLI。要實現跨機器的遠端派工，需要以下自訂擴充：

| 元件 | OpenClaw 官方 | 自訂擴充 |
|---|---|---|
| `acpx plugin-sdk` | ✅ 有（僅限本機） | 仿造做了 `remote-acpx plugin-sdk` |
| `node-host` | ✅ 有 | 擴充加入 ACP 事件轉發 |
| `gateway` | ✅ 有 | 擴充加入 ACP 事件路由到遠端 Node |
| `remote-acpx plugin` | ❌ 官方無此功能 | 全新實作，給 Agent 用的 ACP tool |
| `ACP skill` | ❌ 官方無此功能 | 全新實作，教 Agent 管理遠端 session |

具體來說：

1. **`remote-acpx plugin-sdk`** — 仿造官方 `acpx plugin-sdk`，定義遠端 ACP 事件的介面和型別
2. **`node-host` 擴充** — 在現有 node-host 上加入 ACP 事件的 WebSocket 轉發能力
3. **`gateway` 擴充** — 讓 Gateway 能將 ACP 事件路由到正確的遠端 Node
4. **`remote-acpx plugin`** — 全新的 plugin，提供 tool 讓 Agent 能 emit/receive ACP 事件（session/new、session/prompt 等）
5. **`ACP skill`** — 全新的 skill，教 Agent 如何使用上述 tool 來管理遠端 coding CLI session
