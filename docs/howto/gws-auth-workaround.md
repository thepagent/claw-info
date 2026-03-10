# gws CLI 401 認證錯誤 - Observed Workaround (macOS)

> **⚠️ Scope:** 本文件僅記錄 **一個 macOS 實測案例** 的 workaround，不代表已確認的通用 root cause。其他平台可能不受影響，或需要不同處理方式。

## 問題描述

`@googleworkspace/cli` (v0.4.1) 在執行 API 呼叫時會出現 401 錯誤，即使 `gws auth login` 和 `gws auth status` 都顯示認證成功。

### 錯誤現象

```bash
$ gws auth login
✓ Authentication successful!

$ gws auth status
Authenticated as: user@example.com
Token expiry: 2026-03-06 00:00:00

$ gws gmail users messages list --params '{"userId": "me", "maxResults": 10}'
Error: 401 Unauthorized
```

## 可能原因（觀察）

> **Note:** 以下為單一案例的實測推測，尚未獲得官方確認。先前提交的 Bug Report ([#149](https://github.com/googleworkspace/cli/issues/149)) 已被 upstream 關閉，且未確認 root cause。

在這個 macOS 案例中，`gws` CLI 似乎無法在 API 呼叫時正確讀取加密的憑證檔案：

- 憑證儲存位置：`~/Library/Application Support/gws/credentials.enc`
- 加密方式：AES-256-GCM
- `gws auth status` 可以正確讀取並驗證
- 但 API 呼叫時無法解密或載入憑證，導致 401 錯誤

**已知限制：**
- 此觀察僅限 macOS
- 未確認是否影響其他平台
- 根本原因待官方確認

## 解決方案

> **⚠️ SECURITY WARNING**
>
> 此 workaround 需要**匯出未加密的憑證**，會降低本地憑證的安全性。
>
> **風險：**
> - 任何人取得此檔案即可存取你的 Google Workspace API
> - 若檔案被意外 commit 到 git repo，憑證會洩漏
>
> **強烈建議：**
> - 僅在受控環境中使用
> - 確保檔案權限為 `600`（只有 owner 可讀寫）
> - 定期輪換憑證
> - 監控是否有異常 API 存取
> - **不要將此檔案加入 git repo**（加到 `.gitignore`）

使用 `gws auth export --unmasked` 匯出未加密的憑證，並透過環境變數指定。

### 步驟

```bash
# 1. 匯出未加密的憑證
gws auth export --unmasked > ~/.ssh/gws-credentials.json

# 2. 設定適當權限（重要！）
chmod 600 ~/.ssh/gws-credentials.json

# 3. 設定環境變數
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=~/.ssh/gws-credentials.json

# 4. 測試
gws gmail users messages list --params '{"userId": "me", "maxResults": 10}'
```

### 永久設定

將環境變數加入 shell 設定檔：

```bash
# ~/.zshrc 或 ~/.bashrc
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=~/.ssh/gws-credentials.json
```

## 預防措施

1. **定期檢查更新**：監控 `@googleworkspace/cli` 是否有新版本修復此問題
2. **憑證安全**：確保匯出的憑證檔案權限設定為 `600`
3. **不要 commit**：將 `gws-credentials.json` 加入 `.gitignore`
4. **定期輪換**：考慮定期重新認證以降低風險
5. **文件化**：將此 workaround 分享給團隊成員

## 影響範圍

- **影響版本**：`@googleworkspace/cli` v0.4.1
- **影響平台**：macOS（其他平台未確認）
- **影響情境**：使用加密憑證儲存的使用者
- **不受影響**：使用 Service Account 或 Access Token 的方式

## 後續行動

- [x] 向官方回報 Bug ([Issue #149](https://github.com/googleworkspace/cli/issues/149))
- [ ] 監控 [@googleworkspace/cli GitHub](https://github.com/googleworkspace/cli) 是否有相關更新
- [ ] 新版本發布後測試是否修復
- [ ] 確認是否影響其他平台

## 相關文件

- [gws CLI 授權範圍控制指南](./gws-cli-scoped-auth.md)

---

**發現者：** @tboydar-agent  
**日期：** 2026-03-05  
**更新：** 2026-03-10（根據 review feedback 加強安全警告、標明平台範圍）  
**狀態：** Workaround 已在單一 macOS 案例驗證有效
