---
last_validated: 2026-04-02
---

# OpenClaw Sandbox 深度解析

## 概述

OpenClaw Sandbox 是一個基於 Docker 的隔離執行環境，用於保護主機系統免受 AI Agent 潛在危險操作的影響。

**首次引入版本：** `2026.1.8`

---

## 解決的問題

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           沒有 Sandbox 的風險                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User: "幫我整理 ~/Downloads"                                              │
│                        │                                                    │
│                        ▼                                                    │
│   ┌─────────────┐    ┌─────────────────────────────────────────────────┐   │
│   │   Agent     │───▶│  exec: rm -rf ~/*   (模型幻覺/惡意 prompt)      │   │
│   └─────────────┘    └─────────────────────────────────────────────────┘   │
│                                       │                                     │
│                                       ▼                                     │
│                              💥 整台電腦毀了                                │
│                                                                             │
│   風險來源：                                                                │
│   • 模型幻覺 (Hallucination) - 產生錯誤指令                                │
│   • Prompt Injection - 惡意輸入誘導執行危險指令                            │
│   • 工具濫用 - Agent 有完整 Host 權限                                      │
│   • 資料外洩 - 可讀取 ~/.ssh, ~/.aws 等敏感檔案                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 架構

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenClaw Sandbox 架構                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐                                                           │
│   │   Agent     │                                                           │
│   │  (Gateway)  │                                                           │
│   └──────┬──────┘                                                           │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                    Sandbox Mode 判斷                              │      │
│   │  • off      → 直接在 Host 執行                                   │      │
│   │  • non-main → 只有非主 session 進 sandbox                        │      │
│   │  • all      → 所有 session 都進 sandbox                          │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                    Docker Container                               │      │
│   │  ┌────────────────────────────────────────────────────────────┐  │      │
│   │  │  debian:bookworm-slim (預設)                               │  │      │
│   │  │                                                            │  │      │
│   │  │  安全設定：                                                │  │      │
│   │  │  • --read-only (唯讀根目錄)                                │  │      │
│   │  │  • --cap-drop ALL (移除所有 capabilities)                  │  │      │
│   │  │  • --security-opt no-new-privileges                        │  │      │
│   │  │  • --pids-limit (限制 process 數量)                        │  │      │
│   │  │  • --memory / --cpus (資源限制)                            │  │      │
│   │  │  • seccomp / apparmor profiles                             │  │      │
│   │  │                                                            │  │      │
│   │  │  掛載：                                                    │  │      │
│   │  │  • workspace → /workspace (:ro 或 :rw)                     │  │      │
│   │  │  • tmpfs → /tmp, /var/tmp                                  │  │      │
│   │  │  • 自訂 binds                                              │  │      │
│   │  └────────────────────────────────────────────────────────────┘  │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三層控制機制

| 層級 | 設定路徑 | 功能 |
|------|----------|------|
| **Sandbox** | `agents.defaults.sandbox.*` | 決定工具在哪裡執行（Docker vs Host） |
| **Tool Policy** | `tools.allow/deny` | 決定哪些工具可用 |
| **Elevated** | `tools.elevated.*` | exec 專用的 Host 逃逸機制 |

---

## Sandbox Scope（容器共享範圍）

| Scope | 說明 |
|-------|------|
| `session` | 每個 session 獨立容器 |
| `agent` | 同一 agent 共用容器 |
| `shared` | 所有 agent 共用一個容器 |

---

## 設定範例

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "scope": "agent",
        "workspaceAccess": "rw",
        "docker": {
          "image": "openclaw-sandbox:bookworm-slim",
          "containerPrefix": "openclaw-sbx-",
          "readOnlyRoot": true,
          "capDrop": ["ALL"],
          "pidsLimit": 256,
          "memory": "2g",
          "cpus": 2
        }
      }
    }
  }
}
```

---

## CLI 指令

```bash
# 查看當前 sandbox 狀態
openclaw sandbox explain

# 列出所有 sandbox 容器
openclaw sandbox list

# 重建所有容器（更新 image 後）
openclaw sandbox recreate --all
```

---

## 核心問題與解法

| 問題 | 說明 | Sandbox 解法 |
|------|------|-------------|
| **爆炸半徑** | Agent 出錯可能毀掉整台機器 | 限制在容器內，最多毀 workspace |
| **敏感資料** | Agent 可讀 ~/.ssh, ~/.aws | 容器內看不到 Host 檔案系統 |
| **惡意指令** | Prompt injection 誘導執行 `rm -rf` | 唯讀根目錄 + 權限限制 |
| **資源耗盡** | 無限 fork bomb, 記憶體耗盡 | pids-limit, memory limit |
| **網路攻擊** | Agent 被誘導發起攻擊 | 可限制網路存取 |

---

## 一句話總結

> **Sandbox = 讓 Agent 在「沙盒」裡玩，玩壞了也不會影響你的電腦。**

---

## 當前狀態（2026.2.15）

### 最新版本更新

| 版本 | 重點更新 |
|------|----------|
| 2026.2.15 | `sandbox.browser.binds` 獨立設定 browser 容器掛載 |
| 2026.2.14 | Sandbox file tools 支援 bind-mount 路徑、read-only 語意強化 |
| 2026.2.13 | 安全強化：skill sync 路徑限制、media 路徑驗證 |

### 近期安全修復

- **Skill sync 路徑限制**：防止 frontmatter 控制的 skill name 作為檔案系統路徑
- **Media 路徑驗證**：message tool attachments 強制 sandbox 路徑檢查
- **Browser 安全**：sandbox browser bridge server 需要認證
- **Web tools**：browser/web 內容預設視為不可信

---

## 🌪️ Sandbox 災情總結（2026.2.15）

> **核心問題**：2026.2.15 版本引入的 Sandbox 改動導致多個關鍵場景失效。

### 發生災情的版本

- **引入版本**：`2026.2.15`
- **影響範圍**：使用 `sandbox.mode != "off"` + `elevated exec` + cron/nested sessions 的組合

### 四大核心改動摘要

| 星級 | 改動 | 說明 |
|------|------|------|
| ⭐️⭐️⭐️ | SHA-1 → SHA-256 | 沙箱配置雜湊演算法升級，影響緩存標識與重建檢查 |
| ⭐️⭐️⭐️ | 阻止危險 Docker 設定 | 封鎖 bind mounts、host networking、unconfined seccomp/apparmor |
| ⭐️ | 保留陣列順序於配置雜湊 | 修正順序敏感的 Docker 設定未觸發容器重建 |
| ⭐️ | 澄清系統提示路徑 (#17693) | sandbox bash/exec 使用容器路徑 /workspace，檔案工具保持主機映射 |

### 🔴 高影響 — 功能性災難

| Issue | 標題 | 說明 | 影響 | 狀態 |
|-------|------|------|------|------|
| [#18748](https://github.com/openclaw/openclaw/issues/18748) | Elevated exec 在 cron 和 sessions_send 中失效 | sandbox 模式下，cron job 和跨 agent 訊息觸發的 exec(elevated=true) 全部失敗，即使 config 正確設定 `tools.elevated.enabled: true` 也沒用 | ⚠️ 多 agent + sandbox + cron 組合完全無法使用 elevated exec（如 gog、remindctl、memo 等工具） | 🔒 CLOSED (stale) |
| [#4171](https://github.com/openclaw/openclaw/issues/4171) | Cron isolated agent 沒傳 sandboxInfo 給 system prompt | agent 收到主機路徑而非容器路徑 `/workspace`，導致路徑錯誤、幻覺檔案 | ⚠️ cron job 的 agent 使用錯誤路徑，可能創建/讀取錯誤檔案 | 🔒 CLOSED (stale) |
| [#2432](https://github.com/openclaw/openclaw/issues/2432) | Read tool 不尊重 Docker bind mounts | 設了 `docker.binds` 但 agent 讀不到掛載的路徑 | ⚠️ 無法讀取 bind-mount 的資料夾內容 | 🔒 CLOSED (stale) |
| [#4368](https://github.com/openclaw/openclaw/issues/4368) | DEFAULT_SANDBOX_WORKSPACE_ROOT 忽略 MOLTBOT_STATE_DIR | 硬編碼 `~/.clawdbot/sandboxes`，不管你怎麼設環境變數 | ⚠️ 環境變數配置無效，路徑混亂 | 🔒 CLOSED |

### 🟡 中影響 — 安全性問題

| Issue | 標題 | 說明 | 狀態 |
|-------|------|------|------|
| [#18766](https://github.com/openclaw/openclaw/issues/18766) | SKILL.md runtime 指令不受路徑限制 | install-time 有限制，但 runtime 階段 SKILL.md 可以指示 agent 讀寫任意路徑 | 🔒 CLOSED (stale) |
| [#18739](https://github.com/openclaw/openclaw/issues/18739) | Windows 上 exec tool 因 `detached: true` 導致 stdout 全空 | Windows 上所有 exec 指令回傳 `(no output)` | 🔒 CLOSED |

### 📊 影響評估

| 使用場景 | 目前狀態 | 建議 |
|---------|---------|------|
| `sandbox.mode: "all"` + `elevated exec` + 直接互動 | ✅ 正常 | 無 |
| `sandbox.mode: "all"` + `elevated exec` + cron job | ❌ 無法使用 | 暫時設定 `sandbox.mode: "off"` 或移除 elevated 需求 |
| `sandbox.mode: "all"` + `elevated exec` + sessions_send | ❌ 無法使用 | 同上 |
| `sandbox.mode: "all"` + `docker.binds` + read tool | ❌ 無法使用 | 暫時停用 bind mounts |
| 多agent cron 工作流 | ⚠️ 部分失效 | 注意路徑錯誤問題 |

### ✅ 已解決問題（關閉）

| Issue | 狀態 | 說明 |
|-------|------|------|
| [#4689](https://github.com/openclaw/openclaw/issues/4689) | 🔒 CLOSED (stale) | sandbox.mode=off 時 exec 仍預設進 sandbox |
| [#4807](https://github.com/openclaw/openclaw/issues/4807) | 🔒 CLOSED (stale) | sandbox-setup.sh 未包含在 npm 包中 |
| [#5255](https://github.com/openclaw/openclaw/issues/5255) | 🔒 CLOSED (stale) | browser file upload API 缺少路徑驗證 |

### 🔧 Workarounds

#### 1. Elevated exec 在 cron 中失效

**暫解方案**：對需要 elevated exec 的 agent 關閉 sandbox

```json
{
  "agents": {
    "list": [{
      "id": "scout",
      "sandbox": {
        "mode": "off"
      },
      "tools": {
        "elevated": {
          "enabled": true
        }
      }
    }]
  }
}
```

**缺點**：失去 sandbox 安全隔離

#### 2. Cron agent 路徑錯誤

**暫解方案**：避免在 cron agent 中依賴工作目錄，明確使用 `/workspace` 路徑

```bash
# 在 SKILL.md 中，使用絕對路徑
cd /workspace
read: /workspace/data/input.txt
```

#### 3. Docker bind mounts 無法讀取

**暫解方案**：暫時停用 bind mounts，或改用其他資料傳遞方式

#### 4. Windows 上 exec 無 stdout

**暫解方案**：使用 PowerShell 腳本檔案而非 inline command

---

## 已知問題（Open Issues）

### 🔴 Critical

| Issue | 標題 | 說明 | 狀態 |
|-------|------|------|------|
| [#8566](https://github.com/openclaw/openclaw/issues/8566) | Sandbox browser runs Chromium as root with --no-sandbox | CVSS 9.6 - Chromium 以 root 執行且停用 sandbox | 🔒 CLOSED (stale) |
| [#50655](https://github.com/openclaw/openclaw/issues/50655) | Agent crashes (exit code 255) when fetching GitHub profile page inside OpenShell sandbox | OpenShell sandbox 內 web_fetch GitHub 頁面導致 agent crash | 🟢 OPEN |

### 🟠 Bugs

| Issue | 標題 | 說明 | 狀態 |
|-------|------|------|------|
| [#9348](https://github.com/openclaw/openclaw/issues/9348) | write tool restriction inconsistent with exec tool | write 和 exec 路徑限制不一致 | 🔒 CLOSED (stale) |
| [#13276](https://github.com/openclaw/openclaw/issues/13276) | slugifySessionKey truncates phone numbers | 容器名稱截斷電話號碼 | 🔒 CLOSED (stale) |
| [#16382](https://github.com/openclaw/openclaw/issues/16382) | Discord attachments impossible from sandboxed agents | Sandbox 內無法發送 Discord 附件 | 🔒 CLOSED |

### 🟢 Feature Requests

| Issue | 標題 | 說明 | 狀態 |
|-------|------|------|------|
| [#7722](https://github.com/openclaw/openclaw/issues/7722) | Filesystem Sandboxing Config (tools.fileAccess) | 請求 allowedPaths/denyPaths 設定 | 🟢 OPEN |
| [#7827](https://github.com/openclaw/openclaw/issues/7827) | Default Safety Posture: Sandbox & Session Isolation | 請求預設啟用 sandbox | 🔒 CLOSED |
| [#12405](https://github.com/openclaw/openclaw/issues/12405) | Pluggable sandbox backends & per-agent exec routing | 支援 VM/OrbStack 等非 Docker 後端 | 🟢 OPEN |
| [#13543](https://github.com/openclaw/openclaw/issues/13543) | Tool-level sandbox mode for selective isolation | 請求 per-tool sandbox 設定 | 🟢 OPEN |
| [#52662](https://github.com/openclaw/openclaw/issues/52662) | Browser sandbox should support non-Docker backends | 要求 browser sandbox 支援外部 CDP/noVNC endpoint（與 pluggable backend 方向一致） | 🟢 OPEN |

---

## 社群討論重點

### 1. 預設安全姿態爭議

目前 sandbox 預設為 `off`，社群建議：

- 新安裝預設 `mode: "non-main"`
- 公開 agent 預設 `mode: "all"` + `workspaceAccess: "none"`
- DM 預設 `dmScope: "per-channel-peer"`

### 2. Docker 限制

Docker sandbox 對 coding agent 過於嚴格，社群正在探索：

- OrbStack VM 作為 node
- exe.dev 雲端 VM
- 請求 pluggable backend 支援

### 3. 路徑限制不一致

`write` tool 有額外路徑限制，但 `exec` 可用 `cat > file` 繞過，社群建議統一以 Docker binds 為準。

---

## Workarounds

### npm 安裝缺少 sandbox image

```bash
docker pull debian:bookworm-slim
docker tag debian:bookworm-slim openclaw-sandbox:bookworm-slim
```

### sandbox.mode=off 但 exec 仍進 sandbox

```json
{
  "tools": {
    "exec": { "host": "gateway" }
  }
}
```

### Discord 附件問題

暫時停用 sandbox：`sandbox.mode: "off"`

---

## 參考資料

- [OpenClaw Sandbox CLI Docs](https://github.com/openclaw/openclaw/blob/main/docs/cli/sandbox.md)
- [Sandbox vs Tool Policy vs Elevated](https://github.com/openclaw/openclaw/blob/main/docs/gateway/sandbox-vs-tool-policy-vs-elevated.md)
- [Source: src/agents/sandbox/docker.ts](https://github.com/openclaw/openclaw/blob/main/src/agents/sandbox/docker.ts)
- [Multi-agent Sandbox Tools](https://docs.openclaw.ai/multi-agent-sandbox-tools)
- [Security Docs](https://docs.openclaw.ai/cli/security)
- [Original Gist](https://gist.github.com/pahud/d937b72dcbd404b07115be681de1d46e)

---

## Pluggable Sandbox Backends（v2026.3.22）

> **背景：** 社群長期反映 Docker sandbox 對 coding agent 過於嚴格，且無法適應 VM、OrbStack、雲端等不同部署環境（見 issue [#12405](https://github.com/openclaw/openclaw/issues/12405)）。v2026.3.22 將 sandbox 重構為可插拔架構。

### 架構演進

```
══════════════════════════════════════════════════════════════
  舊架構（v2026.1.8 ~ v2026.2.15）：只有 Docker
══════════════════════════════════════════════════════════════

  ┌─────────┐     ┌──────────────────┐     ┌───────────────┐
  │  Agent  │────▶│  Sandbox 判斷    │────▶│    Docker     │
  └─────────┘     │  off/non-main/all│     │   Container   │
                  └──────────────────┘     └───────────────┘
                         │ mode=off
                         ▼
                  ┌──────────────┐
                  │  Host 直接執行│
                  └──────────────┘

══════════════════════════════════════════════════════════════
  新架構（v2026.3.22）：Pluggable Backends
══════════════════════════════════════════════════════════════

  ┌─────────┐     ┌──────────────────┐     ┌──────────────────────┐
  │  Agent  │────▶│  Sandbox 判斷    │────▶│   Backend 路由       │
  └─────────┘     │  off/non-main/all│     │  （可插拔介面）       │
                  └──────────────────┘     └──────┬───────────────┘
                                                  │
                          ┌───────────────────────┼───────────────┐
                          ▼                       ▼               ▼
                  ┌──────────────┐     ┌────────────────┐  ┌──────────┐
                  │    Docker    │     │   OpenShell    │  │   SSH    │
                  │   Backend    │     │   Backend      │  │  Backend │
                  └──────────────┘     └───────┬────────┘  └──────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                             ┌────────────┐       ┌────────────┐
                             │   mirror   │       │   remote   │
                             │   模式     │       │   模式     │
                             └────────────┘       └────────────┘
```

### Backend 介面

所有 backend 實作同一介面，`sandbox list/recreate/prune` 等指令因此變成 backend-aware：

```
┌──────────────────────────────────┐
│   Sandbox Backend Interface      │
├──────────────────────────────────┤
│  create()                        │
│  exec(cmd)                       │
│  destroy()                       │
│  getStatus()                     │
└────────────┬─────────────────────┘
             │
   ┌─────────┼─────────┐
   ▼         ▼         ▼
Docker   OpenShell    SSH
```

### OpenShell Backend 兩種 Workspace 模式

| 模式 | 說明 | 適合場景 |
|------|------|----------|
| `mirror` | 本地 workspace 同步鏡像至 OpenShell | 本地開發，需要隔離但保留本地檔案 |
| `remote` | workspace 完全存在於遠端 | 雲端開發，不需要本地副本 |

```
  mirror 模式                          remote 模式
  ┌──────────┐  同步  ┌──────────┐    ┌──────────┐      ┌──────────┐
  │  本地    │──────▶│OpenShell │    │  本地    │      │OpenShell │
  │ workspace│◀──────│  副本    │    │ (無資料) │      │ workspace│
  └──────────┘  回寫  └──────────┘    └──────────┘      └──────────┘
                                              指令直接在遠端執行
```

### sandbox 指令 backend-aware 示意

```
openclaw sandbox list
  ├── Docker containers:
  │     openclaw-sbx-session-abc123   running
  ├── OpenShell instances:
  │     openclaw-os-agent-main        running
  └── SSH sessions:
        openclaw-ssh-dev-server       running

openclaw sandbox recreate --all
  ├── Docker  → docker rm + docker run
  ├── OpenShell → 銷毀 + 重建 workspace
  └── SSH     → 斷線 + 重連 + 重新初始化
```

## 參考資料

- [ACPX Harness 架構與演進史](./acpx-harness.md)
