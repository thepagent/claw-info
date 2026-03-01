# acpx → kiro relay 整合文件

## 目標
Telegram DM → kiro-cli 直接對話

## 現狀（可用）✅

**Klaw bot DM** → klaw agent（embedded LLM）→ `exec relay.sh` → `acpx kiro prompt` → kiro-cli → 回應 → Telegram

- 功能正常，對話持久化（persistent session `klaw-tg`）
- **非串流**：Telegram 不支援 thread binding
- **需要 acpx patch**：kiro-cli 輸出格式不符 ACP spec，需 workaround（見下方）

---

## 架構

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐
│ Telegram │────▶│ klaw agent (gpt-5.2)    │────▶│ relay.sh     │────▶│ acpx         │────▶│ kiro-cli  │
│          │     │                         │     │              │     │ (ACP client) │     │ acp       │
│ 用戶訊息 │     │ 1. message_send         │     │ acpx ensure  │     │              │     │ (session  │
│          │     │    【轉接Kiro中...】     │     │ acpx prompt  │     │ JSON-RPC     │     │  klaw-tg) │
│          │     │ 2. exec relay.sh        │     │  -s klaw-tg  │     │ over stdio   │     │           │
│          │     │ 3. message_send(回應)   │     │              │     │              │     │           │
└──────────┘     └─────────────────────────┘     └──────────────┘     └──────────────┘     └─────┬─────┘
     ▲                                                                                             │
     └─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              kiro 回應
```

---

## 關鍵設定

### klaw SOUL.md (`~/.openclaw/workspace-klaw/SOUL.md`)
```
FOR ALL messages:
  1. message_send【轉接Kiro中...】
  2. exec relay.sh "<user message>"
  3. message_send(exec output)

SPECIAL: /new → exec acpx sessions new, message_send【初始化完成】
```

### relay.sh (`~/.openclaw/workspace-klaw/relay.sh`)
```bash
ACPX=~/.npm-global/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx
$ACPX kiro sessions ensure --name klaw-tg 2>/dev/null
$ACPX kiro prompt -s klaw-tg "$1" 2>/dev/null | grep -v '^\[' | grep -v '^$' | head -50
```

### acpx config (`~/.acpx/config.json`)
```json
{ "agents": { "codex": { "command": "..." } } }
```
kiro 使用預設 `kiro-cli acp`（無 override）。

### klaw agent model
- Primary: `openai-codex/gpt-5.2`
- Auth: `~/.openclaw/agents/klaw/agent/auth-profiles.json`（同 main，7 profiles）
- models.json: 已移除（繼承 global 設定）

---

## 為何用 relay.sh 而非 sessions_spawn

| 方法 | 問題 |
|------|------|
| `sessions_spawn` | klaw LLM 自作主張：改寫訊息、自行 debug、不照 SOUL.md |
| `exec relay.sh` | 同步 shell，輸出即 kiro 回應，LLM 無發揮空間 ✅ |

---

## 已知問題 / 限制

### 1. 非串流
- Telegram 不支援 thread binding（Discord 才支援）
- 目前：blocking exec，等 kiro 完成才回覆

### 2. 無 conversation continuity ✅ 已解決
- 改用 `acpx kiro prompt -s klaw-tg`（persistent session）
- kiro 記住對話歷史，`/new` 時 `sessions new` 重置

### 3. klaw LLM 偶爾不穩定
- SOUL.md 指示有時被忽略
- 解法：truncate session 讓 SOUL 重新注入

---

## 串流研究結論

| 方案 | 串流 | 狀態 |
|------|------|------|
| `exec relay.sh`（acpx exec）| ❌ blocking | ✅ 穩定可用 |
| `sessions_spawn`（klaw LLM）| ❌ blocking | ⚠️ 不穩定 |
| ACP session binding（Telegram）| ✅ 真串流 | ❌ Telegram 不支援 |
| ACP session binding（Discord）| ✅ 真串流 | ✅ 支援（未測試）|

---

## 檔案位置

```
~/.openclaw/workspace-klaw/SOUL.md
~/.openclaw/workspace-klaw/BOOTSTRAP.md
~/.openclaw/workspace-klaw/relay.sh
~/.openclaw/agents/klaw/agent/auth-profiles.json
~/.openclaw/agents/klaw/agent/models.json.bak   # 已停用
~/.acpx/config.json
~/.openclaw/openclaw.json
```

---

## Next Steps

1. **等待 kiro-cli 修正**：已回報 [kirodotdev/Kiro#6131](https://github.com/kirodotdev/Kiro/issues/6131)，kiro-cli 輸出裸 JSON 不符合 ACP spec，修正後可移除 acpx patch
2. **openclaw PR #28817 / #29547**：若 kiro 修正，這兩個 PR 合併後可直接用 `sessions_spawn(runtime:"acp-standard")` 取代 relay.sh，架構更乾淨
3. **Discord 串流**：測試 `/acp spawn kiro --thread here`

---

## kiro-cli ACP 相容性問題

kiro-cli 1.26.2 輸出裸 JSON `{"content":"...","type":"text"}`，不符合 ACP spec 要求的 `session/update` JSON-RPC 2.0 notification。

- **Bug report**：[kirodotdev/Kiro#6131](https://github.com/kirodotdev/Kiro/issues/6131)
- **我們的 workaround**：acpx patch（`normalizeAgentOutput()` TransformStream）
- **Workaround repo**：[thepagent/acpx feat/kiro-agent](https://github.com/thepagent/acpx/tree/feat/kiro-agent)
- **相關 openclaw PR**：[#28817](https://github.com/openclaw/openclaw/pull/28817)、[#29547](https://github.com/openclaw/openclaw/pull/29547)（若 kiro 修正後可直接用）
