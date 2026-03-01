# OpenClaw × Codex ACP 整合指南

讓 OpenClaw agent（如 guan-yu）透過 `acpx codex` 呼叫 Codex，實現對話持久化。

---

## 架構概覽

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────┐     ┌───────────────────┐
│ Telegram │────▶│ guan-yu agent           │────▶│ acpx codex   │────▶│ codex-acp         │
│          │     │ (openclaw)              │     │              │     │ (@zed-industries) │
│ 用戶訊息 │     │ exec acpx codex prompt  │     │ session mgmt │     │ ACP JSON-RPC      │
└──────────┘     └─────────────────────────┘     └──────────────┘     └───────────────────┘
```

---

## 與 kiro ACP 完全相同的模式

`acpx` 內建 codex 支援，用法與 kiro 一致：

| 操作 | kiro | codex |
|------|------|-------|
| 建立 session | `acpx kiro sessions ensure --name <n>` | `acpx codex sessions ensure --name <n>` |
| 發送 prompt | `acpx kiro prompt -s <n> "<msg>"` | `acpx codex prompt -s <n> "<msg>"` |
| 一次性執行 | `acpx kiro exec "<msg>"` | `acpx codex exec "<msg>"` |
| 重置 session | `acpx kiro sessions new --name <n>` | `acpx codex sessions new --name <n>` |

---

## 前置需求

- `codex` CLI 已安裝並授權
- `@zed-industries/codex-acp` 已安裝（`npm i -g @zed-industries/codex-acp`）
- `/usr/local/bin/codex-acp.real` symlink 正確指向實際 binary

### 修復 codex-acp wrapper（若損壞）

```bash
REAL_BIN=$(find ~/.npm-global -path "*codex-acp-linux-x64/bin/codex-acp" | head -1)
sudo ln -sf "$REAL_BIN" /usr/local/bin/codex-acp.real
```

驗證：
```bash
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | /usr/local/bin/codex-acp | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['agentInfo'])"
```

---

## ACPX 路徑

```bash
ACPX=/home/pahud/.npm-global/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx
```

---

## 使用方式

```bash
# 建立/確保 session
$ACPX codex sessions ensure --name guan-yu-tg

# 發送 prompt（持久 session）
$ACPX codex prompt -s guan-yu-tg "你好" 2>/dev/null | grep -v '^\[' | grep -v '^$'

# 一次性（無 session）
$ACPX codex exec "what is 2+2" 2>/dev/null | grep -v '^\[' | grep -v '^$'

# 重置 session
$ACPX codex sessions new --name guan-yu-tg
```

---

## guan-yu SOUL.md 整合

在 SOUL.md 加入：

```markdown
## /codex 指令

ACPX=/home/pahud/.npm-global/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx

收到 `/codex <prompt>` 時：
1. exec: `$ACPX codex sessions ensure --name guan-yu-tg 2>/dev/null && $ACPX codex prompt -s guan-yu-tg "<prompt>" 2>/dev/null | grep -v '^\[' | grep -v '^$'`
2. 回傳輸出。

收到 `/codex-new` 時：
1. exec: `$ACPX codex sessions new --name guan-yu-tg 2>/dev/null`
2. 回傳【Codex session 已重置】。
```

---

## ~~relay 腳本（已廢棄）~~

`codex-relay.sh` 不再需要。`acpx codex` 已內建 session 管理，無需手動維護 UUID 檔案。

---

## 常見問題

| 問題 | 原因 | 解法 |
|------|------|------|
| `codex-acp.real: No such file` | wrapper symlink 損壞 | 見上方修復步驟 |
| `[error] RUNTIME: Resource not found` | session 首次 load 失敗 | 正常，acpx 自動 fallback 建新 session |
| 無輸出 | codex 未授權 | `codex login` |
