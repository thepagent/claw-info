# OpenClaw Skills Symlink 載入問題與 `extraDirs` 解法

本文說明：當你用 symlink 把外部 skills repo 掛進 OpenClaw 的技能目錄時，為什麼在 2026-03-07 之後可能載入失敗，以及正確的替代做法 `skills.load.extraDirs`。

## 目錄

- [TL;DR](#tldr)
- [症狀](#症狀)
- [問題原因](#問題原因)
- [正確解法：使用 `skills.load.extraDirs`](#正確解法使用-skillsloadextradirs)
- [`extraDirs` 路徑規則](#extradirs-路徑規則)
- [技術細節](#技術細節)
- [操作步驟](#操作步驟)
- [遷移檢查清單](#遷移檢查清單)
- [故障排除](#故障排除)
- [延伸閱讀](#延伸閱讀)

## TL;DR

- 2026-03-07 之後，OpenClaw 會追蹤 skill 路徑的 `realpath`。
- 若 symlink 解析後的真實路徑落在允許目錄外，skill 會被拒絕載入。
- 常見症狀是技能被略過，並在掃描/診斷輸出中看到類似：`Skipping skill path that resolves outside its configured root.`
- 這不是「掃描不到 symlink」，而是掃描後的 canonical path/contained-root 驗證拒絕了 out-of-root 目標。
- 正確做法不是繼續把外部 skill symlink 進來，而是用 `skills.load.extraDirs` 明確告訴 OpenClaw 去掃描外部技能目錄。
- `extraDirs` 應指向「技能類別目錄」，不是更上層的父目錄。

## 症狀

若透過中央管理技能的方式，並使用 symlink 將實際檔案指向 AI 工具（如 OpenClaw）的全域技能目錄，在 2026-03-07 的安全性更新後可能遇到載入失敗。較接近真實的症狀，是技能掃描時出現類似：

```text
[skills] Skipping skill path that resolves outside its configured root.
```

可先用正式存在的 CLI 入口做診斷：

```bash
openclaw skills list --eligible -v
```

若需要再看 gateway logs，使用：

```bash
openclaw logs --plain | grep 'allowed'
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

特別是當你的 skills 採「集中管理」模式，實際的 skill 檔案、scripts、binary 或相關資源都維護在其他位置時，`extraDirs` 是讓 OpenClaw 直接取得這些能力的最快、也最正規的方式。

判斷原則可以寫得更直接：

- 若 skill 目錄在 symlink 解析後的真實路徑（real path）位於 `~/.openclaw/skills` 或 `~/.openclaw/workspace/skills` 之外，請不要再依賴 symlink 載入
- 這種情況下，應改用 OpenClaw CLI 明確設定 `skills.load.extraDirs`

### 安全性注意事項

`extraDirs` 不是叫你把任何任意路徑都交給 OpenClaw 掃描，而是把「你明確信任的外部技能來源」顯式加入掃描清單。

- 僅將 `extraDirs` 指向你信任、可控、且內容可審查的目錄
- 不要把來路不明、多人共用、或會被其他流程動態改寫的路徑直接加入 `extraDirs`
- 相比之下，symlink 載入的問題在於它會把最終真實路徑藏在 alias 後面；`extraDirs` 則是把外部來源明確宣告出來，行為更可預期、也更容易審核

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

實務上，`extraDirs` 應優先指向：

- ✅ 技能類別目錄，例如 `<skills-repo>/skills/git`
- ✅ 技能類別目錄，例如 `<skills-repo>/skills/infra`
- ❌ 不要指向 `<skills-repo>/skills/`
- ❌ 不要指向 `<skills-repo>/`

可以直接對照成下面這種正確 / 錯誤示例：

```text
✅ <skills-repo>/skills/git          # 技能類別目錄
✅ <skills-repo>/skills/infra        # 技能類別目錄
❌ <skills-repo>/skills              # 太上層，一層掃描找不到真正 skill
❌ <skills-repo>                     # 更寬，會掃到非技能內容
```

這樣做的原因是：

- 指向類別目錄時，一層掃描就能找到每個 skill 子目錄裡的 `SKILL.md`
- 指向更上層父目錄時，一層掃描只會看到 `git/`、`infra/`、`productivity/` 這類資料夾本身，還到不了真正 skill 所在位置

## 技術細節

技能載入的路徑驗證可以分成兩階段。

### 階段一：目錄掃描

在掃描階段，OpenClaw 會列出子目錄。若某個 entry 是 symlink，且其目標是目錄，仍可能被加入掃描結果。

也就是說，**掃描階段仍可能看見 symlink entry**；真正阻擋外部目標的是後續的 canonical path 驗證。

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

### 替代方案：直接複製進本地 skills 目錄

另一個可行做法，是把 skill 直接複製到 `~/.openclaw/skills` 或 `~/.openclaw/workspace/skills`。

這在單機、單 repo、變動不頻繁的情境下可以工作，但若你的 skills 是集中管理的，通常不如 `extraDirs`：

- 複製容易造成版本漂移
- 同一份 skill 需要重複同步到多個位置
- 後續更新時，比較難確認目前生效的是哪一份

### 3. 重啟 gateway

```bash
openclaw gateway restart
```

### 4. 驗證技能是否正常載入

```bash
openclaw skills list --eligible
```

## 遷移檢查清單

若你是從舊的 symlink 做法遷移到 `extraDirs`，可照這個最短流程走：

1. **確認症狀**
   - 先跑 `openclaw skills list --eligible -v`
   - 若需要更進一步，再跑 `openclaw logs --plain | grep 'allowed'`
   - 確認目前真的是 contained-root / canonical path 驗證導致載入失敗
2. **清理舊 symlink 依賴**
   - 找出仍放在 `~/.openclaw/skills` 或其他技能根目錄中的外部 symlink
   - 避免新舊做法並存，讓來源判讀混亂
3. **設定 `extraDirs` 並重啟驗證**
   - 將 `skills.load.extraDirs` 指向技能類別目錄
   - `openclaw gateway restart`
   - 再跑 `openclaw skills list --eligible` 確認已正常載入

## 故障排除

### 症狀：設定了 `extraDirs` 但還是找不到 skill

可能原因：

- `extraDirs` 指到了父目錄，不是技能類別目錄
- 目標 skill 目錄下沒有 `SKILL.md`
- `extraDirs` 指到的路徑根本不存在
- OpenClaw 對 `<skills-repo>` 沒有讀取權限
- gateway 尚未重啟，仍在使用舊設定

建議檢查：

```bash
openclaw config get skills.load.extraDirs
openclaw gateway restart
openclaw skills list --eligible
```

並額外確認：

```bash
ls -la <skills-repo>/skills
```

### 症狀：仍然看到 `Skipping` 警告

檢查 warning：

```bash
openclaw skills list --eligible 2>&1 | grep "Skipping"
```

若仍出現類似 `Skipping skill path that resolves outside its configured root.` 的訊息，代表某些 skill 來源仍然依賴外部 symlink，尚未完全改成 `extraDirs` 掃描。

### 症狀：技能有載入，但來源不是預期目錄

檢查來源：

```bash
openclaw skills list --eligible | grep "openclaw-extra"
```

若你預期 skill 來自外部額外目錄，通常應能看到 `openclaw-extra`。

## 延伸閱讀

- [Skills 系統（打包、版本控制、測試）](../core/skills-system.md)
- [SKILL.md Frontmatter 欄位說明](../skill-frontmatter.md)
- [故障排除（常見問題）](../troubleshooting.md)
�見問題）](../troubleshooting.md)
.md)
