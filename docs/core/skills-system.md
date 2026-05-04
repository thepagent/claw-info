---
last_validated: 2026-05-04
validated_by: chaodu-agent
---

# Skills 系統（打包、版本控制、測試）

> 本文是 OpenClaw 的核心概念深度解析：Skills 是什麼、如何打包、如何寫 SKILL.md、如何在本機測試與安全地發布/更新。
>
> 目標讀者：要「新增/維護一個 Skill」、或要把內部工具變成可重用能力的人。

---

## TL;DR

- **Skill = 可重用的能力包**：把「一個工具/一個整合/一套操作流程」封裝成可被 agent 理解與遵循的單位。
- **SKILL.md 是契約**：它同時是「使用說明」與「提示模板」，會直接影響 agent 如何使用該 Skill。
- **版本控制以 Git 為主**：先用 git tag / commit SHA 追蹤即可；不要在文件裡硬塞版本號造成漂移。
- **測試重點是“可重現”**：用最小 example + 明確前置條件，確保別人照做能跑通。
- **安全是預設假設不可信**：Skill 會放大工具能力（exec/browser/message/nodes），必須把危險行為寫清楚、加護欄、降低爆炸半徑。

---

## 1. 名詞與範圍

### 1.1 Skill 是什麼？

在 OpenClaw 的語境中，**Skill** 是一個可被重用、可被文件化、可被測試/維護的能力單元。它通常包含：

- 一份 **SKILL.md**（核心文件，給人與模型看）
- （可選）scripts / config / assets，用來支撐該能力

你可以把 Skill 想成：

- 「一個整合（integration）」：例如 Twitter、1Password、AgentCore Browser
- 「一個專門工作流程（workflow）」：例如從 issue → 修 code → 開 PR
- 「一個封裝好的工具鏈」：例如 ffmpeg 抽影格、或一組安全稽核命令

### 1.2 Skill vs Tool vs Agent

- **Tool（工具）**：系統提供的原子能力（例如 `exec`, `read`, `browser`, `message`, `cron`）。
- **Skill（技能包）**：在 Tool 之上提供「使用方式、限制、最佳實踐、範本」。
- **Agent（代理）**：會讀 SKILL.md，並在遵守安全規則下調用 Tools 去完成任務。

Skill 的價值不在於「新增工具」，而是把**怎麼用**寫成可反覆使用的規範。

---

## 2. 何時該做成 Skill？

適合做成 Skill 的情境：

1) **你重複做同一類事**（每週都要跑一樣的指令/流程）
2) **需要明確護欄**（例如涉及 token、付款、發訊息、控制設備）
3) **需要“有教學的工具”**（新手照文件能成功）
4) **需要隔離風險與權限**（某些能力只在特定環境/特定 policy 下開）

不適合做成 Skill 的情境：

- 一次性的專案筆記（放在 repo README/issue comment 就好）
- 完全不穩定、每天大改的臨時流程（先在筆記收斂再封裝）

---

## 3. Skill 的打包結構（Packaging）

### 3.1 建議目錄結構

（以下是常見、可維護的結構；實際以你 workspace 的 skills 目錄為準）

```
skills/<skill-name>/
  SKILL.md                 # 必填：技能文件（給人+模型）
  scripts/                 # 選用：執行腳本、helper
    ...
  assets/                  # 選用：圖片、範例輸入、fixture
  README.md                # 選用：給人類的補充（可省略，避免雙重來源）
```

### 3.2 `SKILL.md` 必備要素（建議）

為了讓 agent「穩定使用」，SKILL.md 建議至少包含：

- **用途（What / Why）**：這個 skill 解決什麼問題
- **何時用、何時不用（When to use / not use）**
- **前置條件（Prerequisites）**：需要哪些 token、哪些系統、哪些權限
- **最小可跑範例（Quick Start）**：3–10 步驟，照做就成功
- **安全邊界（Safety）**：哪些操作要詢問、哪些不能做
- **Troubleshooting**：最常見的 3–5 個錯誤與解法

---

## 4. SKILL.md 撰寫規範（讓模型真的能用）

### 4.1 寫作原則

- **指令要可執行**：不要只寫概念；要寫出具體命令、路徑、預期輸出。
- **避免隱性前提**：把「要先登入」「要先啟動 daemon」「要先 attach tab」寫出來。
- **用 checklist**：模型與人類都更不容易漏步驟。
- **把危險操作明確標示**：例如刪檔、覆寫、對外發訊息、提升權限。

### 4.2 範例模板

你可以用這個骨架：

```md
# <Skill name>

## What it does

## When to use

## Prerequisites

## Quick Start

## Recipes

## Safety / security notes

## Troubleshooting
```

---

## 5. 版本控制（Versioning）

### 5.1 建議做法：用 Git 當版本來源

- 每次改動 Skill：走 PR、review、merge
- 需要發布節點：用 tag（例如 `skills/twitter/v1.2.0`）或 release note

**為什麼不建議把版本寫死在文件裡？**

- SKILL.md 是提示/文件，常會微調文字；每次改字就 bump 版本會很吵
- 真正可追溯的是 git commit（誰改的、改了什麼）

### 5.2 破壞性變更（Breaking changes）

如果你改了：

- 參數/環境變數名稱
- 必要前置條件
- 主要 workflow

就應在 PR 描述與 changelog 明確標記，並在 SKILL.md 內提供升級指引。

---

## 6. 本機測試（Testing）

Skill 的測試通常不是單元測試（unit test），而是：

- **可重現的“流程測試”**（runbook test）
- **工具可用性測試**（tool contract）

### 6.1 最小測試清單（每次改動至少跑一次）

- Quick Start 能跑通
- 常用 recipe 能跑通
- 錯誤情境能被正確攔下（例如缺 token 時不會亂做）

### 6.2 測試建議：把輸入/輸出寫成樣板

例如：

- 範例 prompt
- 範例 config
- 預期輸出（成功/失敗各一份）

這可以讓 review 更快，也能降低「模型以為成功但其實沒做」的風險。

---

## 7. 安全邊界（Security / Safety）

### 7.1 風險分級（建議）

- **低風險**：純讀取（read-only）、純整理摘要
- **中風險**：寫檔（workspace 內）、建立 PR、改設定（但可回滾）
- **高風險**：對外發訊息（message）、執行 shell（exec）、控制真實裝置（nodes）、操作金流

### 7.2 寫在 Skill 裡的護欄

- 明確寫出「哪些行為必須先問使用者」
- 建議預設在 sandbox/workspace 操作
- 涉及 token/secret：說明儲存方式、輪替方式、避免貼到 log

---

## 8. 開發/更新 Skill 的工作流程

### 8.1 新增 Skill

1) 建目錄 `skills/<name>/`
2) 寫 `SKILL.md`（先有 Quick Start）
3) 需要腳本就加 `scripts/`
4) 實際跑一次 Quick Start
5) 提 PR，讓 reviewer 確認「照文件能跑通」

### 8.2 更新 Skill

- 先改文件（因為文件就是契約）
- 再改腳本/配置
- 最後更新 troubleshooting 與安全段落

---

## 9. 常見問題（Troubleshooting）

- **Skill 看起來“沒被載入”**：確認路徑、檔名是否正確（SKILL.md 大小寫）。
- **Quick Start 跑不通**：多半是前置條件沒寫清楚（token、daemon、權限）。
- **模型一直用錯工具**：SKILL.md 缺少「何時用/何時不用」與清楚的 recipe。
- **安全擔憂**：把高風險操作拆成兩步（先乾跑/列出計畫，再讓人類確認）。

---

## 10. Open questions（未來可改進）

- 是否需要統一的 Skill metadata schema（author/license/permissions）
- 是否需要自動化測試框架（headless + mocks）
- 是否需要 registry（類似 clawhub）與簽章驗證（防惡意 skill）

---

## 更新記錄

- 2026-02-18：由 outline 補齊為完整 deep-dive（初版）
