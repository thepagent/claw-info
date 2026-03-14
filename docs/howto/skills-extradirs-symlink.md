# OpenClaw Skills Symlink 載入問題與 `extraDirs` 解法

本文說明：當你用 symlink 把外部 skills repo 掛進 OpenClaw 的技能目錄時，為什麼在 2026-03-07 之後可能載入失敗，以及正確的替代做法 `skills.load.extraDirs`。

## TL;DR

- 2026-03-07 之後，OpenClaw 會追蹤 skill 路徑的 `realpath`。
- 若 symlink 解析後的真實路徑落在允許目錄外，skill 會被拒絕載入。
- 常見症狀是 log 出現：`resolved path is outside allowed directory`。
- 這不是掃描階段看不到 symlink，而是後續的 canonical path 驗證拒絕了它。
- 正確做法不是繼續把外部 skill symlink 進來，而是用 `skills.load.extraDirs` 明確告訴 OpenClaw 去掃描外部技能目錄。
- `extraDirs` 應指向「技能類別目錄」，不是更上層的父目錄。

## 症狀

若透過中央管理技能的方式，並使用 symlink 將實際檔案指向 AI 工具（如 OpenClaw）的全域技能目錄，在 2026-03-07 的安全性更新後可能遇到載入失敗：

```text
Skipping skill at /path/to/skill: resolved path is outside allowed directory
```

## 問題原因

在安全性更新後，OpenClaw 不只看你放進技能目錄的「symlink 表面路徑」，而會追蹤到 symlink 實際指向的真實路徑，再檢查該路徑是否仍位於允許的目錄內。

若 symlink 指到外部 repo 或其他未授權位置，OpenClaw 會拒絕載入。

相關來源：

- [`253e159`](https://github.com/openclaw/openclaw/commit/253e159700599a04d971ae9b804525cd434b82cf)
- [`resolveContainedSkillPath()`](https://github.com/openclaw/openclaw/blob/main/src/agents/skills/workspace.ts#L201-L221)
- [`tryRealpath()`](https://github.com/openclaw/openclaw/blob/main/src/agents/skills/workspace.ts#L179-L185)
- [`isPathInside()`](https://github.com/openclaw/openclaw/blob/main/src/agents/sandbox-paths.test.ts#L22)

## 正確解法：使用 `skills.load.extraDirs`

若你的 skill 實際存放在外部 repo，不要再依賴 symlink 把它掛進 OpenClaw 預設技能目錄。

改用：

```bash
openclaw config set skills.load.extraDirs '[
  "<skills-repo>/skills/git",
  "<skills-repo>/skills/infra",
  "<skills-repo>/skills/productivity",
  "<skills-repo>/skills/learning"
]'
```

然後重啟 gateway：

```bash
openclaw gateway restart
```

這種方式的意思是：直接把外部技能類別目錄加入掃描來源，而不是透過 symlink 偽裝成內部路徑。

## `extraDirs` 路徑規則

OpenClaw 的技能掃描使用 [`listChildDirectories()`](https://github.com/openclaw/openclaw/blob/main/src/agents/skills/workspace.ts#L151-L177)，只掃描一層深度的直接子目錄，並在該層尋找 `SKILL.md`。

因此 `extraDirs` 應該指向：

- ✅ 技能類別目錄，例如 `<skills-repo>/skills/git`
- ✅ 技能類別目錄，例如 `<skills-repo>/skills/infra`
- ❌ 不要指向 `<skills-repo>/skills/`
- ❌ 不要指向 `<skills-repo>/`

原因很簡單：

- 指向類別目錄時，一層掃描就能找到每個 skill 子目錄裡的 `SKILL.md`
- 指向更上層父目錄時，一層掃描只會看到 `git/`、`infra/`、`productivity/` 這類資料夾本身，還到不了真正 skill 所在位置

## 技術細節

技能載入的路徑驗證可以分成兩階段。

### 階段一：目錄掃描

在掃描階段，OpenClaw 會列出子目錄。若某個 entry 是 symlink，且其目標是目錄，仍可能被加入掃描結果。

也就是說，**symlink 並不是在第一階段就被拒絕**。

```typescript
if (entry.isSymbolicLink()) {
  try {
    if (fs.statSync(fullPath).isDirectory()) {
      dirs.push(entry.name);
    }
  } catch {
    // ignore broken symlinks
  }
}
```

### 階段二：canonical path 驗證

真正拒絕外部 symlink 的地方，是後續路徑驗證鏈：

1. `resolveContainedSkillPath()` 呼叫 `tryRealpath()`
2. `tryRealpath()` 解析 symlink 的真實檔案系統路徑
3. `isPathInside()` 檢查該真實路徑是否仍位於允許根目錄內

若真實路徑不在允許範圍內，skill 就會被略過，並出現前面的 warning。

## 操作步驟

### 1. 查看目前設定

```bash
openclaw config get skills.load.extraDirs
```

### 2. 設定外部技能類別目錄

```bash
openclaw config set skills.load.extraDirs '[
  "<skills-repo>/skills/git",
  "<skills-repo>/skills/infra",
  "<skills-repo>/skills/productivity",
  "<skills-repo>/skills/learning"
]'
```

### 3. 重啟 gateway

```bash
openclaw gateway restart
```

### 4. 驗證技能是否正常載入

```bash
openclaw skills list --eligible
```

## Troubleshooting

### 症狀：設定了 `extraDirs` 但還是找不到 skill

可能原因：

- `extraDirs` 指到了父目錄，不是技能類別目錄
- 目標 skill 目錄下沒有 `SKILL.md`
- gateway 尚未重啟，仍在使用舊設定

建議檢查：

```bash
openclaw config get skills.load.extraDirs
openclaw gateway restart
openclaw skills list --eligible
```

### 症狀：仍然看到 `Skipping` 警告

檢查 warning：

```bash
openclaw skills list --eligible 2>&1 | grep "Skipping"
```

若仍出現 `resolved path is outside allowed directory`，代表某些 skill 來源仍然依賴外部 symlink，尚未完全改成 `extraDirs` 掃描。

### 症狀：技能有載入，但來源不是預期目錄

檢查來源：

```bash
openclaw skills list --eligible | grep "openclaw-extra"
```

若你預期 skill 來自外部額外目錄，通常應能看到 `openclaw-extra`。

## See also

- [Skills 系統（打包、版本控制、測試）](../core/skills-system.md)
- [SKILL.md Frontmatter 欄位說明](../skill-frontmatter.md)
- [Troubleshooting（常見故障排除）](../troubleshooting.md)
