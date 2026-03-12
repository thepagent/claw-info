# 升級前自動備份工作流

## 使用場景

每次執行 `openclaw update` 前，Agent 自動觸發 `openclaw backup create --verify`，確保本地狀態、設定、credentials 均已封存並通過完整性驗證，再進行升級。適用於長期運行的 VPS / 伺服器部署，不想在升級後才發現資料遺失。

## 功能依賴

- OpenClaw v2026.3.8+（[#40163](https://github.com/openclaw/openclaw/pull/40163)）
- `openclaw backup create` / `backup verify` 指令

---

## 核心流程

```text
Agent 偵測到升級意圖
（使用者說「升級」/「update」）
          │
          ▼
┌─────────────────────────┐
│  openclaw backup create │  打包 state / config /
│  --output ~/Backups     │  credentials / workspace
│  --verify               │
└──────────┬──────────────┘
           │
    verify 通過？
    ┌───────┴───────┐
   Yes              No
    │                │
    ▼                ▼
openclaw         告知使用者
update           備份失敗，
                 停止升級
```

---

## 實際執行記錄（Linux VPS, v2026.3.8）

### 完整備份 + 立即驗證

```bash
openclaw backup create --output ~/Backups --verify
```

輸出：
```
Backup archive: ~/Backups/2026-03-11T04-36-31.521Z-openclaw-backup.tar.gz
Included 1 path:
- state: ~/.openclaw
Skipped 1 path:
- workspace: ~/.openclaw/workspace (covered by ~/.openclaw)
Created ~/Backups/2026-03-11T04-36-31.521Z-openclaw-backup.tar.gz
Archive verification: passed
```

**關鍵行為：** workspace 位於 state dir 內部時，自動標記為 `covered`，不重複打包，封存檔不膨脹。

### 驗證已有備份

```bash
openclaw backup verify ~/Backups/2026-03-11T04-36-31.521Z-openclaw-backup.tar.gz
```

輸出：
```
Backup archive OK: ~/Backups/2026-03-11T04-36-31.521Z-openclaw-backup.tar.gz
Archive root: 2026-03-11T04-36-31.521Z-openclaw-backup
Created at: 2026-03-11T04:36:31.521Z
Runtime version: 2026.3.8
Assets verified: 1
Archive entries scanned: 1371
```

### 僅備份 config（快速輕量版）

```bash
openclaw backup create --output ~/Backups --only-config
```

封存大小對比：
- 完整 state：7.4 MB
- 只備份 config：1.6 KB

適合只改過 config、不需要備份完整工作區的場景。

---

## 讓 Agent 自動執行：三種方式

### 方式一：對話觸發（最簡單）

在 `AGENTS.md` 或 `SOUL.md` 加入一條規則：

```markdown
## 升級前必做
每次使用者要求執行 openclaw update 前，先執行：
openclaw backup create --output ~/Backups --verify
確認輸出含 "Archive verification: passed" 後才繼續升級。
```

Agent 看到升級意圖時，會自動先備份再繼續。

### 方式二：cron 定期備份（不依賴升級觸發）

```yaml
# openclaw.json
crons:
  - name: weekly-backup
    schedule: "0 3 * * 0"   # 每週日凌晨 3 點
    task: |
      執行 openclaw backup create --output ~/Backups --verify
      確認備份成功後回報結果。
    delivery:
      channel: telegram
```

每週自動備份一次，不依賴手動升級。

### 方式三：HEARTBEAT.md 定期檢查

```markdown
# HEARTBEAT.md
- 檢查 ~/Backups 最新備份是否超過 7 天
- 若超過，執行 openclaw backup create --output ~/Backups --verify
```

Agent 在每次心跳時自動評估是否需要備份，不需要 cron 設定。

---

## Manifest 結構說明

每份備份封存檔內含 `manifest.json`，記錄備份元資料：

```json
{
  "schemaVersion": 1,
  "createdAt": "2026-03-11T04:36:31.521Z",
  "archiveRoot": "2026-03-11T04-36-31.521Z-openclaw-backup",
  "runtimeVersion": "2026.3.8",
  "platform": "linux",
  "options": {
    "includeWorkspace": true,
    "onlyConfig": false
  },
  "paths": {
    "stateDir": "/home/user/.openclaw",
    "configPath": "/home/user/.openclaw/openclaw.json",
    "oauthDir": "/home/user/.openclaw/credentials",
    "workspaceDirs": ["/home/user/.openclaw/workspace"]
  },
  "assets": [...],
  "skipped": [
    {
      "kind": "workspace",
      "reason": "covered",
      "coveredBy": "~/.openclaw"
    }
  ]
}
```

`backup verify` 就是比對 manifest 宣告的 assets 與封存檔內的實際 payload，確保兩者一致。

---

## 常用指令速查

| 指令 | 用途 |
|------|------|
| `openclaw backup create` | 在當前目錄建立時間戳備份 |
| `openclaw backup create --output ~/Backups` | 指定備份目錄 |
| `openclaw backup create --verify` | 建立後立即驗證 |
| `openclaw backup create --only-config` | 只備份 config（1.6KB） |
| `openclaw backup create --no-include-workspace` | 排除 workspace |
| `openclaw backup create --dry-run --json` | 預覽備份計畫不寫檔 |
| `openclaw backup verify <archive>` | 驗證已有備份 |

---

## 注意事項

- 封存檔採**原子寫入**（先寫暫存再 rename），失敗不留殘缺檔案
- **不會覆蓋**已存在的同名封存檔，每次都建立新的時間戳版本
- 輸出路徑**不能在備份來源目錄內**（系統會自動偵測並拒絕）
- `backup restore` 尚未實作（v2026.3.8），恢復需手動解壓縮

---

## 延伸閱讀

- [OpenClaw CLI Backup 文件](https://docs.openclaw.ai/cli/backup)
- [cron-automated-workflows.md](./cron-automated-workflows.md) — 定期任務設定參考
- 原始 PR：[#40163](https://github.com/openclaw/openclaw/pull/40163)
