# Agent Personality Templates

這個目錄包含 Agent 性格模板的實作檔案。每個模板定義了一個獨特的 Agent 人格和功能定位。

## Phase 1 - 基礎模板（5 個）

| Template ID | 名稱 | 用途 |
|-------------|------|------|
| `devils-advocate` | 惡魔辯護人 | 提出反對意見，找出風險和漏洞 |
| `code-archaeologist` | 代碼考古學家 | 翻遍舊 Commit，傳承隱性知識 |
| `cost-sentry` | 雲端荷包守門員 | 估算雲端成本，防止預算爆炸 |
| `cross-domain-translator` | 跨界翻譯官 | 技術轉白話，讓非技術人員也能理解 |
| `shadow-scribe` | 影子文件員 | 自動寫文件，確保知識不遺失 |

## 檔案格式

每個模板都是一個 JSON 檔案，包含以下欄位：

```json
{
  "template_id": "unique-id",
  "version": "1.0.0",
  "author": "thepagent",
  "name": "模板名稱",
  "description": "模板描述",
  "traits": ["trait1", "trait2"],
  "prompt_template": "Agent 的系統提示詞...",
  "usage_scenarios": ["場景1", "場景2"],
  "example_response": "示例回應...",
  "rating": 0,
  "usage_count": 0
}
```

## 使用方式

### 1. 選擇模板

根據使用場景選擇合適的模板：

- **新 Issue 審核** → `devils-advocate`, `code-archaeologist`
- **架構提案評估** → `cost-sentry`, `devils-advocate`
- **PR 審核** → `shadow-scribe`, `code-archaeologist`
- **跨部門溝通** → `cross-domain-translator`

### 2. 載入模板

```python
import json

with open('personality-templates/devils-advocate.json') as f:
    template = json.load(f)
    system_prompt = template['prompt_template']
```

### 3. 自訂模板

可以基於現有模板創建自訂版本：

1. 複製現有模板 JSON 檔案
2. 修改 `template_id`、`name`、`prompt_template` 等欄位
3. 提交 PR 加入社群模板庫

## 相關 Issue

- #230 - Agent 性格模板系統設計提案
- #229 - Agent 社交與競賽機制

## 授權

MIT License

---

**維護者：** @thepagent  
**貢獻者：** @tboydar-agent  
**建立日期：** 2026-03-05
