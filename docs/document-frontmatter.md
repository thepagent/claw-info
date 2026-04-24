---
last_validated: 2026-04-08
validated_by: masami-agent
---

# 文件 Frontmatter 規範

本文件定義 `docs/` 與 `usecases/` 目錄中文件 frontmatter 的最小慣例，作為 doc-review 類修補 PR 的一致依據。

## 適用範圍

- `docs/**/*.md`
- `usecases/**/*.md`

若文件暫時沒有 frontmatter，可依本文件補齊最小欄位。

## 標準欄位

| 欄位 | 必填 | 格式 | 說明 |
|------|------|------|------|
| `last_validated` | 建議 | `YYYY-MM-DD` | 最近一次人工重新確認內容仍與目前行為/文件定位相符的日期 |
| `validated_by` | 建議 | GitHub handle（例如 `masami-agent`） | 誰做了最近一次 validation |

## 最小範例

```yaml
---
last_validated: 2026-04-08
validated_by: masami-agent
---
```

## 填寫規則

### `last_validated`

- 使用 `YYYY-MM-DD`。
- 僅在實際重新檢查文件後更新，不要因為純格式調整就機械式刷新日期。
- 若 PR 同時修正文案錯誤、補齊缺漏欄位，且有重新檢查內容，可一併更新。

### `validated_by`

- 預設填寫執行驗證者當下使用的 GitHub handle。
- 目前 repo **以 GitHub handle 作為唯一標準格式**，避免同時混用顯示名稱、team 名稱或自由文字。
- 若維護者日後更名，不必回頭逐篇改舊文件；新一輪 validation 以新的 handle 覆寫即可，保留 metadata 的時間點語意。
- 若未來要全面改成更穩定的 identifier（例如 GitHub user id），應先更新本文件，再以獨立批次 PR 統一遷移；不要讓單篇文件自行分岔。

## 使用原則

- 這兩個欄位屬於**維護 metadata**，不應改變文件主體內容語意。
- doc-review 類 PR 應盡量維持「metadata-only」或明確切分 scope，避免把內容重寫與 frontmatter 補齊混在同一支 PR。
- 若 reviewer 對欄位格式有疑問，請以本文件作為對齊基準。

## See also

- [`README.md`](./README.md)
- [`STYLE_GUIDE.md`](./STYLE_GUIDE.md)
- [`../usecases/README.md`](../usecases/README.md)
