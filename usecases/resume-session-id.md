# usecases: resumeSessionId — 跨 Session 恢復 ACP 編程代理上下文

**對應版本：** OpenClaw v2026.3.11
**功能：** `sessions_spawn` 新增 `resumeSessionId` 參數，可恢復之前的 Codex 或 Claude Code session，agent 透過 `session/load` 載入歷史 context，從中斷點接著做。

---

## 問題場景

你指派 Codex 分析一個複雜模組，做到一半 gateway 重啟了；或者一個跨天的重構任務，明天想繼續——沒有 `resumeSessionId` 的話，每次都要重新解釋背景。

有了它，agent 接回原本的 session，context 完整保留。

---

## 支援的 Agent

| Agent | agentId | Session 存放位置 |
|---|---|---|
| Codex | `"codex"` | `~/.codex/sessions/YYYY/MM/DD/` |
| Claude Code | `"claude"` | `~/.claude/projects/<project-path>/` |

兩者都實作 `session/load` 協議，`resumeSessionId` 行為一致。

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

**方法 A：orchestrator 自動取（推薦）**

Session 完成後，直接從 agent 的 sessions 目錄讀最新文件名：

```bash
# Codex
ls -t ~/.codex/sessions/$(date +%Y/%m/%d)/ | head -1 | sed 's/rollout-[^-]*-[^-]*-[^-]*-[^-]*-//' | sed 's/.jsonl//'

# Claude Code
ls -t ~/.claude/projects/-root--openclaw-workspace/ | head -1 | sed 's/.jsonl//'
```

或在 orchestrator agent 內用 shell exec tool 執行上述指令，把 UUID 存入變數後傳給下一個 `sessions_spawn`。

**方法 B：手動查**

```bash
# Codex
ls -t ~/.codex/sessions/YYYY/MM/DD/
# rollout-2026-03-15T21-28-24-019cf1af-0283-7202-a7bf-0b336c7e5dcc.jsonl
#                                ↑ 這段就是 resumeSessionId

# Claude Code
ls -lt ~/.claude/projects/-root--openclaw-workspace/
# 最新的 .jsonl 文件名（不含副檔名）即為 resumeSessionId
```

### Step 3：Resume

```json
{
  "task": "根據剛才找到的 race condition，實作修正並補上對應的單元測試",
  "runtime": "acp",
  "agentId": "codex",
  "mode": "run",
  "resumeSessionId": "019cf1af-0283-7202-a7bf-0b336c7e5dcc"
}
```

Resume 成功後，agent 會繼續寫入**同一個** session 文件，而不是建立新的——這是確認接回成功的最直接方式。

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

Resume 後 Claude Code 繼續寫入同一個 `53c3c86d...jsonl`，確認接回原 session。

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
| `acpx exited with code 4` | `resumeSessionId` 傳了錯誤的 UUID（如 acpx recordId）| 去 agent 的 sessions 目錄找正確的 JSONL 文件名 |
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

`resumeSessionId` 讓 ACP 編程 session 從「跑完即忘」變成「可持續接力」。最容易踩的坑只有一個：**UUID 取錯**。記住：

- Codex → `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<UUID>.jsonl`
- Claude Code → `~/.claude/projects/<path>/<UUID>.jsonl`

文件名裡的 UUID 就是 `resumeSessionId`，對了就通。
