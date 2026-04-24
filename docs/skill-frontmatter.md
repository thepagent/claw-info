---
last_validated: 2026-04-02
validated_by: masami-agent
---

# SKILL.md Frontmatter 欄位說明

OpenClaw 讀取每個 `SKILL.md` 的 frontmatter，將 skill 註冊為 Telegram/Discord slash command。

## 欄位一覽

| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | ✅ | Skill 名稱；自動成為 slash command（如 `name: prcli` → `/prcli`） |
| `description` | ✅ | 顯示於 slash command 選單；LLM 依此自動選用 skill（上限 100 字元） |
| `command-dispatch` | ❌ | 設為 `tool` 可繞過 LLM 組合指令，直接 dispatch 至指定工具 |
| `command-tool` | ❌ | 要呼叫的工具名稱（如 `exec`）；`command-dispatch: tool` 時必填 |
| `command-arg-mode` | ❌ | 參數傳遞方式；`raw` = 原樣傳入（目前唯一支援值） |

來源：[`src/agents/skills/workspace.ts`](https://github.com/openclaw/openclaw/blob/v2026.3.2/src/agents/skills/workspace.ts)（v2026.3.2）
- `name` / `description`：[L686](https://github.com/openclaw/openclaw/blob/v2026.3.2/src/agents/skills/workspace.ts#L686)、[L699](https://github.com/openclaw/openclaw/blob/v2026.3.2/src/agents/skills/workspace.ts#L699)
- `command-dispatch`：[L706](https://github.com/openclaw/openclaw/blob/v2026.3.2/src/agents/skills/workspace.ts#L706)
- `command-tool`：[L720](https://github.com/openclaw/openclaw/blob/v2026.3.2/src/agents/skills/workspace.ts#L720)
- `command-arg-mode`：[L734](https://github.com/openclaw/openclaw/blob/v2026.3.2/src/agents/skills/workspace.ts#L734)

## Dispatch 模式比較

### 預設（經 LLM 判斷）

```
用戶 /skillname args → OpenClaw → LLM 推理 → 呼叫工具 → 回傳結果
```

彈性高但較慢，適合需要 LLM 理解意圖或分析結果的 skill。

### 直接 dispatch（`command-dispatch: tool`）

```
用戶 /skillname args → OpenClaw → 直接呼叫工具(args) → 原樣回傳結果
```

跳過 LLM，速度快、成本低、行為確定。**注意：** `args` 就是完整指令字串，工具不會自動加前綴。

## 重要限制：`command-dispatch` + `exec` 的正確用法

`exec` tool 收到的 `command` 參數 = 用戶輸入的 rawArgs（完整 shell 指令）。

```
/run ls -la        → exec("ls -la")        ✅
/run prcli aws/aws-cdk/pull/123  → exec("prcli aws/aws-cdk/pull/123")  ✅
/prcli aws/aws-cdk/pull/123      → exec("aws/aws-cdk/pull/123")        ❌ 缺少前綴
```

因此 `command-dispatch: tool` + `exec` **只適合** skill name 本身是「shell 指令入口」的場景，即用戶輸入的 args 本身就是完整指令。

## 範例：`run` skill（直接執行任意 shell 指令）

> ⚠️ **安全警告**：`run` skill 允許任何有權限的用戶執行任意 shell 指令，風險極高。
> 建議僅在以下條件下啟用：
> - gateway 設有嚴格的 `allowFrom` 白名單（僅限信任用戶）
> - 或搭配 `exec` 的 `security: allowlist` 模式限制可執行指令
> - 切勿在多用戶或公開 bot 環境中使用

```yaml
---
name: run
description: Execute a shell command directly. Use /run <command> to run any shell command without LLM interpretation.
command-dispatch: tool
command-tool: exec
command-arg-mode: raw
---

# run

Execute any shell command directly via `/run <command>`.

## Examples

\`\`\`
/run prcli aws/aws-cdk/pull/36303
/run opcli cron list
/run ls -la ~
\`\`\`

The command is passed as-is to the shell. No LLM interpretation.
```

用戶輸入 `/run prcli aws/aws-cdk/pull/36303`，OpenClaw 直接執行 `prcli aws/aws-cdk/pull/36303`，原樣回傳輸出。

## Native Slash Command 設定

Slash command 預設在 Telegram/Discord 自動啟用，由 `openclaw.json` 的 `nativeSkills` 控制：

```json
"commands": {
  "nativeSkills": "auto"
}
```

| 值 | 行為 |
|----|------|
| `auto` | TG/Discord 啟用，Slack 停用 |
| `true` | 全部啟用 |
| `false` | 全部停用 |
