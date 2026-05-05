---
last_validated: 2026-05-05
---

# OpenClaw File Transfer Plugin

## 概述

File Transfer Plugin 是 OpenClaw v2026.5.3 新增的 bundled plugin，讓 agent 能透過 paired nodes 進行 binary 檔案操作——讀取、列出、寫入遠端節點上的檔案與目錄。

**首次引入版本：** `2026.5.3`
**相關 PR：** [#74742](https://github.com/openclaw/openclaw/pull/74742)
**感謝：** @omarshahine

---

## 解決的問題

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      沒有 File Transfer Plugin 前                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Agent 想處理 paired node 上的檔案                                         │
│       │                                                                     │
│       ▼                                                                     │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │  只能用 exec 工具跑 shell 指令                                   │      │
│   │  cat / base64 / tar ...                                         │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│       │                                                                     │
│       ▼                                                                     │
│   問題：                                                                    │
│   • Binary 檔案透過 exec pipeline 容易損壞                                │
│   • 大檔案受 shell buffer / encoding 限制                                 │
│   • 沒有統一的存取控制，安全性參差不齊                                    │
│   • 每次都要拼湊 shell 指令，不可靠也不可攜                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     File Transfer Plugin 的價值                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ✓ 專用工具：四個 agent tool，分別處理檔案讀取、目錄列表、目錄下載、寫入   │
│   ✓ Binary 安全：直接處理 binary 資料，不經 shell pipeline                 │
│   ✓ 統一安全模型：default-deny per-node 路徑政策                            │
│   ✓ 操作者可控：需要 operator approval 才能設定存取權限                    │
│   ✓ Symlink 防護：預設拒絕 symlink traversal                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 架構

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   File Transfer Plugin 架構                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐                                                           │
│   │   Gateway   │                                                           │
│   │   (Agent)   │                                                           │
│   └──────┬──────┘                                                           │
│          │ 呼叫 tool                                                        │
│          ▼                                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                File Transfer Plugin                              │      │
│   │                                                                  │      │
│   │  Tools：                                                         │      │
│   │  ┌──────────────┐  ┌──────────────┐                             │      │
│   │  │ file_fetch   │  │ file_write   │                             │      │
│   │  │ 讀取單一檔案 │  │ 寫入單一檔案 │                             │      │
│   │  └──────────────┘  └──────────────┘                             │      │
│   │  ┌──────────────┐  ┌──────────────┐                             │      │
│   │  │ dir_list     │  │ dir_fetch    │                             │      │
│   │  │ 列出目錄內容 │  │ 下載整個目錄 │                             │      │
│   │  └──────────────┘  └──────────────┘                             │      │
│   │                                                                  │      │
│   └──────────────────────────┬───────────────────────────────────────┘      │
│                              │                                               │
│                              ▼                                               │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                 Paired Node（目標裝置）                           │      │
│   │                                                                  │      │
│   │  安全檢查：                                                      │      │
│   │  ① 路徑是否在 nodes.<nodeId>.allowedPaths 內？                   │      │
│   │  ② Symlink traversal 檢查（預設拒絕）                            │      │
│   │  ③ 檔案大小 ≤ 16 MB per round-trip                              │      │
│   │                                                                  │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 工具列表

Plugin ID 為 `file-transfer`，啟用後 agent 會獲得以下四個工具：

| 工具名稱 | 功能 | 回傳 |
|----------|------|------|
| `file_fetch` | 讀取指定路徑的單一檔案 | 檔案內容（binary safe） |
| `dir_list` | 列出指定目錄下的檔案與子目錄 | 目錄列表（名稱、大小、類型等） |
| `dir_fetch` | 下載整個目錄的內容 | 目錄結構與所有檔案 |
| `file_write` | 將資料寫入指定路徑 | 寫入結果 |

---

## 安全模型

File Transfer Plugin 採取 **default-deny** 政策——未明確允許的路徑一律拒絕存取。

### 核心安全原則

| 原則 | 說明 |
|------|------|
| **Default-deny** | 每個 node 預設不允許任何路徑存取，必須明確設定 `allowedPaths` |
| **Per-node 政策** | 不同 node 可以設定不同的允許路徑 |
| **Operator approval** | 路徑設定需要 operator 確認，agent 不能自行變更 |
| **Symlink 防護** | 預設拒絕 symlink traversal（opt-in `followSymlinks` 才會跟隨） |
| **大小限制** | 單次 round-trip 上限 **16 MB**，防止大量資料外洩 |

### 安全檢查流程

```
Agent 呼叫 file_fetch / dir_list / dir_fetch / file_write
    │
    ▼
  ① Node 是否已 paired？
    │ 否 → 拒絕
    ▼
  ② 請求路徑是否在 nodes.<nodeId>.allowedPaths 內？
    │ 否 → 拒絕
    ▼
  ③ 路徑是否包含 symlink？（若 followSymlinks 未啟用）
    │ 是 → 拒絕
    ▼
  ④ 檔案大小是否 ≤ 16 MB？
    │ 否 → 拒絕
    ▼
  ✓ 允許操作
```

---

## 安裝與啟用

File Transfer Plugin 是 bundled plugin，**不需要額外安裝**。只需在 `openclaw.json` 中啟用並設定即可。

### 最小設定

```json
{
  "plugins": {
    "entries": {
      "file-transfer": {
        "enabled": true,
        "config": {
          "nodes": {
            "my-laptop": {
              "allowedPaths": ["/Users/tboydar/Documents"]
            }
          }
        }
      }
    }
  }
}
```

這會：
1. 啟用 `file-transfer` plugin
2. 允許 agent 透過 `my-laptop` 這個 paired node 存取 `/Users/tboydar/Documents` 路徑

### 進階設定

```json
{
  "plugins": {
    "entries": {
      "file-transfer": {
        "enabled": true,
        "config": {
          "nodes": {
            "my-laptop": {
              "allowedPaths": [
                "/Users/tboydar/Documents",
                "/Users/tboydar/Photos"
              ],
              "followSymlinks": false
            },
            "home-server": {
              "allowedPaths": [
                "/data/shared",
                "/home/backup"
              ],
              "followSymlinks": true
            }
          }
        }
      }
    }
  }
}
```

### 設定欄位說明

| 欄位 | 類型 | 預設 | 說明 |
|------|------|------|------|
| `plugins.entries.file-transfer.enabled` | boolean | `false` | 是否啟用 plugin |
| `plugins.entries.file-transfer.config.nodes` | object | — | 以 node ID 為 key 的設定物件 |
| `nodes.<nodeId>.allowedPaths` | string[] | `[]` | 允許存取的路徑清單（白名單） |
| `nodes.<nodeId>.followSymlinks` | boolean | `false` | 是否允許跟隨 symlink |

---

## 使用場景範例

### 場景 1：讀取遠端節點的日誌檔案

Agent 需要檢查 home-server 上的應用日誌：

```
Agent: 我來讀取 home-server 上的日誌檔案
→ 使用 file_fetch 工具
  nodeId: home-server
  path: /var/log/myapp/error.log
← 回傳檔案內容，Agent 可以分析日誌並回報問題
```

### 場景 2：備份文件到另一台機器

Agent 從 my-laptop 取得文件後寫入 home-server：

```
Agent: 幫你把報告備份到 home-server
→ 使用 file_fetch 從 my-laptop 讀取 /Users/tboydar/Documents/report.pdf
→ 使用 file_write 寫入 home-server 的 /data/shared/backup/report.pdf
```

### 場景 3：列出目錄結構

Agent 想了解某個目錄下有什麼檔案：

```
Agent: 讓我看看 Photos 目錄下有什麼
→ 使用 dir_list 工具
  nodeId: my-laptop
  path: /Users/tboydar/Photos
← 回傳檔案列表（名稱、大小、類型）
```

### 場景 4：批次下載目錄

Agent 需要整個目錄的內容進行處理：

```
Agent: 我來下載整個專案目錄
→ 使用 dir_fetch 工具
  nodeId: home-server
  path: /data/shared/project
← 回傳完整目錄結構與所有檔案
```

---

## 安全注意事項

> ⚠️ 路徑設定是安全邊界。設定前請確認以下事項。

### 1. 最小權限原則

只開放 agent **確實需要**存取的路徑。避免開放過大的範圍：

```json
// ❌ 不建議：開放整個家目錄
"allowedPaths": ["/Users/tboydar"]

// ✅ 建議：只開放需要的子目錄
"allowedPaths": ["/Users/tboydar/Documents/reports"]
```

### 2. Symlink 風險

預設 `followSymlinks: false` 是安全防護——防止攻擊者透過 symlink 指向 `/etc/shadow` 等敏感檔案。除非你確實理解風險，**請保持預設值**。

### 3. 寫入操作的風險

`file_write` 工具可以寫入檔案。雖然路徑受 `allowedPaths` 限制，但仍需注意：
- Agent 可能覆蓋重要檔案
- 建議寫入路徑與讀取路徑分開設定

### 4. 16 MB 大小限制

單次操作的 ceiling 為 **16 MB**。超過此限制的檔案會被拒絕。這是安全防護，防止大量資料外洩或異常流量。

---

## Troubleshooting

### 症狀：工具呼叫被拒絕，回傳「path not allowed」

**可能原因：**
- 請求的路徑未包含在該 node 的 `allowedPaths` 中

**處理方式：**
1. 檢查 `openclaw.json` 中 `plugins.entries.file-transfer.config.nodes.<nodeId>.allowedPaths`
2. 確認路徑完全匹配（注意尾端斜線）
3. 更新設定後重啟 gateway：`openclaw gateway restart`

### 症狀：工具呼叫被拒絕，回傳「symlink traversal denied」

**可能原因：**
- 路徑中包含 symlink，但 `followSymlinks` 為 `false`

**處理方式：**
1. 確認是否確實需要跟隨 symlink
2. 若需要，在該 node 設定中加入 `"followSymlinks": true`
3. 確認 symlink 目標仍在 `allowedPaths` 範圍內

### 症狀：工具呼叫被拒絕，回傳「node not paired」

**可能原因：**
- 指定的 nodeId 尚未完成 pairing

**處理方式：**
1. 確認 node 已正確配對：`openclaw node list`
2. 若未列出，請先完成 node pairing 流程（參見 [nodes.md](./nodes.md)）

### 症狀：檔案操作回傳「size exceeds ceiling」

**可能原因：**
- 檔案或目錄超過 16 MB 的單次操作上限

**處理方式：**
1. 使用 `dir_list` 先了解檔案大小
2. 改用 `exec` 工具以串流方式處理大檔案（如 `split`、`rsync`）
3. 或考慮將大檔案拆分後逐個操作

---

## 相關連結

- [PR #74742](https://github.com/openclaw/openclaw/pull/74742) — File Transfer Plugin 實作
- [Nodes 文件](./nodes.md) — OpenClaw Node Pairing 說明
- [Sandbox 深度解析](./sandbox.md) — OpenClaw 安全隔離機制
- [OpenClaw Security Docs](https://docs.openclaw.ai/cli/security)
