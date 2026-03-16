# usecases: resumeSessionId — 跨 Session 恢復 ACP 編程代理上下文

**對應版本：** OpenClaw v2026.3.11
**功能：** `sessions_spawn` 新增 `resumeSessionId` 參數，可恢復之前的 Codex 或 Claude Code session，agent 透過 `session/load` 載入歷史 context，從中斷點接著做。

---

## 問題場景

你指派 Codex 分析一個複雜模組，做到一半 gateway 重啟了；或者一個跨天的重構任務，明天想繼續——沒有 `resumeSessionId` 的話，每次都要重新解釋背景。有了它，agent 接回原本的 session，context 完整保留。

---

## 支援的 Agent

| Agent | agentId | Session 存放位置 |
|---|---|---|
| Codex | `"codex"` | `~/.codex/sessions/YYYY/MM/DD/` |
| Claude Code | `"claude"` | `~/.claude/projects/<normalized-project-path>/` |

兩者都實作 `session/load` 協議，`resumeSessionId` 行為一致。

> `<normalized-project-path>` 的生成規則：將 cwd 的每個 `/` 與 `.` 都替換為 `-`。
> 例如 cwd 為 `/root/.openclaw/workspace` → `-root--openclaw-workspace`

> **注意：** Claude Code 啟動和完成的時間明顯比 Codex 長（實測約 60–90 秒 vs 20–30 秒）。orchestrator 輪詢 session 狀態時應給足等待時間，避免誤判為失敗。

---

## 流程

### Step 1：啟動初始 Session

```json
{
  "task": "閱讀 src/auth.ts，找出 token 刷新邏輯中可能的 race condition，列出具體行號和原因",
  "runtime": "acp",
  "agentId": "codex",
  "mode": "run"
}
```

回傳：
```json
{
  "status": "accepted",
  "childSessionKey": "agent:codex:acp:af9e8993-b09b-49dd-aac6-7645b245016c",
  "mode": "run"
}
```

### Step 2：取得 Session UUID

> ⚠️ **關鍵陷阱：** `resumeSessionId` 需要的是 **agent 自身的 session UUID**，不是 OpenClaw 的 `childSessionKey`，也不是 acpx 的 `recordId`——三者長得相似但不同。

| ID | 來源 | 格式範例 | 用途 |
|---|---|---|---|
| `childSessionKey` | `sessions_spawn` 回傳 | `agent:codex:acp:af9e8993-...` | 查 `sessions.json` 的索引 key |
| `acpxSessionId` | `sessions.json` → `acp.identity.acpxSessionId` | `019cf1af-0283-7202-a7bf-...`（純 UUID）| 傳給 `resumeSessionId` 的正確值 ✅ |
| `recordId` | acpx 內部記錄 | 數字或短字串 | 僅 acpx 內部使用，**不可**傳給 `resumeSessionId` |

**方法 A：從 sessions.json 讀取（推薦，並行安全）**

Session 完成後，以 `childSessionKey` 為索引查 `~/.openclaw/agents/<agentId>/sessions/sessions.json`，取出 `acp.identity.acpxSessionId`：

```bash
# 以 Codex 為例，將 childSessionKey 換成實際值
# 路徑依實際安裝位置而定，${HOME} 對應當前登入用戶的 home 目錄
python3 -c "
import json, os
with open(os.path.expanduser('~/.openclaw/agents/codex/sessions/sessions.json')) as f:
    d = json.load(f)
key = 'agent:codex:acp:<your-child-session-uuid>'
print(d[key]['acp']['identity']['acpxSessionId'])
"
```

Claude Code 同理，路徑改為 `~/.openclaw/agents/claude/sessions/sessions.json`。

orchestrator 內可用 `exec` tool 執行上述指令，把 UUID 存入變數後傳給下一個 `sessions_spawn`。

**方法 B：手動查文件名**

```bash
# Codex
ls -t ~/.codex/sessions/YYYY/MM/DD/
# rollout-2026-03-15T21-28-24-019cf1af-0283-7202-a7bf-0b336c7e5dcc.jsonl
#                                ↑ 這段就是 resumeSessionId

# Claude Code
ls -lt ~/.claude/projects/<normalized-project-path>/
# 最新的 .jsonl 文件名（不含副檔名）即為 resumeSessionId
```

> 並行跑多個 session 時，`ls -t | head -1` 可能取錯。建議使用方法 A。

### Step 3：Resume

```json
{
  "task": "根據剛才找到的 race condition，實作修正並補上對應的單元測試",
  "runtime": "acp",
  "agentId": "codex",
  "mode": "run",
  "resumeSessionId": "019cf1af-0283-7202-a7bf-0b336c7e5dcc",
  "runTimeoutSeconds": 300
}
```

> 建議 `runTimeoutSeconds`：Codex 設 `120–300`，Claude Code 設 `300–600`。Claude Code 啟動較慢（實測 60–90 秒），預設值偏短容易誤判超時。

Resume 後，agent 通常會繼續寫入同一個 session 文件，可作為成功接回的重要驗證訊號。

---

## 實測記錄（2026-03-15，VPS icern）

### Codex

**Session 1：**
```
task:     記住這個字串：「RESUME-TEST-CODEX」。回覆「已記住」，然後停止。
UUID:     019cf1af-0283-7202-a7bf-0b336c7e5dcc
state:    idle ✅（約 25 秒）
response: 已記住
```

**Resume：**
```
task:     你之前記住了一個字串，那個字串是什麼？
response: RESUME-TEST-CODEX ✅
```

### Claude Code（第三方 proxy）

**Session 1：**
```
task:     記住這個字串：「RESUME-TEST-CLAUDE」。回覆「已記住」，然後停止。
UUID:     53c3c86d-4d27-40c4-a056-67d1006d9bd2
state:    idle ✅（約 75 秒）
response: 已記住
```

**Resume：**
```
task:     你之前記住了一個字串，那個字串是什麼？
response: 「RESUME-TEST-CLAUDE」 ✅
```

---

## VPS / Proxy 環境的額外設定

若 OpenClaw 跑在 VPS 且 Claude Code 走第三方 Anthropic 相容 proxy，需確保 gateway 繼承正確的環境變數，否則 agent 啟動時拿不到 API key（`acpx exited with code 1`）。

`~/.openclaw/.env` 加入：

```bash
ANTHROPIC_BASE_URL=https://your-proxy.example.com/api/anthropic
ANTHROPIC_AUTH_TOKEN=<your-key>
```

然後重啟 gateway：
```bash
openclaw gateway restart
```

Codex 用 OpenAI key，通常不需要額外設定。

---

## 常見錯誤

| 錯誤 | 原因 | 解法 |
|---|---|---|
| `acpx exited with code 4` | `resumeSessionId` 傳了錯誤的 UUID（如 acpx recordId）| 改用方法 A 從 `sessions.json` 取 `acpxSessionId` |
| `acpx exited with code 1` | Claude Code auth 失敗，key 未被 gateway 繼承 | 把 key 寫入 `~/.openclaw/.env`，重啟 gateway |
| `acpx exited with code 5` | agent 初始化失敗（未安裝或 auth 設定問題）| 先確認 agent CLI 可獨立執行 |

---

## 適用場景

- **Gateway 重啟後接續** — 服務重啟不等於放棄進度
- **長任務分段執行** — 把複雜任務切成幾個 session，每次 resume 繼續
- **跨裝置接力** — 桌面上開的 ACP session，透過手機 Telegram 繼續下一步
- **Idle timeout 恢復** — agent 閒置被回收後，重新接回不失 context

---

## 小結

`resumeSessionId` 讓 ACP 編程 session 從「跑完即忘」變成「可持續接力」。取 UUID 最可靠的方式：以 `childSessionKey` 查 `sessions.json`，取 `acp.identity.acpxSessionId`——並行安全，不依賴文件排序。
