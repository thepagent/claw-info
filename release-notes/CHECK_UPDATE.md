# OpenClaw 版本檢查機制

## 整體架構

```
┌─────────────────────────────────────────────────────────────────┐
│                      自動更新檢查完整架構                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OS crond                                                       │
│  (排程觸發)                                                      │
│      │                                                          │
│      ▼                                                          │
│  kiro-cli chat --non-interactive --trust-all-tools              │
│      "openclaw skill to check update now"                       │
│      │                                                          │
│      ▼                                                          │
│  Kiro CLI                                                       │
│  (自動載入 OpenClaw SKILL)                                       │
│      │                                                          │
│      ▼                                                          │
│  SKILL: 版本檢查                                                 │
│  openclaw --version  vs  npm show openclaw version              │
│      │                                                          │
│      ├─ 版本相同 → 結束                                          │
│      │                                                          │
│      └─ 版本不同                                                 │
│              │                                                  │
│              ▼                                                  │
│         OpenClaw message send                                   │
│         Telegram 通知新版本                                      │
│              │                                                  │
│              ▼                                                  │
│         gh issue list --state all                               │
│         (搜尋 open + closed)                                    │
│              │                                                  │
│              ├─ issue 已存在 → 結束                              │
│              │                                                  │
│              └─ issue 不存在                                     │
│                      │                                          │
│                      ▼                                          │
│                 gh issue create                                  │
│                 (release notes 任務)                             │
│                      │                                          │
│                      ▼                                          │
│                 OpenClaw message send                            │
│                 Telegram 通知 issue URL                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```


## 設計決策：為何選擇 OS crond + Kiro CLI

我們選擇 **OS crond + Kiro CLI** 而非 OpenClaw 內建的 heartbeats 機制，原因是可靠性：

- crond 是 OS 層級的排程，不依賴 OpenClaw gateway 是否正常運行
- 若 gateway 當機或重啟中，heartbeats 會靜默失敗；crond 則獨立運作不受影響
- Kiro CLI 可在 gateway 異常時仍執行檢查，並透過 Telegram 通知 owner

## 1. 版本檢查與自動建立 Issue

比對本機安裝版本與 npm 最新版本，若有新版本則自動建立 release notes issue。

```
┌─────────────────────────────────────────────────────┐
│                   版本檢查完整流程                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  openclaw --version   vs   npm show openclaw version│
│                │                                    │
│           版本不同？                                 │
│           ├─ NO  → 結束                             │
│           │                                         │
│           └─ YES → Telegram 通知新版本               │
│                         │                           │
│                         ▼                           │
│    TITLE = "Release notes: OpenClaw <LATEST>"       │
│                         │                           │
│    gh issue list --state all                        │
│    ⚠️  open + closed 都查                           │
│                         │                           │
│                  issue 存在？                        │
│                  ├─ YES → 結束                      │
│                  │                                  │
│                  └─ NO → 建立 issue                 │
│                            - 上游 release tag 連結  │
│                            - zh-TW release notes    │
│                            - Acceptance criteria    │
│                              │                      │
│                              ▼                      │
│                    Telegram 通知 issue URL           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

工具：
- `openclaw --version` — 取得目前安裝版本
- `npm show openclaw version` — 取得 npm 最新版本
- `gh issue list --state all` — 搜尋 open + closed issue，避免重複建立

## 2. 通知機制

透過 Telegram 通知 owner，使用 openclaw 內建訊息功能：

```bash
openclaw message send --channel telegram --target <OWNER_ID> -m "<MESSAGE>"
```

觸發時機：

| 事件 | 通知內容 |
|------|----------|
| 偵測到新版本 | `OpenClaw 有新版本！目前: <CURRENT> → 最新: <LATEST>` |
| 成功建立 issue | `已建立 release notes issue: <ISSUE_URL>` |
