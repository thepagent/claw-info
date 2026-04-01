---
last_validated: 2026-04-02
---

# Chrome DevTools MCP — 本地瀏覽器自動化筆記

## 概述

`chrome-devtools-mcp` 是 Google 官方的 MCP stdio 伺服器，可連接本地 Chrome 並提供 29 個工具，包括 Lighthouse 稽核、效能追蹤、網路檢查、記憶體快照等。OpenClaw 的 `existing-session` driver 內部即透過此伺服器控制 Chrome。

本文記錄在 macOS 上的實測結果，涵蓋設定方式、工具清單、捲動行為，以及與 `agent-browser` 的比較。

## 架構

```
┌───────────────────────────────────────────────────────────┐
│                      本地機器                              │
│                                                           │
│  ┌──────────────┐   spawns    ┌───────────────────────┐  │
│  │   OpenClaw    │ ─────────> │ chrome-devtools-mcp   │  │
│  │   Gateway     │            │ (--autoConnect)       │  │
│  │  :18789       │ <───────── │ 29 個 MCP 工具         │  │
│  └──────────────┘   stdio     └──────────┬────────────┘  │
│                                          │                │
│                                   讀取 DevToolsActivePort │
│                                          │                │
│                                          v                │
│                               ┌───────────────────────┐  │
│                               │  Chrome 146+          │  │
│                               │  :9222 (127.0.0.1)    │  │
│                               └───────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

## 啟用 Remote Debugging

有兩種方式讓 Chrome 開啟 CDP 偵錯埠：

### 方式一：Chrome UI 切換（免重啟）

1. 開啟 `chrome://inspect#remote-debugging`
2. 啟用 **「Allow remote debugging」**
3. 伺服器立即啟動於 `127.0.0.1:9222`

### 方式二：命令列旗標（需重啟）

```bash
open -a "Google Chrome" --args --remote-debugging-port=9222
```

若 Chrome 已在執行，需先關閉再重新啟動，或使用獨立 profile：

```bash
/path/to/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug-profile
```

### 兩種方式的差異

| | UI 切換 | 命令列旗標 |
|---|---|---|
| 需要重啟 Chrome | 否 | 是 |
| `/json/version` HTTP 端點 | ❌ (404) | ✅ |
| `--autoConnect` | ✅ | ✅ |
| `--browserUrl` | ❌ | ✅ |
| 新連線權限提示 | 每次新 process 都會跳出 | 不會 |

**重點：** UI 切換方式必須使用持久連線（單一 process），否則每次新連線都會跳出權限確認對話框。

## 連線方式

### 獨立測試

```bash
npx -y chrome-devtools-mcp@latest --autoConnect
```

### OpenClaw existing-session profile

```json5
{
  browser: {
    profiles: {
      user: {
        driver: "existing-session",
        attachOnly: true
      }
    }
  }
}
```

`existing-session` driver 內部以 `--autoConnect` 啟動 `chrome-devtools-mcp`，透過 `DevToolsActivePort` 檔案自動發現 Chrome。

## 工具清單（29 個）

| 分類 | 工具 |
|------|------|
| 導航 | `navigate_page`, `new_page`, `close_page`, `list_pages`, `select_page` |
| 互動 | `click`, `hover`, `drag`, `fill`, `fill_form`, `type_text`, `press_key`, `upload_file`, `handle_dialog` |
| 檢查 | `take_snapshot`, `take_screenshot`, `evaluate_script`, `emulate`, `resize_page`, `wait_for` |
| 網路 | `list_network_requests`, `get_network_request` |
| 主控台 | `list_console_messages`, `get_console_message` |
| 效能 | `performance_start_trace`, `performance_stop_trace`, `performance_analyze_insight` |
| 診斷 | `lighthouse_audit`, `take_memory_snapshot` |

## 捲動 X (Twitter) 的實測

### press_key ✅

```
press_key({ key: "Space" })
```

頁面確實捲動，推文載入正常。

### evaluate_script ❌

```
evaluate_script({ function: "() => { window.scrollBy(0, 2000); return 'ok'; }" })
```

JS 有執行但頁面未視覺捲動。推測 X 攔截了 scroll 事件，或 CDP context 不同。

### 推文擷取

```
evaluate_script({
  function: "() => JSON.stringify([...document.querySelectorAll('article[data-testid=\"tweet\"]')].map(el=>({...})))"
})
```

可正常擷取當前 DOM 中的推文。X 使用虛擬捲動，同時僅保留約 10-15 個 tweet DOM 節點。

### 實測結果

持久連線 + 10 輪 Space 捲動 → 收集 14 則不重複推文。

## chrome-devtools-mcp vs agent-browser（皆為本地）

兩者皆透過 CDP 連接同一個本地 Chrome，差異在工具面與互動模式。

### 架構比較

```
chrome-devtools-mcp                          agent-browser
┌──────────┐  stdio   ┌──────────┐           ┌──────────┐
│ OpenClaw │ ───────> │ chrome-  │           │ agent-   │
│ / Client │ <─────── │ devtools │           │ browser  │
└──────────┘          │ -mcp     │           │ CLI      │
                      └────┬─────┘           └────┬─────┘
                           │ CDP                  │ CDP
                           v                      v
                      ┌──────────────────────────────┐
                      │     本地 Chrome :9222          │
                      └──────────────────────────────┘
```

### 互動模式

| | chrome-devtools-mcp | agent-browser |
|---|---|---|
| 協定 | MCP over stdio (JSON-RPC) | CLI 指令 |
| 元素發現 | `take_snapshot` → `uid` | `snapshot` → `@ref` |
| 點擊 | `click({ uid: "1_42" })` | `click @e42` |
| 輸入 | `fill({ uid: "1_42", value: "text" })` | `type @e42 "text"` |
| JS 執行 | `evaluate_script({ function: "() => ..." })` | `eval "..."` |
| 捲動 | `press_key({ key: "Space" })` | `scroll down 500` 或 `eval "scrollBy()"` |
| 連線模式 | 必須持久（單一 process） | 有狀態 session，逐指令執行 |

### 功能比較

| 功能 | chrome-devtools-mcp | agent-browser |
|---|---|---|
| 導航 / 點擊 / 輸入 | ✅ | ✅ |
| A11y 快照 | ✅ | ✅ |
| JS eval | ✅ | ✅ |
| 截圖 | ✅ | ✅ |
| 網路檢查 | ✅ | ❌ |
| 主控台訊息 | ✅ | ❌ |
| Lighthouse 稽核 | ✅ | ❌ |
| 效能追蹤 | ✅ | ❌ |
| 記憶體快照 | ✅ | ❌ |
| 多分頁 | ✅ | ❌ |
| 表單批次填寫 | ✅ | ❌ |
| 檔案上傳 | ✅ | ❌ |
| 對話框處理 | ✅ | ❌ |
| 裝置模擬 | ✅ | ❌ |
| 原生捲動指令 | ❌ (用 press_key) | ✅ |

### 何時用哪個

- **chrome-devtools-mcp**：互動式使用、除錯、效能分析、需要網路/記憶體檢查時
- **agent-browser**：腳本化批次自動化、簡單的捲動與擷取、不需要進階診斷工具時

## 環境資訊

- macOS
- Chrome 146.0.7680.80
- chrome-devtools-mcp 0.20.0
- OpenClaw 2026.3.13

## 參考

- [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)
- [OpenClaw Browser Docs — Chrome existing-session via MCP](https://beaverslab.mintlify.app/en/tools/browser#chrome-existing-session-via-mcp)
- [Issue #340](https://github.com/thepagent/claw-info/issues/340)
