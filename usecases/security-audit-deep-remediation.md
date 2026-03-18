# Security Audit --deep 實戰修復指南（skills quarantine、gateway password 移出 config）

## TL;DR

- `openclaw security audit --deep` 會比一般 audit 多做更深入的風險探測，常能抓出高風險 skill 與設定弱點。
- 本文記錄一次真實修復流程：先發現 2 個 critical，再用可回滾方式把風險降到 0 critical。
- 本次修復包含兩件事：**隔離高風險 skills**、**把 gateway password 從 config 移到 LaunchAgent 環境變數**。
- 修復後重新執行 deep audit，結果從 `2 critical · 4 warn · 2 info` 降到 `0 critical · 3 warn · 2 info`。
- 這份流程適合單機 / 個人 OpenClaw 部署者先處理最明顯的高風險項目；不涉及 firewall、SSH 或 OS 層硬化。

---

## 使用場景

很多人跑完：

```bash
openclaw security audit --deep
```

會看到一堆告警，但不知道：

1. 哪些要先處理？
2. 怎麼修才不會把環境弄壞？
3. 哪些可以先用「隔離 / 搬移」而不是直接刪？

本文示範一個**先修 critical、先保留回滾能力**的最小安全流程。

---

## 本次真實環境

- OS：macOS 15.7.4
- OpenClaw：2026.3.13
- Gateway：本機 LaunchAgent，loopback only
- 使用模式：個人 assistant，但有 Telegram / Discord 群組入口

> 重點：這不是 hostile multi-tenant 隔離環境，而是個人 assistant 模式下的實戰修復。

---

## 初始狀態：deep audit 發現什麼

執行：

```bash
openclaw security audit --deep
```

初始摘要：

```text
Summary: 2 critical · 4 warn · 2 info
```

### Critical 1：高風險 skill `capability-evolver`

掃描器偵測到多個高風險模式，例如：

- `child_process` shell execution
- environment variable access + network send

這不一定等於惡意，但代表該 skill 具有：

- 執行外部指令的能力
- 可能讀取環境變數
- 可能往外送資料

若來源不完全可信，應先隔離再說。

### Critical 2：高風險 skill `tavily-search`

同樣被偵測到：

- environment variable access + network send

對 search 類 skill 而言，這可能是正常需求；但若你沒有明確審過它，就不應在高信任 runtime 中直接保留。

### Warn：gateway password 存在 config 檔

audit 顯示：

- `gateway.auth.password` 仍存在 `~/.openclaw/openclaw.json`

這代表只要有人能讀 config 檔，就能取得 gateway password。

---

## 修復策略

本次採用的原則是：

### 1. 先修 critical，不一次動太多

先把：

- 高風險 skills
- 明文落地 secret

處理掉，再看剩餘 warning。

### 2. 優先可回滾

不直接刪除 skills，而是：

- **移到 quarantine 目錄**

不直接重建整份 config，而是：

- 備份原 config
- 將 password 移到 LaunchAgent env

### 3. 不碰 OS 層

這次**不處理**：

- firewall
- FileVault
- SSH / remote access
- Tailscale exposure policy

原因是這些需要更高的人類確認與存取路徑評估。

---

## Step 0：先備份

先建立可回滾備份：

```bash
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$HOME/.openclaw/backups/security-fix-$TS"
mkdir -p "$BACKUP_DIR"

cp -a "$HOME/.openclaw/openclaw.json" "$BACKUP_DIR/openclaw.json.bak"
cp -a "$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist" \
  "$BACKUP_DIR/ai.openclaw.gateway.plist.bak"
```

這樣就算後面搬移 password 或改 LaunchAgent 出問題，也能快速回復。

---

## Step 1：隔離高風險 skills

### 做法

建立 quarantine 目錄，將 skills 移出原載入路徑：

```bash
QDIR="$HOME/.openclaw/quarantine-skills"
mkdir -p "$QDIR"
chmod 700 "$QDIR"

mv "/Users/tboydar/.openclaw/workspace/skills/evolver" "$QDIR/"
mv "/Users/tboydar/.openclaw/workspace/skills/tavily-search" "$QDIR/"
```

### 為什麼不用直接刪？

因為 deep audit 的 `dangerous-exec` / `env-harvesting` 是**高風險訊號**，不是自動證明惡意。

先 quarantine 的好處：

- 風險先降下來
- 之後還能人工 review 程式碼
- 要恢復也只要 `mv` 回去

### 回滾方式

```bash
mv "$HOME/.openclaw/quarantine-skills/evolver" \
   "/Users/tboydar/.openclaw/workspace/skills/"

mv "$HOME/.openclaw/quarantine-skills/tavily-search" \
   "/Users/tboydar/.openclaw/workspace/skills/"
```

---

## Step 2：把 gateway password 從 config 移到 LaunchAgent env

### 目標

把：

- `~/.openclaw/openclaw.json` 裡的 `gateway.auth.password`

改成：

- `~/Library/LaunchAgents/ai.openclaw.gateway.plist` 的 `EnvironmentVariables.OPENCLAW_GATEWAY_PASSWORD`

### 為什麼這樣做？

因為 config 通常：

- 更容易被備份
- 更容易被讀取
- 更常被 diff / 複製 / 分享

而 env 雖然不是完美祕密管理方案，但至少能把 secret 從一般設定檔中抽離。

> Security note：將 secret 移到 LaunchAgent environment variables 屬於**風險降低（risk mitigation）**，不是終極祕密保護。對更高安全要求的環境，仍應優先考慮 macOS Keychain 或專用 Secret Manager。

### 實作範例（Python）

> 注意：下列腳本示範的是「實務上夠用的最小搬移流程」，不是完整事務型（atomic）配置遷移。若你要把中斷風險降到更低，可採用 temp file + replace 寫法，並在修改前先驗證 target plist 路徑與格式。

```python
import json, plistlib, os

home = os.path.expanduser('~')
conf_path = os.path.join(home, '.openclaw', 'openclaw.json')
plist_path = os.path.join(home, 'Library/LaunchAgents/ai.openclaw.gateway.plist')

with open(conf_path) as f:
    data = json.load(f)

password = (((data.get('gateway') or {}).get('auth') or {}).get('password'))
if not password:
    raise SystemExit('No password in config')

with open(plist_path, 'rb') as f:
    plist = plistlib.load(f)

env = plist.get('EnvironmentVariables', {}) or {}
env['OPENCLAW_GATEWAY_PASSWORD'] = password
plist['EnvironmentVariables'] = env

with open(plist_path, 'wb') as f:
    plistlib.dump(plist, f)

# remove password from config
if 'gateway' in data and 'auth' in data['gateway'] and 'password' in data['gateway']['auth']:
    del data['gateway']['auth']['password']
    if not data['gateway']['auth']:
        del data['gateway']['auth']

with open(conf_path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
```

### 重啟 gateway

```bash
launchctl unload "$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
launchctl load "$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
```

或：

```bash
openclaw gateway restart
```

> 若你用的是 LaunchAgent，最好確認 service 實際吃的是哪份 config / env。

---

## Step 3：驗證修復結果

### 驗證 gateway 是否正常

除了 `status`，也建議補看啟動後的 log，避免漏掉短暫的重啟失敗循環或 env 未生效問題。

```bash
openclaw gateway log
```


```bash
openclaw gateway status
```

預期至少要看到：

- runtime running
- RPC probe ok
- bind 仍維持原本設定

### 再跑一次 deep audit

```bash
openclaw security audit --deep
```

本次真實結果：

```text
修復前：2 critical · 4 warn · 2 info
修復後：0 critical · 3 warn · 2 info
```

這代表：

- 高風險 skills 不再被掃到
- gateway password in config 的 warning 已消失

---

## 修復後還剩什麼 warning？

這次沒有處理的項目包括：

### 1. `gateway.trustedProxies` 未設定

如果 Control UI 經過 reverse proxy，應補 trusted proxies；若只在本機 loopback 使用，可先不動。

### 2. multi-user / shared trust boundary 警告

若你同時開：

- Telegram 群組
- Discord 群組
- runtime tools（exec / process）
- 非 sandbox 環境

deep audit 會提醒：這不是嚴格隔離的多租戶安全模型。

### 3. `operator.read` scope 導致 probe degraded

這是可觀察性問題，不是這輪最優先的 critical。

---

## 什麼情況適合照本文做？

### ✅ 適合

- 你剛跑完 `openclaw security audit --deep`
- 看到少數 critical，想先快速降風險
- 你想保留回滾能力
- 你不想一口氣動 OS 安全層

### ❌ 不適合

- 你要做完整主機硬化（firewall / FileVault / SSH）
- 你是多人共用 / 多租戶環境
- 你根本不確定 skill 來源與用途，卻又想立刻恢復它們

---

## Troubleshooting

### 症狀：移走 skills 後某些功能消失

原因：

- 該 runtime 原本就依賴被 quarantine 的 skill

做法：

- 先確認是否真的需要該 skill
- 手動 review skill 程式碼後再決定是否移回

### 症狀：gateway 重啟後連不上

檢查：

```bash
openclaw gateway status
```

若是 env 沒生效：

- 檢查 LaunchAgent plist 的 `EnvironmentVariables`
- 確認有重新 load / restart

### 症狀：deep audit 仍顯示 password in config

原因可能是：

- 移除 config password 後沒有成功寫回檔案
- service 實際使用的不是你以為的 config 路徑

先確認：

```bash
openclaw gateway status
```

看清楚：

- Config (cli)
- Config (service)

---

## 最小修復清單

如果你只想先把 critical 壓下來，最小步驟是：

1. 備份 `openclaw.json` 與 LaunchAgent plist
2. quarantine 高風險 skills
3. 將 gateway password 從 config 移到 env
4. 重啟 gateway
5. 重跑 `openclaw security audit --deep`

---

## 小結

`openclaw security audit --deep` 真正有價值的地方，不只是列出警告，而是幫你找到：

- 哪些 skill 超出你目前的信任邊界
- 哪些 secret 還躺在不該躺的位置

這次實戰證明：

- 先 quarantine，再 review
- 先抽離明文 secret，再驗證服務

就能在**不大改系統、不碰 OS 層**的情況下，把風險從 `2 critical` 直接降到 `0 critical`。

若下一步還要繼續補強，再處理：

- sandbox
- `fs.workspaceOnly`
- trusted proxies
- FileVault / firewall

會更合理。


---

## See also

- [backup-before-upgrade.md](./backup-before-upgrade.md) — 升級前先備份的自動化做法
- [subagent-orchestration.md](./subagent-orchestration.md) — 多 agent 任務編排實戰
- [OpenClaw troubleshooting](../docs/troubleshooting.md) — 常見故障排查
