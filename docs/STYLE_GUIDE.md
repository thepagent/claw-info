# OpenClaw Docs Style Guide（寫作規約）

本文件定義 `docs/` 目錄下文件的統一寫作風格與結構，目標是：**可快速掃描、可直接照做、可排查問題、可長期維護**。

> 適用範圍：本 repo 的 `docs/*.md` 與 `docs/**.md`（含 `docs/core/` 深度文件）。

---

## 1) 寫作目標

每篇文件至少要讓讀者做到以下三件事：

1. **知道這是什麼（What）**：核心名詞與邊界清楚。
2. **知道何時用（When/Why）**：典型使用情境與取捨。
3. **知道怎麼用（How）**：給出可複製的操作步驟，並能自助排查（Troubleshooting）。

---

## 2) 統一文件骨架（建議模板）

> 並非每篇都要 100% 全部章節，但建議依序排列，讀者會更好找。

1. **標題（H1）**
2. **概述 / TL;DR**（3～7 個 bullet）
3. **解決的問題（Problems）/ 使用情境（Use cases）**
4. **核心概念（Core concepts）**
   - 名詞定義、限制、心智模型
   - 可以用 ASCII 圖輔助（推薦）
5. **操作指引（How-to）**
   - 步驟化、可複製
   - 每個步驟寫清楚「前置條件」
6. **範例（Examples）**
   - 先最小可行（minimal）再進階
7. **最佳實務 / Anti-patterns**
8. **Troubleshooting**（症狀 → 可能原因 → 解法）
9. **安全注意事項（Security notes）**（若相關）
10. **版本 / 相依（Compatibility）**（若相關）
11. **相關連結（See also）**（同 repo 其他 docs、issues/PR）

---

## 3) Markdown 規範

- **標題層級**：
  - 每篇文件只有一個 `# H1`。
  - 章節用 `##`，子章節用 `###`。
- **清單優先**：能用 bullet/number list 說清楚就不要長段落。
- **表格**：用於對照（例如 decision table / matrix）很好；但過寬表格要小心手機閱讀。
- **連結**：
  - repo 內連結用相對路徑（例如 `./cron.md`）。
  - issue/PR 用 `#123`（若跨 repo 則用完整 URL）。
- **避免太花的格式**：這些 docs 主要在 GitHub 上閱讀，保持簡潔穩定。

---

## 4) 程式碼與指令區塊規範

### 4.1 指令可複製

- 以 fenced code block 呈現：

```bash
# comment: what this does
openclaw status
```

- **每段指令**盡量可獨立執行，必要時在前面寫清楚：
  - 需要的環境變數（例如 token）
  - 需要的權限（例如 repo write、device permission）
  - 工作目錄（例如 `cd ...`）

### 4.2 輸出示例

- 若提供輸出示例，請標註「示意」，避免讀者誤把值當真。
- 不要把敏感資訊寫進示例：token、cookie、私密 URL、真實 phone/chat id。

---

## 5) 內容寫作規範

- **語言**：以繁體中文為主；必要術語可保留英文（如 session、gateway）。
- **名詞一致**：同一概念不要一篇叫 A、一篇叫 B；若有別名，第一次出現時註明。
- **先說邊界**：例如「這不做什麼 / 不保證什麼」。
- **先講風險再給指令**：若指令可能發送訊息、刪除資料、改設定，先提醒。

---

## 6) Troubleshooting 寫法（建議格式）

每個問題建議用同一種寫法，方便快速掃描：

- **症狀**：看到什麼？（錯誤訊息/現象）
- **可能原因**：1～3 個常見原因
- **處理方式**：具體步驟，能複製的指令最好

---

## 7) PR / Review Checklist（作者自檢）

提交 PR 前，請自查：

- [ ] 文件標題與檔名一致，且檔名語意清楚
- [ ] TL;DR 不超過 7 點，且每點都是「結論」不是背景
- [ ] 指令區塊可複製，且有前置條件說明
- [ ] 範例沒有包含敏感資訊
- [ ] 有 Troubleshooting（至少 3 條常見問題，若此主題可能踩坑）
- [ ] 有連到相關 docs / issue / PR（See also）

---

## 8) 建議檔名慣例

- 概念型（core）：`docs/core/<topic>.md`
- 操作型（how-to）：`docs/<topic>_howto.md` 或 `<topic>.md`（視既有慣例）
- 運維/流程：`docs/<topic>_ops.md` 或 `docs/<topic>.md`

---

## 9) See also

- `docs/README.md`（文件索引）
