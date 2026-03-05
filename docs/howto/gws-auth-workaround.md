# gws CLI 401 認證錯誤 - Workaround

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

## 根本原因

`gws` CLI 無法在 API 呼叫時正確讀取加密的憑證檔案 (`credentials.enc`)：

- 憑證儲存位置：`~/Library/Application Support/gws/credentials.enc`
- 加密方式：AES-256-GCM
- `gws auth status` 可以正確讀取並驗證
- 但 API 呼叫時無法解密或載入憑證，導致 401 錯誤

## 解決方案

使用 `gws auth export --unmasked` 匯出未加密的憑證，並透過環境變數指定。

### 步驟

```bash
# 1. 匯出未加密的憑證
gws auth export --unmasked > ~/.ssh/gws-credentials.json

# 2. 設定適當權限
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
3. **文件化**：將此 workaround 分享給團隊成員

## 影響範圍

- **影響版本**：`@googleworkspace/cli` v0.4.1
- **影響情境**：使用加密憑證儲存的使用者
- **不受影響**：使用 Service Account 或 Access Token 的方式

## 後續行動

- [ ] 監控 [@googleworkspace/cli GitHub](https://github.com/googleworkspace/cli) 是否有相關 issue
- [ ] 向專案回報此 bug
- [ ] 新版本發布後測試是否修復

## 相關文件

- [gws CLI 授權範圍控制指南](./gws-cli-scoped-auth.md)

---

**發現者：** @tboydar-agent  
**日期：** 2026-03-05  
**狀態：** Workaround 已驗證有效
