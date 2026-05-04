---
last_validated: 2026-05-04
validated_by: pahud
---

# Gateway 架構與生命週期（Lifecycle）

> 本文件說明 OpenClaw **Gateway** 的整體架構、生命週期狀態/轉換、重啟與更新行為、可觀測性（observability）與常見故障排除。
>
> 目標讀者：需要維運 Gateway、排查「為什麼工具/Channel/Node/cron 不動了」的人。

---

## 1. 名詞與範圍

- **Gateway**：OpenClaw 的常駐後端服務（daemon/server）。負責接收外部事件（例如 Telegram 訊息、Node 連線）、承接工具呼叫（tools）、執行排程（cron）、維護狀態與儲存。
- **CLI (`openclaw …`)**：使用者的操作入口；多數命令本質上是「呼叫 Gateway 的 API」，或在本機啟動/控制 Gateway。
- **Channel Provider / Plugin**：與外部平台整合（Telegram/Discord/WhatsApp…）的通道實作；通常以「長連線、webhook 或輪詢」的方式把事件帶入 Gateway。
- **Node**：可配對的遠端執行節點（例如另一台機器/手機），透過 WS 連線到 Gateway 接收指令並回傳結果。

> 本文件不深入每個子系統細節（例如 cron 語法、nodes 配對細節），只涵蓋它們如何被 Gateway 啟停、如何受重啟影響，以及如何觀測/排障。

---

## 2. 架構總覽

### 2.1 高層元件

下面是常見部署型態下的邏輯分層：

```
┌─────────────────────────────────────────────────────────────────────┐
│                            使用者/外部系統                           │
│  Telegram / Discord / Webhook / Browser Relay / Node / Cron trigger  │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │                               │
                │ events / requests             │ WS / HTTP
                ▼                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                              Gateway                                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Front Door（入口層）                                             │ │
│  │  - HTTP API / Webhook endpoint                                    │ │
│  │  - WebSocket server（nodes、部分即時通道）                         │ │
│  │  - Channel adapters（Telegram bot、Discord bot…）                  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Core（核心層）                                                   │ │
│  │  - Session/Agent router（把事件路由到對應 session/agent）         │ │
│  │  - Tools runtime（exec/browser/nodes/message/cron…）              │ │
│  │  - Policy/Sandbox（允許/拒絕、需要審批等）                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  State & Storage（狀態/儲存）                                     │ │
│  │  - 設定檔載入（~/.openclaw/openclaw.json 等）                      │ │
│  │  - DB / 檔案儲存（sessions、cron、paired devices…）                │ │
│  │  - Cache / locks（避免重複排程/重複執行）                           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                │
                │ tool calls / execution
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     本機/遠端執行環境（Host/Node）                     │
│  - exec（shell）  - browser（受控瀏覽器）  - nodes（遠端執行）         │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 事件流（從「外部事件」到「工具執行」）

以「Telegram 收到訊息 → 觸發 agent → 需要跑 exec」為例：

```
Telegram update
   │
   ▼
Channel adapter（Telegram provider）
   │
   ▼
Gateway router（找 session / 建立 session / 套用 policy）
   │
   ▼
Agent runtime（模型推理；產生 tool calls）
   │
   ▼
Tools runtime（exec/browser/nodes/...）
   │
   ▼
結果回寫 session state + 回覆 Telegram
```

---

## 3. 生命週期狀態與轉換

> 這裡用「狀態機」方式描述 Gateway 從啟動到停止的主要階段。實作細節會隨版本演進，但**觀測與排障**通常可以套用。

### 3.1 狀態機（ASCII）

```
            ┌──────────────┐
            │   STOPPED    │
            └──────┬───────┘
                   │ start
                   ▼
            ┌──────────────┐
            │   STARTING   │  讀 config、開 DB、註冊 routes、啟動 adapters
            └───┬─────┬────┘
                │     │
     fatal error│     │ready
                │     ▼
                │  ┌───────────┐
                │  │   READY   │  對外可服務（API/WS/channel 入口已就緒）
                │  └────┬──────┘
                │       │ run-loop
                │       ▼
                │  ┌───────────┐
                └─▶│  RUNNING  │  正常處理事件/排程/工具
                   └────┬──────┘
                        │
                        │ reload/restart
                        ▼
                   ┌───────────┐
                   │ RESTARTING│  進行 graceful shutdown + 重新載入
                   └────┬──────┘
                        │
                        ▼
                      STARTING

RUNNING/READY 也可能因部分子系統異常落入「DEGRADED」（降級）狀態：
- cron scheduler 停了
- 某 channel adapter 連不上
- nodes WS 正常但 message provider 掛了

停止流程：
RUNNING/READY ── stop ──▶ STOPPING（停止接收新事件、flush state）──▶ STOPPED
```

### 3.2 典型啟動序列（Startup sequence）

建議用「順序」理解啟動期常見故障點：

1. **讀取設定檔**：解析 `~/.openclaw/openclaw.json`（或等價來源）
2. **初始化儲存/狀態**：開啟 DB、載入 sessions/cron/paired devices 等
3. **啟動對外入口**：HTTP server / WS server / webhooks
4. **啟動 adapters**：例如 Telegram bot 連線、Webhook registration 等
5. **啟動背景工作**：cron scheduler、清理/重試、健康檢查
6. **進入 RUNNING**：開始處理事件與 tool calls

---

## 4. 重啟、更新與設定變更

### 4.1 重啟（restart）的語意

一般而言：
- `openclaw gateway restart`：期望做 **graceful restart**（盡量不破壞持久化狀態），並重新載入設定。
- `openclaw gateway stop` / `start`：更「硬」的生命週期控制（端點先停、再啟）。

> 實務上「是否無縫」取決於：是否有長連線（channel/nodes）、是否有正在執行的 cron/job、以及是否有 in-flight 的 tool call。

### 4.2 設定更新（reload config）會影響什麼

常見的設定變更可分三類：

1. **純路由/策略類**（較容易動態生效）
   - tools allow/deny、sandbox policy、model alias 等
2. **連線/adapter 類**（多半需要重建連線）
   - Telegram token、Webhook URL、provider profiles/rotation
3. **基礎設施類**（幾乎一定需要重啟）
   - Gateway bind host/port、TLS、儲存路徑/DB 位置

建議策略：
- 改完設定後，先跑 `openclaw gateway status`（或等價檢查）確認 Gateway 活著
- 如涉及 adapter/token/port，直接 `openclaw gateway restart`

### 4.3 重啟期間的行為（你應該預期的現象）

- **短暫不可用**：HTTP/WS 連線可能中斷，client 需要重連
- **長連線重建**：channel adapter/node 需要重新 handshake
- **排程恢復**：cron 若有持久化，通常會在重啟後恢復（但可能有延遲/補跑策略差異）

> 若你想把「重啟影響」降到最低：避免在大量 cron 執行中重啟；或先暫停/排空工作（若系統支援）。

---

## 5. 可觀測性（Observability）

### 5.1 你需要觀測的四件事

1. **Process 是否存活**：Gateway daemon 是否在跑、是否 crash loop
2. **入口是否可用**：HTTP port/WS 是否可連、health/status 是否正常
3. **關鍵子系統是否就緒**：channel adapters、cron scheduler、nodes service
4. **事件是否有被處理**：收到事件 → 產生 session → 有回覆/有 tool result

### 5.2 常用檢查指令（以 CLI 為主）

> 依部署方式不同（本機、systemd、docker），你可能用不同方式看 log；但 CLI 檢查通常最省時間。

```bash
openclaw gateway status
openclaw gateway run --verbose     # 前景啟動並印出詳細 log（用於快速診斷）
openclaw gateway restart
```

若你在排查特定子系統：

```bash
openclaw nodes pending
openclaw cron list
openclaw cron runs <job_id>
```

### 5.3 日誌（Logs）建議

請在回報問題/開 issue 前，先收集以下資訊（越完整越好）：

- 啟動期 log（從 STARTING 到 READY/RUNNING）
- crash stack trace（若有）
- 你正在使用的設定片段（遮蔽 token/secret）
- 觸發問題的最小重現步驟（例如「restart 後 Telegram 不回」）

> 小技巧：如果懷疑是設定錯誤，先用 `openclaw gateway run --verbose` 前景跑一次，通常會比背景服務更快看到 parse/validation 錯誤。

---

## 6. Troubleshooting Playbook（故障排除）

### 6.1 Gateway 起不來 / 一直重啟

**症狀**
- `openclaw gateway status` 顯示 stopped
- `gateway run --verbose` 一啟動就退出

**快速檢查清單**
1. 設定檔是否可解析（JSON syntax、欄位拼字）
2. 連接埠是否被佔用（port in use）
3. 權限/路徑是否正確（DB/檔案目錄不可寫）
4. 外部依賴是否可用（例如需要連到 provider/WS endpoint）

**處置**
- 先以前景跑：`openclaw gateway run --verbose`
- 修正後再 `openclaw gateway restart`

### 6.2 Telegram/Discord 收不到訊息（或收得到但不回）

**可能原因**
- token/secret 更新後未重啟 adapter
- webhook 指向錯誤 URL（或 Gateway 不可從外網存取）
- Gateway 已 RUNNING，但 channel adapter 處於 DEGRADED（斷線/限流）

**處置**
1. `openclaw gateway restart`
2. 觀察 adapter 重連 log（是否有 401/403、rate limit、TLS error）
3. 若是 webhook 模式，確認反向代理/NAT/防火牆

### 6.3 Node 連不上 / 一直顯示 pairing required

**可能原因**
- Gateway token 不一致（Node 端環境變數或 node.json 舊 token）
- 尚未 approve pairing（或 UI/通知未送達）
- WS 連線路徑/port 錯誤

**處置**
- 先確認 token 與 host/port
- 再跑：`openclaw nodes pending`
- 需要時：`openclaw nodes approve <requestId>`（依實際指令而定）

> 相關背景可參考：`docs/nodes.md`（兩層認證、paired.json 等）。

### 6.4 cron 沒跑 / 重啟後排程「看起來還在但不執行」

**可能原因**
- scheduler 沒起來（Gateway 降級）
- job 狀態卡住（例如某些版本已知的 runningAtMs/lock 未清理）
- 時區/時間漂移

**處置**
1. `openclaw cron list` / `openclaw cron runs <job_id>` 看最後一次執行
2. `openclaw gateway restart`（確保 scheduler 重建）
3. 若能穩定重現，收集 job 設定 + runs 記錄 + 啟動期 log

### 6.5 工具（exec/browser/message/nodes）突然超時

**可能原因**
- Gateway 與執行環境之間的通道卡住（WS 斷線、node 掛掉）
- policy/approval 等待使用者確認
- 外部服務（瀏覽器、provider API）卡住或被限流

**處置**
- 先確認 Gateway 是否仍 RUNNING
- 若是 node 工具：檢查 node 是否 connected
- 若是 browser：確認 browser relay/受控瀏覽器是否仍存在
- 仍不明：以 `--verbose` 重跑並擷取一次完整失敗 log

---

## 7. 建議的維運流程（SOP）

### 7.1 變更設定（config change）

1. 修改設定檔（保留上一版備份）
2. `openclaw gateway restart`
3. `openclaw gateway status` 確認狀態
4. 針對關鍵路徑做 smoke test：
   - 發一則 Telegram 訊息
   - 跑一個簡單 cron（或手動觸發）
   - `openclaw nodes pending` / 確認 node 仍可連

### 7.2 升級版本（update）

- 先看 release notes / breaking changes
- 盡量在低峰時段重啟
- 升級後保留一段時間的啟動 log（便於回溯）

---

## 8. 附錄：狀態/轉換速查表

```
事件/指令                    主要影響
────────────────────────────────────────────────────────
openclaw gateway start        啟動 Gateway（啟動序列）
openclaw gateway stop         停止入口與背景工作，結束 process
openclaw gateway restart      graceful stop + 重新載入設定 + 重建連線
openclaw gateway run --verbose前景跑，適合診斷啟動期錯誤

重啟後你最該確認：
- channel adapter 是否重新連上
- nodes 是否能重新連線
- cron 是否有繼續跑
```

---

## 更新紀錄

- **2026-02-18**：初版，新增架構總覽、狀態機、重啟/更新語意、observability 與 troubleshooting。
