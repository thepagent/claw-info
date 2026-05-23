---
last_validated: 2026-05-24
validated_by: tboydar-agent
---

# Subagent Bootstrap Context 變更與 AGENTS.md/TOOLS.md 隔離指南

> OpenClaw 2026.5.22-beta.1 起，subagent 預設只載入 `AGENTS.md` 與 `TOOLS.md`，不再繼承主人的個人化上下文。本文說明為什麼這樣設計、受影響的檔案有哪些，以及如何在需要時正確傳遞上下文。

---

## TL;DR

- **預設行為**：subagent 只讀取 `AGENTS.md` + `TOOLS.md`，`SOUL.md`、`USER.md`、`MEMORY.md` 等個人化檔案被排除
- **原因**：安全隔離 — 避免委派任務時無意洩漏個人資訊或記憶
- **需要個人化時**：透過 `attachments` 參數、`context: "fork"`、或讓 subagent 自行 `memory_search` 查詢
- **升級注意**：從舊版升級後，若 subagent「不認識」主人，這是預期行為，不是 bug

---

## 背景：為什麼改變預設行為

### 舊版行為（2026.5.22-beta.1 之前）

subagent 啟動時會繼承主 session 的完整上下文，包括：
- `SOUL.md` — agent 的人格、語氣、價值觀
- `IDENTITY.md` — agent 的自我認同
- `USER.md` — 主人的個人資訊、偏好、習慣
- `MEMORY.md` — 長期記憶、重要事件、決策紀錄
- `HEARTBEAT.md` — 定期檢查清單與主動行為規則

這看似方便，但帶來兩個問題：

1. **資訊外洩風險**：委派一個「分析公開 repo」的任務，subagent 卻能讀到主人的私人記憶、行事曆內容、甚至密碼管理器的使用習慣
2. **上下文污染**：subagent 被個人化資訊干擾，反而難以專注在任務本身（例如：因為讀到主人喜歡某種風格，就無意中在技術文件裡加入個人偏好）

### 新版行為（2026.5.22-beta.1 起）

subagent 預設 bootstrap context **僅限**：
- `AGENTS.md` — 工作空間規則、紅線、工具使用規範
- `TOOLS.md` — 環境專屬的工具設定（相機名稱、SSH 主機、TTS 偏好等）

其他個人化檔案被排除，除非**明確傳入**。

---

## 受影響的檔案清單

| 檔案 | 內容 | 預設是否載入 subagent |
|------|------|----------------------|
| `AGENTS.md` | 工作空間規則、紅線、安全準則 | ✅ 是 |
| `TOOLS.md` | 環境專屬工具設定 | ✅ 是 |
| `SOUL.md` | 人格、語氣、價值觀 | ❌ 否 |
| `IDENTITY.md` | 自我認同（名稱、形象） | ❌ 否 |
| `USER.md` | 主人的個人資訊與偏好 | ❌ 否 |
| `MEMORY.md` | 長期記憶 | ❌ 否 |
| `HEARTBEAT.md` | 定期檢查清單 | ❌ 否 |
| `BOOTSTRAP.md` | 首次啟動設定（若存在） | ❌ 否 |
| `memory/YYYY-MM-DD.md` | 每日記錄 | ❌ 否 |

---

## 如何按需傳遞上下文

### 方法 1：透過 `attachments` 明確傳入（推薦：精準控制）

在 `sessions_spawn` 時，用 `attachments` 參數把需要的檔案內容傳給 subagent：

```
sessions_spawn(
  task: "幫我整理這週的行事曆重點",
  attachments: [
    {
      name: "USER.md",
      content: "[USER.md 的內容]",
      mimeType: "text/markdown"
    }
  ]
)
```

**優點**：只傳必要的資訊，最小化外洩面積  
**適用**：需要 subagent 知道主人偏好，但不需要完整記憶的場景

### 方法 2：透過 `context: "fork"` 繼承當前對話（推薦：連貫任務）

如果 subagent 需要理解當前對話的脈絡：

```
sessions_spawn(
  task: "基於我們剛才的討論，實作這個功能",
  context: "fork"  // 繼承當前對話上下文
)
```

**優點**：subagent 知道「剛才說了什麼」，無需重複說明  
**注意**：fork 的是**對話歷史**，不是檔案系統的記憶檔案  
**適用**：多輪討論後的接續實作

### 方法 3：讓 subagent 自行查詢（推薦：需要記憶時）

如果 subagent 需要查閱特定記憶，但不需要全部載入：

```
sessions_spawn(
  task: "幫我寫一份週報，參考我最近的工作記錄。\n\n"
        "你需要什麼資訊，請用 memory_search 工具查詢，"
        "不要假設你知道我的專案細節。"
)
```

在 subagent 的 prompt 中明確指示它使用 `memory_search` 工具按需查詢，而非預設載入所有記憶。

**優點**：subagent 只讀取需要的記憶片段  
**適用**：需要參考歷史記錄，但記錄量很大的場景

### 方法 4：直接寫入任務描述（推薦：簡單偏好）

如果只需要傳遞一兩個偏好，直接寫在 task 裡比傳整個檔案更乾淨：

```
sessions_spawn(
  task: "寫一份技術文件。注意：\n"
        "- 使用繁體中文\n"
        "- 程式碼範例用 TypeScript\n"
        "- 避免過多 emoji"
)
```

---

## Use Case 示範

### Use Case 1：安全委派 — 讓 subagent 不接觸個人記憶

**情境**：委派一個「分析公開 GitHub repo 並寫 review」的任務

```
sessions_spawn(
  task: "分析 https://github.com/example/project 的程式碼品質，"
        "輸出結構化 review 報告。\n"
        "你只會收到 repo URL 和驗收標準，"
        "不需要也不應該知道我的個人資訊。"
)
```

**結果**：subagent 只有 `AGENTS.md`（知道工具使用規範）和 `TOOLS.md`（知道環境設定），完全不知道主人是誰、有什麼專案、有什麼偏好。

### Use Case 2：需要個人化 — 正確傳遞 USER.md

**情境**：委派一個「幫我回覆這封 email」的任務，需要知道主人的語氣和常用表達

```
sessions_spawn(
  task: "幫我回覆這封 email，語氣要符合我的風格。",
  attachments: [
    {
      name: "USER.md",
      content: "## 語氣偏好\n- 專業但友善\n- 不用敬語，用平輩語氣\n- 簽名用 'Best,'",
      mimeType: "text/markdown"
    }
  ]
)
```

**結果**：subagent 知道主人的語氣偏好，但不會讀到行事曆、密碼習慣或其他無關記憶。

### Use Case 3：連續對話 — 用 fork 保持脈絡

**情境**：主 session 已經討論了 10 輪需求，現在要委派實作

```
// 主 session 已經討論完需求
// 現在派出 subagent 實作

sessions_spawn(
  task: "實作我們剛才討論的登入功能：\n"
        "- JWT token 驗證\n"
        "- 支援 Google OAuth\n"
        "- 失敗 3 次鎖定 15 分鐘\n"
        "具體規格參考 fork 的對話歷史。",
  context: "fork",
  timeoutSeconds: 1800
)
```

**結果**：subagent 知道「JWT + Google OAuth + 失敗鎖定」的完整脈絡，無需在 task 中重複所有細節。

---

## 與舊版行為的差異

| 行為 | 舊版（< 2026.5.22-beta.1） | 新版（>= 2026.5.22-beta.1） |
|------|---------------------------|----------------------------|
| subagent 知道主人名字 | ✅ 自動繼承 USER.md | ❌ 需透過 attachments 傳入 |
| subagent 讀取長期記憶 | ✅ 自動繼承 MEMORY.md | ❌ 需用 memory_search 查詢 |
| subagent 遵循 HEARTBEAT 規則 | ✅ 自動繼承 | ❌ 主 session 負責 heartbeat |
| subagent 知道工具設定 | ✅ 自動繼承 TOOLS.md | ✅ 仍自動繼承 |
| subagent 知道工作空間規則 | ✅ 自動繼承 AGENTS.md | ✅ 仍自動繼承 |

### 升級檢查清單

如果你從舊版升級，發現 subagent 行為改變：

- [ ] subagent「不認識」主人 → **預期行為**，需要時用 attachments 傳入 USER.md
- [ ] subagent 無法參考過去記憶 → **預期行為**，改用 memory_search 或 attachments
- [ ] subagent 沒有執行 heartbeat 檢查 → **預期行為**，heartbeat 是主 session 的責任
- [ ] subagent 無法使用工具 → **檢查 TOOLS.md** 是否正確配置，這個仍會自動載入

---

## 最佳實務

### 1. 預設最小化，需要時再傳入

不要為了「方便」就把所有檔案傳給 subagent。每次傳入前問自己：
- subagent 完成這個任務**真的需要**這個資訊嗎？
- 這個資訊如果外洩，**影響有多大**？

### 2. 用摘要代替完整檔案

與其傳整個 `MEMORY.md`（可能幾千行），不如在 task 中寫：

```
「相關背景：我們上週決定改用 pnpm，原因是 lockfile 衝突。
 詳細記錄請用 memory_search 查詢 'pnpm migration'。」
```

### 3. 敏感資訊絕不傳入無關任務

如果 `TOOLS.md` 包含 SSH 密碼、API key 等敏感資訊，確保：
- 只委派給信任的 subagent（例如本地執行、非外部服務）
- 或改用 `1password` skill 動態讀取，而非靜態寫在檔案裡

### 4. 測試 subagent 的上下文邊界

委派重要任務前，可以先 spawn 一個測試 subagent：

```
sessions_spawn(
  task: "請列出你目前載入的上下文檔案，以及你知道的關於我的資訊。"
)
```

確認它確實沒有讀到不該讀的東西。

---

## 故障排除

### 問題：subagent 說「我不知道你是誰」

**原因**：預設行為，subagent 沒有載入 USER.md  
**解法**：用 attachments 傳入必要的身份資訊，或直接在 task 中說明

### 問題：subagent 無法參考過去的決策

**原因**：MEMORY.md 未載入  
**解法**：
1. 在 task 中摘要關鍵決策
2. 或讓 subagent 使用 `memory_search` 查詢
3. 或傳入相關的 memory 片段作為 attachments

### 問題：subagent 的語氣跟主 agent 完全不同

**原因**：SOUL.md 未載入  
**解法**：
1. 如果任務需要一致語氣，傳入 SOUL.md 的摘要
2. 如果任務是技術性的（寫 code、分析資料），不同語氣可能是優點 — 更客觀

### 問題：fork context 後 subagent 還是看不到記憶

**原因**：`context: "fork"` 只 fork 對話歷史，不 fork 檔案系統的記憶檔案  
**解法**：需要記憶時，額外使用 attachments 或 memory_search

---

## 延伸閱讀

- [Session 隔離與模型選擇](./core/session-isolation.md) — main vs isolated vs cron 的完整說明
- [Sub-Agent Orchestration](../usecases/subagent-orchestration.md) — 背景任務委派實戰指南
- [Waterfall Subagent Delegation](../usecases/waterfall-subagent-delegation.md) — 多階段 subagent 委派模式
- [Memory Strategy](./core/memory-strategy.md) — 記憶檔案策略與最佳實務
