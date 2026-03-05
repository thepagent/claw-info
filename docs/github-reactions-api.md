# GitHub Reactions API 支援的 Emoji 類型

## 概述

GitHub Reactions API 讓你對 Issues、PRs、和Comments 添加表情符號反應。但需要注意的是，**GitHub API 只支援特定的 8 種 reaction 類型**，並非所有 emoji 都可以使用。

---

## 支援的 Reaction 類型

| API 值 | Emoji | 說明 | 使用場景 |
|--------|-------|------|----------|
| `+1` | 👍 | 認同、同意 | 認同提案、支持觀點 |
| `-1` | 👎 | 不認同 | 不同意某個方案 |
| `laugh` | 😄 | 好笑 | 對幽默內容的回應 |
| `confused` | 😕 | 困惑 | 需要進一步說明 |
| `heart` | ❤️ | 喜歡 | 表達喜愛或感謝 |
| `hooray` | 🎉 | 慶祝 | 慶祝功能發布、合併 |
| `rocket` | 🚀 | 部署、發布 | 部署成功、新版本發布 |
| `eyes` | 👀 | 關注、查看 | 正在查看、感興趣 |

---

## 不支援的 Emoji

以下 emoji **無法**透過 API 添加為 reaction：

- 🎯 dart（命中目標）
- 🔥 fire（火焰）
- 🎊 confetti（彩帶）
- 💯 hundred（滿分）
- 其他自定義 emoji
- 任何不在上述8 種列表中的 emoji

**原因：** GitHub Reactions API 有固定的 reaction 類型清單，不接受自訂 emoji。

---

## API 使用方式

### 添加 Reaction

```bash
# 對 Issue 添加 reaction
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  /repos/{owner}/{repo}/issues/{issue_number}/reactions \
  -f content='+1'

# 對PR 添加 reaction
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  /repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/reactions \
  -f content='rocket'
```

### 列出 Reactions

```bash
# 列出 Issue 的所有 reactions
gh api \
  -H "Accept: application/vnd.github+json" \
  /repos/{owner}/{repo}/issues/{issue_number}/reactions
```

### 刪除 Reaction

```bash
# 刪除特定 reaction
gh api \
  --method DELETE \
  -H "Accept: application/vnd.github+json" \
  /repos/{owner}/{repo}/issues/{issue_number}/reactions/{reaction_id}
```

---

## 替代方案

如果想要表達「命中目標」或「精準」的意思，可以使用：

| 想表達的意思 | 建議使用的 Reaction |
|--------------|---------------------|
| 命中目標、精準 | 🚀 `rocket`（發射、命中）|
| 看到了、命中 | 👀 `eyes`（看到了）|
| 認同 | 👍 `+1`（認同）|
| 慶祝成功 | 🎉 `hooray`（慶祝）|

---

## 常見問題

### Q: 為什麼不能用 🎯 dart？

**A:** GitHub Reactions API 的設計是基於固定的 reaction 類型清單，這個清單是在 API 設計初期就決定的。dart emoji 雖然在 GitHub 界面上可以使用，但**透過 API 添加時會返回錯誤**。

### Q: 可以添加自訂 emoji 嗎？

**A:** 不行。GitHub Reactions API 只支援上述 8 種 reaction，無法添加自訂 emoji。

### Q: 如何知道某個 comment 有哪些 reactions？

**A:** 可以使用 `gh api` 列出 reactions：

```bash
gh api /repos/{owner}/{repo}/issues/comments/{comment_id}/reactions
```

---

## 錯誤處理

當嘗試添加不支援的 reaction 時，API 會返回錯誤：

```json
{
  "message": "Invalid request.\n\nInvalid reaction: dart",
  "documentation_url": "https://docs.github.com/rest/reactions",
  "status": "422"
}
```

**建議：** 在程式碼中先檢查 reaction 類型是否在支援清單中：

```python
VALID_REACTIONS = ['+1', '-1', 'laugh', 'confused', 'heart', 'hooray', 'rocket', 'eyes']

def add_reaction(repo, issue_number, reaction_type):
    if reaction_type not in VALID_REACTIONS:
        print(f"不支援的 reaction: {reaction_type}")
        print(f"支援的類型: {', '.join(VALID_REACTIONS)}")
        return False
    
    # 呼叫 GitHub API
    # ...
```

---

## 參考文件

- [GitHub Reactions API 官方文件](https://docs.github.com/en/rest/reactions)
- [GitHub API Reaction Types](https://docs.github.com/en/rest/reactions/reactions#about-reactions)
- [相關討論：Reaction types issue](https://github.com/runatlantis/atlantis/issues/4842)

---

**標籤：** documentation, api, reactions  
**建立日期：** 2026-03-05  
**相關 Issue：** #239

---

*Maintained by thepagent*
