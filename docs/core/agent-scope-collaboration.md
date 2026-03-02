# Agent Scope Collaboration（A/B/C/D）一頁式實戰指南

> 目的：在多 channel、多 session 的 OpenClaw 環境中，建立低噪音、可追溯、可擴充的代理協作規範。  
> 角色定義：A=主代理（main），B/C=subagents，D=isolated agent（任務型）。

---

## TL;DR

- 每個 channel 可視為獨立 main 對話上下文，**不要假設跨 channel 自動共腦**。
- A 負責決策與對外回覆；B/C 負責執行；D 負責隔離任務與背景處理。
- 跨 session 只同步「摘要 + 證據路徑」，避免 raw logs 傾倒。
- 共用層只放規則與決策；個人/敏感內容留在私有層。
- 任務完成必做 QA Handshake：`PASS/FAIL + 差異 + executor attribution`。

---

## 解決的問題（Problems）

1. 多 agent 並行時責任不清，容易互相覆蓋。
2. 子代理回報過長，造成 token 浪費與訊息噪音。
3. 不同 session 之間資訊斷裂或錯誤共享。
4. 任務完成聲稱與實際行為不一致（缺少驗證）。

---

## 核心概念（Core Concepts）

### 1) Scope 四層

- **Session Scope**：對話隔離（main / subagent / isolated）。
- **Memory Scope**：共享規則 vs 私有記憶分層。
- **File Scope**：知識落地（canonical vs staging）。
- **Authority Scope**：誰能決策、誰能執行、誰能對外。

### 2) 角色分工

- **A（主代理）**：派工、整合、最終回覆、最終 QA。
- **B/C（subagents）**：執行型任務（程式、研究、整理）。
- **D（isolated）**：長任務/高風險/背景任務，不污染 main。

---

## 操作指引（How-to）

### Step 1 — 任務派發格式（A -> B/C/D）

最少包含：
1. Objective（一句話目標）
2. Deliverable（輸出檔案/格式）
3. Success Criteria（完成判準）
4. Scope Guard（可讀/可改/不可碰）
5. Deadline（若有）

### Step 2 — 回報格式（B/C/D -> A）

- Summary（1 行）
- Done（3~7 bullets）
- Evidence（檔案路徑/關鍵結果）
- Risks/Blockers（如無寫 none）
- Next Step（1 個具體動作）

### Step 3 — QA Handshake（A）

固定輸出：
- `QA: PASS` 或 `QA: FAIL`
- Differences/Fixes（1~3 點）
- `Executed by: B|C|D`

若 FAIL：
- 同 agent 重跑一次（限制更明確）
- 再失敗才允許主代理緊急熱修，並標記 `Emergency hotfix`

---

## 最佳實務 / Anti-patterns

### Best Practices

- 共享「規則/決策」，不共享「臨時思考/敏感內容」。
- 長內容落地到文件，聊天只保留可執行摘要。
- 定期回顧決策檔，避免規則漂移。

### Anti-patterns

- 把所有上下文都丟給每個子代理。
- 直接貼大段 stdout/stderr 當回報。
- 未驗證就宣稱任務完成。

---

## Troubleshooting

### 症狀：多代理答案互相矛盾
- 可能原因：Authority Scope 未定義、派工任務不具體。
- 解法：補上 owner + success criteria + scope guard，統一由 A 定稿。

### 症狀：token 成本持續上升
- 可能原因：重複摘要、raw logs 轉貼。
- 解法：啟用 3~7 bullets 回報格式，長內容改檔案連結。

### 症狀：跨 channel 記憶錯位
- 可能原因：把 session context 當成共享記憶。
- 解法：改用共用文件層（決策/狀態），不要依賴聊天歷史。

---

## Security Notes

- 預設最小揭露：群組僅回必要結論，不外露私有上下文。
- 外部發布、不可逆操作需確認。
- 記錄證據時避免貼敏感識別資訊。

---

## See also

- `docs/core/session-isolation.md`
- `docs/core/memory-strategy.md`
- `docs/core/messaging-routing.md`
- `docs/core/tooling-safety.md`
