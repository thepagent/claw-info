# Google Workspace CLI (`gws`) 授權範圍控制指南

本文說明如何為 agent 使用的 Google Workspace CLI (`gws`) 設定最小權限授權，限制存取範圍到特定資料夾，並補充其他服務的特殊考量。

## 問題情境

當 agent 需要操作外部服務（如 Google Drive、Gmail、AWS）時，若授予完整權限會有以下風險：

- **資料外洩**：agent 可存取所有檔案、郵件
- **誤操作**：agent 可能刪除或修改重要資料
- **權限濫用**：憑證外洩時攻擊者取得完整存取

**目標**：限制 agent 只能操作特定範圍（如特定資料夾），即使憑證外洩也無法存取其他資源。

---

## Google Workspace CLI (`gws`)

### OAuth Scope 選擇

`gws` 的權限範圍由 OAuth scope 決定，在 `gws auth login` 時設定：

| Scope | 權限範圍 | 敏感度 | 適用場景 |
|-------|---------|--------|----------|
| `drive.file` | 只能存取 App 建立或使用者選擇的檔案 | Non-sensitive ✅ | 新建檔案為主 |
| `drive.appfolder` | 只能存取 App 專屬隱藏資料夾 | Non-sensitive | App 專用資料 |
| `drive.readonly` | 唯讀存取所有檔案 | Restricted ⚠️ | 唯讀需求 |
| `drive` | 完整存取所有檔案 | Restricted ❌ | 需避免 |

**最佳實務**：避免使用完整的 `drive` scope。

### 登入時選擇 Scopes

```bash
# 唯讀模式（最安全）
gws auth login --readonly

# 自訂 scopes（推薦：只請求需要的權限）
gws auth login --scopes "https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/spreadsheets.readonly"

# 完整存取（不推薦）
gws auth login --full
```

---

## 方案一：Service Account + 資料夾分享（推薦）

這是最乾淨的權限隔離方式。

### 設定步驟

1. **建立 Service Account**

在 Google Cloud Console 建立 Service Account 並下載 JSON key：

```bash
# Service Account email 格式
my-agent@my-project.iam.gserviceaccount.com
```

2. **在 Drive UI 分享資料夾**

在 Google Drive 網頁介面中，將目標資料夾分享給 Service Account 的 email：

- 右鍵點擊資料夾 → 分享
- 輸入 Service Account email
- 選擇適當權限（檢視者/編輯者）

3. **使用 Service Account 執行 CLI**

```bash
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/path/to/service-account.json

# 只列出該資料夾下的檔案
gws drive files list --params '{"q": "'<folder_id>' in parents"}'
```

### 權限限制效果

| 操作 | 結果 |
|------|------|
| 列出 My Drive | ❌ 空白（無法存取） |
| 列出 Shared Drives | ❌ 無法存取 |
| 存取已分享資料夾 | ✅ 可存取 |
| 存取其他資料夾 | ❌ 權限錯誤 |

---

## 方案二：Shared Drives（共用雲端硬碟）

適合團隊協作場景。

### 設定步驟

1. 建立專門的 Shared Drive 給 Agent 使用
2. 設定 Service Account 為該 Shared Drive 的成員
3. 可限制權限等級（檢視者/評論者/編輯者）

```bash
# 列出可用的 Shared Drives
gws drives list --params '{"useDomainAdminAccess": false}'

# 操作特定 Shared Drive
gws drive files list --params '{"driveId": "<shared_drive_id>", "corpus": "drive"}'
```

### 權限等級

| 角色 | 權限 |
|------|------|
| 檢視者 (reader) | 僅檢視 |
| 評論者 (commenter) | 檢視 + 留言 |
| 編輯者 (writer) | 編輯檔案 |
| 管理者 (organizer) | 管理成員、刪除檔案 |

---

## 方案三：使用 `drive.file` Scope

適合以建立新檔案為主的場景。

### 特性

- App 只能存取自己建立的檔案
- 使用者透過 Google Picker 選擇分享給 App 的檔案
- 無法存取使用者的其他檔案

### 設定

```bash
gws auth login --scopes "https://www.googleapis.com/auth/drive.file"
```

### 限制

- 無法存取既有檔案（除非使用者手動選擇）
- 需要整合 Google Picker API 才能讓使用者選擇檔案
- 適合「App 自建檔案」的使用模式

---

## 方案四：Domain-Wide Delegation（企業環境）

適用於 Google Workspace 企業帳號。

### 設定方式

1. Admin 在 Admin Console 啟用 Domain-Wide Delegation
2. 設定 Service Account 可模擬的使用者範圍
3. Admin 可透過 API 控制檔存取範圍

```bash
# 模擬特定使用者
export GOOGLE_WORKSPACE_CLI_IMPERSONATED_USER=user@company.com
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/path/to/service-account.json
gws drive files list
```

### 注意事項

- 需要 Google Workspace 管理員權限
- Service Account 仍可存取該使用者的所有資料
- 適合「代理人」場景，非權限隔離

---

## 方案比較

| 方案 | 資料夾級控制 | 複雜度 | 適用場景 |
|------|-------------|--------|----------|
| Service Account + 分享資料夾 | ✅ 完整 | 低 | 個人/小團隊（推薦） |
| Shared Drives | ✅ 完整 | 中 | 團隊協作 |
| `drive.file` scope | ⚠️ 需 Picker | 低 | 新建檔案為主 |
| Domain-Wide Delegation | ❌ 全帳號 | 高 | 企業代理人 |

---

## 其他 Google Workspace 服務

Drive 的 Service Account + 分享機制同樣適用於其他 Google Workspace 服務：

### Sheets / Docs / Slides

這些檔案本質上是 Drive 檔案，**繼承 Drive 的權限設定**。Service Account 只要能存取所在的 Drive 資料夾，就能操作其中的 Sheets/Docs/Slides。

```bash
# 存取試算表（需先分享所在資料夾給 Service Account）
gws sheets spreadsheets get --params '{"spreadsheetId": "..."}'
```

### Gmail

Gmail 沒有資料夾級權限，只有 mailbox 級 scope：

| Scope | 權限 |
|-------|------|
| `gmail.readonly` | 唯讀所有郵件 |
| `gmail.modify` | 讀取、修改、刪除 |
| `gmail.send` | 發送郵件 |

**無法**限制只能存取特定標籤或郵件。若需隔離，考慮建立獨立的 Google 帳號。

### Calendar

Calendar 支援日曆級分享，類似 Drive 資料夾：

1. 在 Google Calendar UI 分享特定日曆給 Service Account
2. 使用 `calendar` scope 存取

```bash
# 列出可存取的日曆
gws calendar calendarList list
```

---

## Troubleshooting

### Service Account 無法存取資料夾

**症狀**：執行 `gws drive files list` 返回空白或權限錯誤

**可能原因**：
1. 未在 Drive UI 分享資料夾給 Service Account
2. Service Account 與使用者屬於不同 Google Workspace 組織

**處理方式**：
```bash
# 確認 Service Account email
cat $GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE | jq -r '.client_email'

# 在 Drive UI 右鍵資料夾 → 分享 → 輸入上述 email
```

### OAuth Scope 錯誤

**症狀**：`Error 403: insufficient permissions`

**可能原因**：請求的 scope 不足

**處理方式**：
```bash
# 檢查已授權的 scopes
gws auth status

# 重新登入請求更大範圍的 scope
gws auth login --scopes "https://www.googleapis.com/auth/drive"
```

### Domain-Wide Delegation 失敗

**症狀**：`Error 403: unauthorized_client`

**可能原因**：
1. Admin 未啟用 Domain-Wide Delegation
2. 模擬的使用者不在允許清單

**處理方式**：請 Workspace Admin 檢查 Admin Console → Security → API controls

---

## 安全注意事項

1. **憑證保存**：Service Account JSON key 應妥善保管，勿提交至版控
2. **定期輪替**：定期更換 Service Account key
3. **最小權限**：永遠只請求必要的 scope
4. **監控使用**：透過 Google Admin Console 監控 API 呼叫
5. **測試驗證**：部署前測試權限邊界是否如預期

---

## See Also

- [gws CLI GitHub](https://github.com/googleworkspace/cli)
- [Google Drive API Scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Google Service Account 文件](https://cloud.google.com/iam/docs/service-accounts)