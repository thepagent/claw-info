---
last_validated: 2026-04-05
validated_by: thepagent
---

# OpenClaw 自動更新流程

使用 openclaw cron、Telegram 與 kiro-cli 實現自動版本檢查與更新。

## 概覽

當有新版 openclaw 時，系統會透過 Telegram 通知你，並附上風險評估（🟢/🟡/🔴）。你回覆 `UPDATE CLAW` 後，更新會自動執行，包含 gateway 重啟與完成確認。

## 工作流程

```
     TELEGRAM              OPENCLAW                 KIRO CLI
        │                     │                        │
        │          ┌──────────┴──────────┐             │
        │          │  cron（每小時）      │             │
        │          │  比較版本號          │             │
        │          └──────────┬──────────┘             │
        │                     │                        │
        │          ┌──────────┴──────────┐             │
        │          │  發現新版本          │             │
        │          │  抓取 release notes  │             │
        │          │  讀取 openclaw.json  │             │
        │          │  分析風險等級        │             │
        │          └──────────┬──────────┘             │
        │                     │                        │
        │◄────────────────────┤                        │
        │  "🦞 X→Y 有新版本   │                        │
        │   風險評估：🟡 medium│                        │
        │   • breaking change │                        │
        │   說 UPDATE CLAW"   │                        │
        │                     │                        │
        │  你送出             │                        │
        │  UPDATE CLAW        │                        │
        ├────────────────────►│                        │
        │                     │                        │
        │          ┌──────────┴──────────┐             │
        │          │  main agent         │             │
        │          │  workspace skill:   │             │
        │          │  update_claw        │             │
        │          └──────────┬──────────┘             │
        │                     │                        │
        │                     │  setsid kiro-cli       │
        │                     │  "UPDATE CLAW"         │
        │                     ├───────────────────────►│
        │                     │                        │
        │                     │          ┌─────────────┴────────────┐
        │                     │          │  skill: openclaw-update   │
        │                     │          │  執行 openclaw-update.sh  │
        │                     │          └─────────────┬────────────┘
        │                     │                        │
        │                     │          ┌─────────────┴────────────┐
        │                     │          │  npm install -g           │
        │                     │          │  openclaw@latest          │
        │                     │          └─────────────┬────────────┘
        │                     │                        │
        │                     │          ┌─────────────┴────────────┐
        │                     X          │  systemctl restart        │◄─ gateway 重啟
        │                  （重啟中）    │  openclaw-gateway         │
        │                     │          └─────────────┬────────────┘
        │                     │                        │
        │                     │          ┌─────────────┴────────────┐
        │                     │          │  輪詢 openclaw health     │
        │                     │◄─────────┤  直到 gateway 就緒        │
        │                     │  就緒    └─────────────┬────────────┘
        │                     │                        │
        │◄────────────────────┼────────────────────────┤
        │  "🎉 已更新至 Y"    │                        │
        │                     │                        │
```

## 元件說明

### openclaw cron 排程
- 每小時執行一次，使用獨立 isolated agent session
- 比較 `openclaw --version` 與 `npm show openclaw version`
- 版本相同時靜默，不發任何通知
- 發現新版本時：
  1. 抓取 GitHub release notes（`api.github.com/repos/openclaw/openclaw/releases/tags/v$LATEST`）
  2. 讀取 `~/.openclaw/openclaw.json`
  3. 分析 release notes 對照當前 config，產出風險等級與影響摘要
  4. 發送含風險評估的 Telegram 通知

> ⚠️ cron payload 直接內嵌完整指令，不依賴 skill（isolated session 不載入 skill）

### openclaw workspace skill：`update_claw`
- 自動註冊為 `/update_claw` Telegram slash command
- 你在 Telegram 送出 `/update_claw` 或 `UPDATE CLAW` 時觸發
- 使用 `setsid` 讓 kiro-cli 脫離 gateway 程序，確保 gateway 重啟後仍能繼續執行

### kiro skill：`openclaw-update`
- 由 `UPDATE CLAW` 訊息觸發
- 執行 `~/.openclaw/scripts/openclaw-update.sh`

### 更新腳本：`openclaw-update.sh`
```bash
npm install -g openclaw@latest --ignore-scripts
openclaw doctor --fix --non-interactive   # 修復 systemd service 設定
systemctl --user restart openclaw-gateway.service
# 輪詢直到 gateway 就緒
openclaw message send ... "🎉 已更新至 $NEW_VERSION"
```

## 設計重點

- **`setsid`** — 讓 kiro-cli 脫離 openclaw gateway 的 cgroup，確保 gateway 重啟時不被一併終止
- **`--ignore-scripts`** — 避免 node v24 上 `@discordjs/opus` 原生編譯失敗
- **`openclaw doctor --fix`** — npm install 後、restart 前執行，修復 systemd service 指向正確的 node/binary
- **輪詢等待** — gateway 重啟後最多等待 60 秒，確認就緒後才發送 TG 確認訊息
- **獨立 cron session** — 版本檢查在獨立 isolated context 執行，不污染 main session
- **inline cron message** — isolated session 不載入 skill，完整步驟直接內嵌於 cron payload message

## 常見問題排除

### Agent 抱怨「工具壞了」或找不到 openclaw

Isolated session 使用精簡 PATH，找不到 `~/.npm-global/bin/openclaw`。

```
isolated session exec
        │
        ▼
┌─────────────────────────────────┐
│ PATH = /usr/local/bin:/usr/bin  │  ← 精簡 PATH
│        無 ~/.npm-global/bin     │
└─────────────────┬───────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ openclaw 找不到 │──► agent 回報「工具壞了」❌
        └─────────────────┘

  設定 tools.exec.pathPrepend 後：

isolated session exec
        │
        ▼
┌──────────────────────────────────────┐
│ PATH = ~/.npm-global/bin             │
│      + ~/.local/share/fnm/.../bin    │
│      + /usr/local/bin:...            │
└──────────────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────┐
        │ openclaw ✅       │
        │ npm ✅            │
        └──────────────────┘
```

**解法**：將常用 binary symlink 至 `~/.local/bin/`，再設定 `tools.exec.pathPrepend`：

```bash
# 建立 symlink
ln -sf ~/.npm-global/bin/openclaw ~/.local/bin/openclaw
ln -sf ~/.local/share/fnm/node-versions/<version>/installation/bin/npm ~/.local/bin/npm

# 設定 pathPrepend（只需一個路徑）
openclaw config set tools.exec.pathPrepend '["~/.local/bin"]' --strict-json
systemctl --user restart openclaw-gateway.service
```

### UPDATE CLAW 一直要求人工核准

`host=gateway` 時 exec 預設需要批准。需要同時設定兩處：

```
        ┌─────────────────────┐
        │   agent exec 請求   │
        └──────────┬──────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │       取較嚴格者             │
        │                              │
        │  tools.exec.ask              │
        │  (openclaw.json)             │
        │          vs                  │
        │  exec-approvals.json         │
        │  defaults.ask                │
        └──────────┬───────────────────┘
                   │
         ┌─────────┴──────────┐
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────────┐
│  兩者皆 off     │  │  任一為 on-miss      │
└────────┬────────┘  └──────────┬──────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐  ┌─────────────────────┐
│  直接執行 ✅    │  │  要求人工批准        │
└─────────────────┘  └──────────┬──────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  approval timeout   │
                      │  → 拒絕執行 ❌      │
                      └─────────────────────┘
```

> ⚠️ `tools.exec.*` 與 `exec-approvals.json` 取**較嚴格**者，兩處都要設。

**1. `openclaw.json`（全域）**：

```bash
openclaw config set tools.exec.ask off
openclaw config set tools.exec.security full
```

**2. `exec-approvals.json`（用 CLI，勿直接編輯）**：

直接編輯 `exec-approvals.json` 會被 gateway 重啟覆寫。請用 CLI：

```bash
# 所有 agent 允許跑 scripts/
openclaw approvals allowlist add --agent "*" "/home/<user>/.openclaw/scripts/*"

# main agent 允許 kiro-cli + setsid
openclaw approvals allowlist add --agent "main" "/home/<user>/.local/bin/kiro-cli"
openclaw approvals allowlist add --agent "main" "/usr/bin/setsid"
```

**3. Per-agent 設定（最終保障）**：

```bash
openclaw config set agents.list[0].tools.exec.ask off
openclaw config set agents.list[0].tools.exec.security full
openclaw config set agents.list[0].tools.exec.host gateway
systemctl --user restart openclaw-gateway.service
```
