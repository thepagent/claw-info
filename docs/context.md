---
last_validated: 2026-05-23
validated_by: tboydar-agent
---

# /context 指令群與 Context 視覺化

> 本文說明 OpenClaw 的 `/context` 指令群，特別是 `/context map` 視覺化功能與 Control UI 的 context usage indicator。

---

## TL;DR

- `/context map` — 產生當前 session 所有 context contributors 的 treemap 圖片，一眼看出誰佔了最多 token
- `/context compact` — 觸發 compaction，壓縮對話歷史
- Control UI 右上角有 persistent 的 context usage indicator，即時顯示用量百分比
- **診斷場景**：回覆變慢、模型開始「失憶」或偏離主題時，先用 `/context map` 檢查

---

## 1. /context 指令群總覽

| 指令 | 功能 | 適用時機 |
|------|------|----------|
| `/context map` | 產生 treemap 圖片，視覺化各 context contributor 的 token 佔比 | 診斷 context 膨脹、找出「誰佔最多」 |
| `/context compact` | 觸發 compaction，壓縮對話歷史為摘要 | 對話過長、需要釋放 token |
| `/context` | 顯示當前 context 的基本資訊（文字摘要） | 快速確認當前 context 狀態 |

> 各版本支援的子指令可能略有不同，請以實際 CLI 提示為準。

---

## 2. /context map 詳解

### 2.1 什麼是 Context Contributor？

OpenClaw 的 session context 由多個「貢獻者」組成：

- **對話歷史（messages）** — 人類與 agent 的來回對話
- **系統提示（system prompt）** — 包含 AGENTS.md、SOUL.md、USER.md 等專案上下文
- **工具定義（tool definitions）** — 可用工具的描述與 schema
- **記憶檔案（memory files）** — MEMORY.md、memory/*.md 等（若已載入）
- **技能檔案（skill files）** — 當前載入的 SKILL.md
- **其他注入內容** — heartbeat payload、cron 注入、webhook 內容等

### 2.2 Treemap 怎麼讀

`/context map` 輸出的 treemap：

```
┌─────────────────────────────────────────┐
│  [對話歷史] ████████████████████  45%   │
│  [系統提示] ████████████          25%   │
│  [工具定義] ████████              18%   │
│  [記憶檔案] ███                    8%   │
│  [技能檔案] ██                     4%   │
└─────────────────────────────────────────┘
```

- **面積越大 = token 佔比越高**
- 通常對話歷史會隨時間膨脹，成為最大塊
- 若「工具定義」佔比異常高，可能載入了過多技能或 MCP server

### 2.3 使用範例

在 WebChat 或任何支援的 channel 中輸入：

```
/context map
```

Agent 會回傳一張 treemap 圖片，並附上簡短說明。

---

## 3. 何時使用 /context map 診斷

### 3.1 症狀對照表

| 症狀 | 可能原因 | 建議操作 |
|------|----------|----------|
| 回覆變慢、延遲明顯增加 | Context 接近上限，模型處理量大 | `/context map` → 確認佔比 → `/context compact` |
| 模型開始「失憶」早期內容 | Context window 被擠滿，早期訊息被截斷 | `/context map` → 考慮 compaction 或重開 session |
| 回覆偏離主題、出現幻覺 | 上下文雜訊過多（例如大量工具定義） | `/context map` → 檢查是否有不必要的技能/MCP 載入 |
| 某個功能突然無法使用 | 工具定義被擠出 context window | `/context map` → 確認工具定義是否仍在 context 內 |

### 3.2 診斷流程

```
1. 輸入 /context map
2. 觀察 treemap：
   - 對話歷史 > 60%？→ 考慮 compact 或分段處理
   - 工具定義 > 30%？→ 檢查是否載入過多技能/MCP
   - 記憶檔案異常大？→ 檢查 MEMORY.md 是否過度膨脹
3. 根據結果採取行動：
   - /context compact（壓縮對話）
   - 或重開新 session（最乾淨）
   - 或調整技能/MCP 載入策略
```

---

## 4. /context compact 與 compaction 機制

### 4.1 Compaction 是什麼？

當對話越來越長，OpenClaw 會自動或手動觸發 **compaction**：

- 把早期對話歷史「壓縮」成摘要
- 釋放 token 空間給新的對話
- 保留關鍵資訊，但可能遺失細節

### 4.2 自動 vs 手動

| 類型 | 觸發時機 | 效果 |
|------|----------|------|
| 自動 compaction | 達到設定的 context 閾值時 | 背景執行，可能輕微延遲 |
| 手動 `/context compact` | 使用者主動觸發 | 即時壓縮，可觀察前後變化 |

### 4.3 與 /context map 的關係

- ** compaction 前**：`/context map` 顯示「膨脹狀態」
- ** compaction 後**：再次 `/context map` 可觀察「對話歷史」區塊縮小
- 若 compact 後仍佔比過高，表示非對話部分（工具/記憶）過大

---

## 5. Control UI 的 Context Usage Indicator

### 5.1 位置與外觀

WebChat / Control UI 右上角有一個 **persistent 的 context usage indicator**：

```
┌────────────────────────────────────┐
│  OpenClaw                    [██░░]  │  ← 這個
│                                    │
│  對話內容...                        │
└────────────────────────────────────┘
```

- 以進度條形式顯示當前 context 用量百分比
- 即時更新，不需要手動刷新

### 5.2 如何解讀

| 狀態 | 含義 | 建議 |
|------|------|------|
| [░░░░] < 50% | 健康，空間充裕 | 正常對話 |
| [██░░] 50-80% | 開始膨脹，注意觀察 | 留意回覆品質，準備 compact |
| [███░] 80-95% | 接近上限，風險升高 | 建議 `/context compact` 或分段任務 |
| [████] > 95% | 危險，可能截斷或失敗 | 立即 compact 或重開 session |

### 5.3 與 /context map 的搭配使用

- **Indicator 顯示高用量** → 用 `/context map` 找出「誰佔最多」
- **Indicator 突然飆升** → 可能是大量工具定義或記憶檔案被載入，用 `/context map` 確認

---

## 6. 與 Memory Flush 的關係

### 6.1 Memory Flush 是什麼？

Memory flush 是更激進的 context 清理：

- 完全清除當前 session 的對話歷史
- 保留系統設定與基本狀態
- 相當於「軟重啟」session

### 6.2 選擇：compact vs flush vs 新 session

| 需求 | 建議操作 | 效果 |
|------|----------|------|
| 保留對話脈絡，但釋放空間 | `/context compact` | 壓縮歷史，保留主題 |
| 完全清除，重新開始 | memory flush（若支援）或重開 session | 最乾淨，但失去所有上下文 |
| 長期任務，避免污染主對話 | spawn isolated session | 主對話乾淨，任務在獨立環境執行 |

---

## 7. 常見問題

### Q1: /context map 顯示的圖片可以下載嗎？

A: 產生的 treemap 圖片會隨對話回傳，可視 channel 支援程度保存。建議在診斷時直接觀察即可，通常不需要長期保存。

### Q2: 為什麼 compact 後 indicator 還是很高？

A: Compaction 主要壓縮「對話歷史」。如果 indicator 仍高，可能是：
- 工具定義過多（檢查載入的技能/MCP）
- 記憶檔案過大（整理 MEMORY.md）
- 系統提示過長（檢查 AGENTS.md 是否膨脹）

### Q3: 可以限制 context 上限嗎？

A: Context 上限主要由模型決定（例如 128K、200K）。OpenClaw 會在接近上限時自動觸發 compaction，但無法「硬限制」在更低值。建議透過 isolated session 分散長任務。

### Q4: 在 isolated session 也能用 /context map 嗎？

A: 理論上可以，但 isolated session 通常生命週期較短、context 較乾淨，較少需要診斷。若遇到異常，仍可嘗試使用。

---

## 8. 最佳實務

1. **定期檢查**：長對話（>20 輪）後，偶爾用 `/context map` 確認健康度
2. **高用量即處理**：Indicator > 80% 時主動 compact，不要等到變慢
3. **長任務隔離**：超過 30 輪的任務，考慮 spawn isolated session
4. **技能管理**：只載入當下需要的技能，避免工具定義膨脹
5. **記憶整理**：定期整理 MEMORY.md，避免記憶檔案無限增長

---

## 延伸閱讀

- `docs/core/session-isolation.md` — main vs isolated session 的選擇
- `docs/core/memory-strategy.md` — 記憶系統與檔案策略
- `docs/cli.md` — CLI 指令速查
