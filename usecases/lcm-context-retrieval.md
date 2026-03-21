# LCM Context Retrieval — 從壓縮記憶中精準撈回細節

> 當對話被 compaction 壓縮後，用 `lcm_grep` → `lcm_expand` → `lcm_expand_query` 精準找回被摘要掉的細節，而不是重新問一遍。

---

## TL;DR

- OpenClaw 的 Lossless Context Management（LCM）會自動壓縮長對話，把早期訊息變成摘要
- 摘要保留語義但丟失細節——當你需要精確數字、程式碼片段、或確切用詞時，摘要不夠用
- 四個工具組成檢索鏈：`lcm_grep`（搜）→ `lcm_describe`（看）→ `lcm_expand`（展開）→ `lcm_expand_query`（問答）
- 實戰用法：先 grep 定位摘要 ID，再 expand 展開到原始訊息層
- 支援跨 session 搜尋（`allConversations: true`），可以找到其他對話中的內容

---

## 解決什麼問題

長對話中常見這些情境：

| 情境 | 症狀 | 沒有 LCM 工具的做法 |
|------|------|---------------------|
| 兩小時前討論的設定參數 | agent 回答「之前我們決定用 X」但說不出具體值 | 請人類翻聊天紀錄重貼 |
| 昨天的錯誤訊息全文 | 摘要只寫「遇到權限錯誤」 | 重新觸發錯誤，或放棄 |
| 跨天任務的上下文銜接 | 新 session 不知道前一天做到哪 | 人類手動摘要貼過來 |
| 「我之前說過 XX」但找不到 | context window 裡已經沒有了 | 猜測或重問 |

LCM 工具讓 agent 自己挖回細節，不需要人類翻紀錄。

---

## 核心概念

### Compaction 與摘要 DAG

OpenClaw 的 compaction 機制將舊訊息壓縮成樹狀摘要結構：

```
sum_001 (頂層摘要："討論了部署方案並決定用 Docker")
  ├── sum_002 ("比較了三種部署方式的 pros/cons")
  │     ├── msg_101 (原始訊息：使用者貼的 benchmark 數據)
  │     └── msg_102 (原始訊息：agent 的分析回覆)
  └── sum_003 ("最終選擇 Docker，設定了 port mapping")
        ├── msg_103 (原始訊息：docker-compose.yml 內容)
        └── msg_104 (原始訊息：測試結果)
```

- **摘要（sum_xxx）**：壓縮後的語義概括，保留在 context 中
- **原始訊息（msg_xxx）**：被壓縮掉的完整內容，仍然儲存在 LCM 中
- **DAG（有向無環圖）**：摘要可以巢狀，頂層摘要包含子摘要，子摘要包含原始訊息

### 四個工具的分工

| 工具 | 用途 | 類比 |
|------|------|------|
| `lcm_grep` | 用 regex 或全文搜尋找到相關的摘要/訊息 | `grep` — 找到位置 |
| `lcm_describe` | 查看某個 sum/file 的 metadata 和內容 | `ls -la` — 看詳情 |
| `lcm_expand` | 展開摘要，取得子摘要或原始訊息 | `cat` — 讀內容 |
| `lcm_expand_query` | 帶著問題展開，由 sub-agent 整理答案 | `grep + awk` — 搜尋並整理 |

---

## 操作指引

### 模式一：知道關鍵字 → grep 定位 → expand 取回

最常見的模式。你記得討論過某個東西，想找回細節。

**Step 1：搜尋**

```json
{
  "tool": "lcm_grep",
  "pattern": "docker-compose",
  "mode": "full_text",
  "scope": "both"
}
```

回傳會包含匹配的摘要 ID（如 `sum_003`）和片段預覽。

- `mode`: `"regex"` 用正規表達式，`"full_text"` 用全文搜尋
- `scope`: `"messages"` 只搜原始訊息，`"summaries"` 只搜摘要，`"both"` 全搜

**Step 2：展開**

```json
{
  "tool": "lcm_expand",
  "summaryIds": ["sum_003"],
  "includeMessages": true
}
```

設定 `includeMessages: true` 會一路展開到原始訊息，拿到完整的 docker-compose.yml 內容。

### 模式二：帶問題直接查 → expand_query

> ⚠️ 此模式會觸發 sub-agent 呼叫，token 成本與延遲通常高於 grep + expand。適合「需要整理答案」的複雜問題；簡單關鍵字搜尋用模式一即可。

當你要回答一個具體問題，但不確定關鍵字時。

```json
{
  "tool": "lcm_expand_query",
  "prompt": "之前設定的 nginx reverse proxy 監聽哪個 port？",
  "query": "nginx proxy port"
}
```

`lcm_expand_query` 會自動：
1. 用 `query` 做 grep 搜尋
2. 展開匹配的摘要
3. 用 sub-agent 根據 `prompt` 從展開內容中提取答案

回傳的是整理過的答案，附帶引用的摘要 ID。

> 💡 **參數版本提醒**：`tokenCap`、`maxDepth`、`conversationId` 等參數可能隨 OpenClaw 版本更迭而異。實作前建議先透過工具 schema 或 `lcm_describe` 確認當前版本支援的參數。

### 模式三：檢查特定摘要的結構 → describe

當你拿到一個 sum_xxx ID，想先看它的 metadata 再決定要不要展開。

```json
{
  "tool": "lcm_describe",
  "id": "sum_003"
}
```

回傳摘要內容、子項目列表、token 數等 metadata。用來判斷「這個摘要值不值得花 token 展開」。

### 模式四：跨對話搜尋

在另一個 session 中討論過的內容，也可以搜到：

```json
{
  "tool": "lcm_grep",
  "pattern": "deployment strategy",
  "allConversations": true,
  "mode": "full_text"
}
```

> 💡 使用 `allConversations: true` 時，建議先用更精確的關鍵字（結合時間/主題詞），避免跨 session 搜尋產生過量雜訊。確認當前 session 搜不到後再擴大範圍。

或指定 conversation：

```json
{
  "tool": "lcm_expand_query",
  "prompt": "上次在 Telegram 討論的部署決定是什麼？",
  "query": "deploy",
  "conversationId": 42
}
```

---

## 實戰範例：找回三小時前的錯誤訊息

場景：三小時前跑 `npm install` 出錯，當時貼了完整 error log，現在要 debug 但 compaction 已經把它壓成「安裝依賴時遇到 peer dependency 衝突」。

```
# Step 1: grep 搜尋
lcm_grep(pattern="peer dependency|npm ERR", mode="regex", scope="messages")

# 找到 msg_2847 在 sum_1204 裡
# Step 2: expand 那個摘要
lcm_expand(summaryIds=["sum_1204"], includeMessages=true)

# 拿到原始 error log 全文，包含具體的版本衝突資訊
```

---

## 最佳實務

### 該用哪個工具？

```
「我記得關鍵字」           → lcm_grep → lcm_expand
「我要回答一個具體問題」    → lcm_expand_query
「我拿到 ID 想先看看」     → lcm_describe
「我要完整原始訊息」       → lcm_expand(includeMessages: true)
```

### 省 Token 的技巧

- **先 grep 再 expand**：不要盲目展開大範圍摘要，先用 grep 縮小範圍
- **用 `tokenCap`**：`lcm_expand` 和 `lcm_expand_query` 都支援 `tokenCap` 參數，限制展開的 token 量
- **用 `maxDepth`**：只需要子摘要不需要原始訊息時，設 `maxDepth: 1`
- **先 describe 再 expand**：用 `lcm_describe` 看 token 數，太大的摘要分批展開

### Anti-patterns

| 做法 | 問題 | 改用 |
|------|------|------|
| 每次都 `allConversations: true` | 搜尋範圍太大，結果雜訊多 | 預設搜當前 session，確定不在才跨 session |
| 直接 expand 頂層摘要 | 一次展開整棵樹，token 爆炸 | 先 grep 定位，只展開相關分支 |
| 用 lcm_expand_query 做簡單關鍵字搜尋 | 殺雞用牛刀，多花一次 sub-agent 呼叫 | 簡單搜尋用 lcm_grep 就夠 |
| 忽略回傳的 sum_xxx ID | 下次又要重新搜尋 | 記下 ID，後續可直接 expand |

---

## Troubleshooting

- **症狀**：`lcm_grep` 搜不到明明討論過的內容
  - **可能原因**：內容在其他 session / conversation 中
  - **處理方式**：加 `allConversations: true` 重試；或檢查 `conversationId` 是否正確

- **症狀**：`lcm_expand` 回傳 token 太多，context 爆了
  - **可能原因**：展開了一個包含大量子項目的頂層摘要
  - **處理方式**：加 `tokenCap` 限制；或先 `lcm_describe` 看結構，只展開需要的子摘要

- **症狀**：`lcm_expand_query` 回答不精確
  - **可能原因**：`query` 太模糊，grep 到不相關的摘要
  - **處理方式**：讓 `query` 更具體（用確切術語），或改用 `summaryIds` 直接指定要展開的摘要

---

## 與 memory_search 的區別

| | `memory_search` | LCM 工具 |
|---|---|---|
| 搜尋範圍 | MEMORY.md + memory/*.md（持久檔案） | 對話歷史（含被壓縮的訊息） |
| 資料來源 | agent 主動寫入的筆記 | 自動保留的完整對話紀錄 |
| 適用場景 | 長期知識、偏好、決策記錄 | 本次或近期對話的具體細節 |
| 持久性 | 永久（除非刪除檔案） | 隨 session 生命週期 |

**兩者互補**：重要結論寫進 memory 檔案，臨時細節用 LCM 撈回。

---

## See also

- `docs/cron.md` — cron job 的 isolated session 也有獨立的 LCM context
- `usecases/workspace-file-architecture.md` — 持久記憶的檔案分層設計
