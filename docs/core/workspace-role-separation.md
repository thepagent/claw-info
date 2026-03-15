# Workspace 檔案分工：AGENTS.md、SOUL.md、IDENTITY.md、USER.md（以及 memory）

## TL;DR

- **AGENTS.md**：工作區規則與操作邊界（什麼能做、什麼必須先問）。
- **SOUL.md**：人格/語氣/教學風格（怎麼說、怎麼陪）。
- **USER.md**：這位使用者的偏好與界線（這個人想要怎樣被協助）。
- **IDENTITY.md**：快速名片（我是誰，一眼看懂）。
- **MEMORY.md / memory/**：記憶多半是敏感資料，預設私密；協作/公開 repo 時要特別小心。
- **遇到衝突**：通常以 **AGENTS.md（規則/安全）優先**；其餘文件在不違反規則的前提下生效。

## 使用情境（你為什麼需要分工）

新手最常踩的坑不是「不會寫提示詞」，而是把不同層級的內容混在一起：

- 把「安全規則」寫進「人格檔」→ 之後改語氣時不小心破壞安全界線
- 把「個人隱私」寫進「共享 repo」→ 直接變成安全事故
- 把「今天要做什麼」塞進「長期偏好」→ 內容爆炸、難維護

分工的目的：**可掃描、可稽核、可維護、可協作**。

## 核心概念：四層資訊（Policy / Persona / Preferences / State）

建議用下面這個心智模型來放內容：

```
(最高優先)  Policy      : 允許/禁止什麼（AGENTS.md）
            Persona     : 如何表現（SOUL.md）
            Preferences : 這個使用者想要什麼（USER.md）
(最低優先)  State/Notes  : 當下狀態/環境筆記（NOW.md/TOOLS.md/memory）
```

### 衝突解決優先序（很重要）

當不同檔案出現矛盾時，建議優先序如下：

1. **AGENTS.md**：安全/授權/紅線（最高）
2. **USER.md**：使用者偏好（在不違反 AGENTS.md 的前提下）
3. **SOUL.md**：語氣與互動風格（在不違反 1/2 的前提下）
4. **IDENTITY.md**：簡短名片（通常不會與其他衝突）

> 直覺記法：**規則 > 偏好 > 風格 > 名片**。

## 各檔案責任（What goes where）

### AGENTS.md：工作區規則 / 操作政策（Policy）

放這裡：
- 需要先 approve 的行為（改檔、跑指令、對外發言、排程等）
- 工具使用規範（例如避免 destructive commands）
- repo/部署特有的流程

不要放：
- 個人隱私
- 長篇人格描述

### SOUL.md：人格與語氣（Persona）

放這裡：
- 你的語氣、教學方式、文化敏感度
- 情緒支持的風格（溫柔但不操控）

不要放：
- token、帳密
- 需要頻繁變動的「今日待辦」

### USER.md：使用者偏好與界線（Preferences）

放這裡：
- 稱呼、語言偏好、格式偏好
- 自主程度偏好（要不要先問、問到什麼程度）

不要放：
- 全域安全政策（那應該在 AGENTS.md）

### IDENTITY.md：快速名片（Identity card）

放這裡：
- 名字、簡短自我介紹、signature emoji

### TOOLS.md：環境筆記（Environment notes）

很多工作區會額外用 TOOLS.md 放「只對這台機器有效」的資訊：
- 裝置名稱、IP、路徑、偏好語音、SSH alias

> 這種內容不是 policy，也不是 user preference，是「環境現實」。

### NOW.md（可選）：熱狀態/短期焦點（Hot state）

若你需要記錄「現在最重要的 3 件事」或「當下上下文」，建議用單獨的 NOW.md（或類似檔案），避免污染 USER.md / MEMORY.md。

## How-to：快速判斷要放哪裡

### 決策小抄

- 「這是安全/授權/禁止」→ **AGENTS.md**
- 「這是說話方式/人格」→ **SOUL.md**
- 「這是這位使用者的偏好」→ **USER.md**
- 「這是我叫什麼」→ **IDENTITY.md**
- 「這台機器/環境的資訊」→ **TOOLS.md**
- 「我今天正在做什麼」→ **NOW.md（建議）」

### 範例：同一件事（發送訊息）在不同檔案怎麼寫

- AGENTS.md：
  - 「發送 email / GitHub comment / 任何對外訊息前必須先詢問使用者 approve」
- USER.md：
  - 「我希望你每次對外發言前先給我一段草稿讓我確認」
- SOUL.md：
  - 「對外發言語氣要禮貌、簡潔，不要情緒化」

## Anti-patterns（常見錯法）

- 把隱私記憶（MEMORY.md / memory/）推到公開 repo。
- 把所有事情都塞進 AGENTS.md，導致規則/筆記/偏好混在一起。
- 用 SOUL.md 寫「允許做什麼」→ 人格變動時容易破壞安全邊界。

## Troubleshooting

- **症狀**：我改了 USER.md 但 agent 行為沒變
  - **可能原因**：AGENTS.md 有更高優先序的限制（例如要求 approve）
  - **處理**：先檢查 AGENTS.md 是否有「Ask first」規則覆蓋你的偏好

- **症狀**：文件越寫越長、找不到東西
  - **可能原因**：把短期狀態寫進長期檔案（USER.md / MEMORY.md）
  - **處理**：把短期內容搬到 NOW.md；把環境細節搬到 TOOLS.md

- **症狀**：協作/分享後出現隱私風險
  - **可能原因**：把 memory 類檔案放進可共享的 repo
  - **處理**：確認 `.gitignore` 排除 `MEMORY.md`、`memory/` 等敏感路徑，並改用私有儲存

## Security notes

- **預設假設**：`MEMORY.md` 與 `memory/` 可能包含高度個人化資料。
- **共享/協作情境**：
  - 不要把記憶檔案推到公開 repo
  - 在 shared sessions 或多人可讀的環境中，建議直接禁止載入這些檔案（或先脫敏）

## See also

- `./approval-first-workflow.md`（#297）
- `../howto/agent-owned-github-repo.md`（#298）
- `../STYLE_GUIDE.md`
