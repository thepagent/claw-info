# ACPX Harness

## ACPX Harness 是什麼

ACPX（ACP eXternal）Harness 是 OpenClaw ACP（Agent Communication Protocol）的**外部執行後端橋接層**。它讓 OpenClaw gateway 能夠將 agent 任務**委派給外部 AI CLI 工具**執行，而非使用 OpenClaw 自身的內建 LLM runtime。

---

## 它解決了什麼痛點

### 問題背景

OpenClaw 本身是一個 AI agent 平台，內建自己的 LLM runtime（呼叫 OpenAI、Anthropic 等 API）。但社群有強烈需求：

| 痛點 | 說明 |
|------|------|
| **工具生態割裂** | Claude Code、Codex CLI、Gemini CLI 各有獨立的工具呼叫能力、MCP 整合、permission model，無法在 OpenClaw 內直接使用 |
| **認證管理複雜** | 各 CLI 有自己的 OAuth / API key 管理，重複在 OpenClaw 實作成本高且易出錯 |
| **session 狀態不一致** | 外部 CLI 維護自己的對話歷史與 context window，強行整合會造成狀態不同步 |
| **能力上限不同** | Claude Code 有 computer use、file edit 等原生能力，OpenClaw 內建 runtime 無法完整複製 |

### ACPX 的解法

> 不重造輪子，直接橋接外部 CLI。

ACPX 透過標準化的 JSON-RPC over stdin/stdout 協議，讓 OpenClaw 像「指揮官」一樣派發任務給外部 CLI，由外部 CLI 負責實際執行與 AI 呼叫，結果再回傳至 OpenClaw session。

---

## 為何不可或缺

1. **多模型協作**：同一個 OpenClaw workflow 可同時調度 Claude、Codex、Gemini 等不同模型，各司其職
2. **保留原生能力**：外部 CLI 的 tool use、MCP、permission model 完整保留，不受 OpenClaw 限制
3. **認證解耦**：OpenClaw 不需持有各 AI 廠商的 API key，由外部 CLI 自行管理
4. **靜默 fallback 風險**：若 acpx 缺失，OpenClaw 會靜默降級至內建 runtime——使用者以為在用 Claude，實際上是 OpenClaw 自己在回答（這是 v2026.3.22 打包災難最嚴重的影響）

---

## 運作原理

```
┌─────────────────────────────────────────────────────────────────┐
│                  ACP Harness 運作原理                           │
└─────────────────────────────────────────────────────────────────┘

  使用者發送訊息
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway                           │
│                                                               │
│   session 設定 runtime: "acp", agent: "claude"               │
│                                                               │
│   ┌─────────────────────────────────────────────────────┐    │
│   │                  ACPX Harness                        │    │
│   │                                                      │    │
│   │  1. spawn  claude --experimental-acp                 │    │
│   │  2. 透過 stdin 送出 JSON-RPC 請求                    │    │
│   │  3. 從 stdout 讀取 JSON-RPC 回應                     │    │
│   │  4. 串流 token 回傳至 OpenClaw session               │    │
│   └──────────────────────┬───────────────────────────────┘    │
│                          │ stdin/stdout pipe                   │
└──────────────────────────│────────────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  外部 CLI 進程  │
                  │                 │
                  │  e.g. claude    │
                  │       codex     │
                  │       gemini    │
                  │       kiro      │
                  └────────┬────────┘
                           │
                           ▼
                    實際 AI 模型 API
                  (Anthropic / OpenAI
                   / Google / Amazon)
```

支援的內建 harness：

| Agent ID | 對應外部 CLI | 廠商 |
|----------|-------------|------|
| `claude` | Claude Code CLI | Anthropic |
| `codex` | OpenAI Codex CLI | OpenAI |
| `gemini` | Gemini CLI | Google |
| `kiro` | Kiro CLI | Amazon |
| `cursor` | Cursor CLI | Cursor |

---

## 演進史

**2026-02-27 — 誕生**
- PR [#23580](https://github.com/openclaw/openclaw/pull/23580)：ACP 執行緒代理成為一等公民，`acpx backend bridging` 首次引入

**2026-03-01 — 初步穩定**
- PR [#30036](https://github.com/openclaw/openclaw/pull/30036)：pin ACPX 至 `0.1.15`，加入 command/version probing

**2026-03-02~04 — 早期 bug 爆發**
- [#31686](https://github.com/openclaw/openclaw/issues/31686)：Claude ACP session 失敗
- [#32967](https://github.com/openclaw/openclaw/issues/32967)：`@openclaw/acpx` npm 404，scoped package 未發布
- [#33514](https://github.com/openclaw/openclaw/issues/33514)：Windows `resolveWindowsSpawnProgramCandidate` 不存在
- [#33843](https://github.com/openclaw/openclaw/issues/33843)：`sessions_spawn` CLI 語法錯誤

**2026-03-08~13 — 快速迭代修復**
- 修 Gemini `--experimental-acp` flag
- 修 Codex OAuth auth / env key 洩漏
- 修 JSON-RPC done/error 事件解析
- 版本 pin 從 `0.1.15` → `0.1.16` → `0.2.0`

**2026-03-15 — 擴展支援**
- PR [#47575](https://github.com/openclaw/openclaw/pull/47575)：新增 **Kiro CLI** 為內建 ACP agent
- PR [#48174](https://github.com/openclaw/openclaw/pull/48174)：新增 **Cursor CLI** 為內建 ACP agent

**2026-03-17~21 — 持續修復**
- Codex `--cd` flag、process group orphan、permission flags 轉發
- 版本 pin 升至 `0.3.0`

**2026-03-22~23 — v2026.3.22 打包災難**
- `dist/extensions/acpx/` 未打包進 npm
- 所有外部 harness（claude/codex/gemini/kiro/cursor）靜默 fallback 至內建 runtime
- PR [#52846](https://github.com/openclaw/openclaw/pull/52846)：緊急修復，保留 whatsapp 與 acpx bundled

---

## v2026.3.22 升級後啟動失敗：診斷與修復

> **適用範圍**：曾透過外部 extension 路徑安裝 acpx（即 `plugins.load.paths` 或 `plugins.installs` 中含有 `/extensions/acpx` 路徑）的使用者。若是全新安裝 v2026.3.22 則不受影響。

升級至 v2026.3.22 後，執行 `openclaw update` 完成後立刻使用 `openclaw status`，部分使用者會遇到 gateway 完全無法啟動的問題。

### 症狀

執行任何 `openclaw` 指令均出現：

```
Config invalid
File: ~/.openclaw/openclaw.json
Problem:
 - plugins.load.paths: plugin: plugin path not found:
   /usr/lib/node_modules/openclaw/extensions/acpx

Run: openclaw doctor --fix
```

完整 stack trace：

```
[openclaw] Failed to start CLI: Error: Invalid config at /root/.openclaw/openclaw.json:
- plugins.load.paths: plugin: plugin path not found:
  /usr/lib/node_modules/openclaw/extensions/acpx
    at Object.loadConfig (file:///usr/lib/node_modules/openclaw/dist/io-cPs4dU7X.js:...)
```

### 根因

v2026.3.22 將 acpx 從**獨立外部 extension**改為**完全內建至 `dist/` 的 bundled plugin**，舊路徑 `/usr/lib/node_modules/openclaw/extensions/acpx` 不復存在。

升級後 `~/.openclaw/openclaw.json` 仍保留三處指向舊路徑的殘留設定，以及一個舊版遺留的獨立 runtime config 檔：

| 殘留位置 | 問題 |
|---------|------|
| `plugins.load.paths[]` | 含舊 extension 路徑，config 驗證失敗，gateway 無法啟動 |
| `plugins.installs.acpx` | 舊版 path-install 紀錄，`sourcePath` 指向已消失的路徑 |
| `~/.openclaw/extensions/acpx.json` | 舊 ACP runtime binary config，`command` 指向不存在的 binary |

> ⚠️ `openclaw doctor --fix` **對此問題無效**，需手動修復。

### 手動修復步驟

**第一步：備份 config**

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak
```

**第二步：從 `plugins.load.paths` 移除 acpx 舊路徑**

找到 `plugins.load.paths` 陣列，刪除含 `extensions/acpx` 的那一行：

```jsonc
// 修改前
"load": {
  "paths": [
    "/usr/lib/node_modules/openclaw/extensions/acpx",  // ← 刪除此行
    "/root/.openclaw/extensions/execution-watchdog-probe",
    "/root/.openclaw/extensions/execution-watchdog"
  ]
}

// 修改後
"load": {
  "paths": [
    "/root/.openclaw/extensions/execution-watchdog-probe",
    "/root/.openclaw/extensions/execution-watchdog"
  ]
}
```

**第三步：從 `plugins.installs` 移除 `acpx` key**

```jsonc
// 修改前
"installs": {
  "acpx": {
    "source": "path",
    "spec": "acpx",
    "sourcePath": "/usr/lib/node_modules/openclaw/extensions/acpx",
    "installPath": "/usr/lib/node_modules/openclaw/extensions/acpx",
    "installedAt": "2026-03-10T07:04:32.239Z"
  },
  "feishu": { ... }
}

// 修改後
"installs": {
  "feishu": { ... }
}
```

**第四步：備份並移除舊的 ACP runtime config**

```bash
mv ~/.openclaw/extensions/acpx.json ~/.openclaw/extensions/acpx.json.bak
```

新版 acpx 完全內建，不再需要外部 binary config。若此檔案不存在可跳過。

**第五步：重啟並確認**

```bash
openclaw gateway restart
openclaw status
```

Gateway 正常啟動後，`plugins.entries.acpx` 會由 openclaw 自動寫入 config，無需手動設定。

### 外部 CLI 作為修復工具（Gateway 完全失效時的 workaround）

若 `openclaw` 所有指令均失效，可直接啟動已安裝的外部 ACP CLI（kiro、claude、codex 任一），將上述錯誤訊息告知它，讓它自動診斷並修改 `~/.openclaw/openclaw.json`。

這正是 acpx harness「認證解耦、保留原生 CLI 能力」設計的實際體現：**當 OpenClaw 本身出問題，外部 CLI 仍可獨立運作，反過來成為修復 OpenClaw 的工具。**

---

## 核心問題模式

版本 pin 頻繁變動（`0.1.15` → `0.1.16` → `0.2.0` → `0.3.0`）、npm 打包流程不穩定、Windows 支援持續有問題，是整個 acpx 生命週期的三大痛點。

---

## 參考資料

- [ACP + Codex 設定指南](./acp_codex.md)
- [ACP + Gemini 設定指南](./acp_gemini.md)
- [ACP + Kiro 設定指南](./acp_kiro.md)
- [Sandbox 架構與 Pluggable Backends](./sandbox.md)
- [Tooling Safety](./core/tooling-safety.md)
- [openclaw/openclaw ACP Megathread](https://github.com/openclaw/openclaw/issues/34626)
