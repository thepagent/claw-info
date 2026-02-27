# OpenClaw 外部 Secrets 管理

> 引入版本：v2026.2.26 ([#26155](https://github.com/openclaw/openclaw/pull/26155))

## 概念

將 `openclaw.json` 中的敏感資訊（API key、token、service account 等）替換為 **SecretRef**，由 openclaw 在啟動時從外部來源解析實際值，永不將明文寫回設定檔。

## SecretRef 格式

```json
{
  "models": {
    "providers": {
      "my-provider": {
        "apiKey": {
          "source": "<provider>",
          ...
        }
      }
    }
  }
}
```

---

## Providers

### 1. `env` — 環境變數

```json
{
  "apiKey": {
    "source": "env",
    "name": "MY_API_KEY"
  }
}
```

- 從環境變數讀取
- 可設定 allowlist 限制可讀取的變數名稱

### 2. `file` — 檔案

```json
{
  "apiKey": {
    "source": "file",
    "path": "/run/secrets/my-api-key"
  }
}
```

- `singleValue` 模式：整個檔案內容即為 secret 值
- `json` 模式：使用 JSON Pointer 取特定欄位
- 路徑安全檢查：拒絕 symlink、路徑遍歷

### 3. `exec` — 執行外部程式

```json
{
  "apiKey": {
    "source": "exec",
    "argv": ["vault", "kv", "get", "-field=value", "secret/my-api-key"]
  }
}
```

openclaw 執行 `argv[0]`，從 stdout 讀取 secret 值。

**安全限制**：
- `argv` 固定，不可動態插值（防止注入）
- 最小化 env（不繼承父程序環境變數）
- timeout 限制（防止卡住 gateway 啟動）
- 拒絕 symlink（防止 `argv[0]` 被替換）

**可串接的外部工具**（需自行安裝並驗證）：

```bash
# HashiCorp Vault
vault kv get -field=value secret/my-api-key

# AWS Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id my-api-key \
  --query SecretString \
  --output text

# 1Password CLI
op read "op://vault/item/field"

# Azure Key Vault
az keyvault secret show \
  --vault-name my-vault \
  --name my-api-key \
  --query value \
  --output tsv
```

> ⚠️ `exec` 是非原生整合，openclaw 只讀取 stdout，不直接整合這些服務。

---

## CLI 子命令

```bash
openclaw secrets audit      # 掃描 config 中的明文 secrets
openclaw secrets configure  # 設定 provider 與 ref 對應
openclaw secrets apply      # 套用遷移計畫，清除明文（嚴格 target-path 驗證）
openclaw secrets reload     # 執行期熱重載（原子性，失敗保留舊值）
```

## 執行期行為

- gateway **啟動時**立即解析所有 SecretRef，失敗即中止（fail-fast）
- 解析結果存於**記憶體快照**，永不序列化回設定檔
- `reload` 為原子性操作：失敗時保留舊值，不影響運行中的 gateway

## 流程圖

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                  OpenClaw 外部 Secrets 管理 v2026.2.26                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐    SecretRef 契約                                    │
│  │  openclaw.json │───────────────────┐                                 │
│  │               │  { source,         │                                 │
│  │  apiKey ──────│──► provider, id }  │                                 │
│  │  token  ──────│──►                 │                                 │
│  │  serviceAcct ─│──►                 │                                 │
│  └───────────────┘                    │                                 │
│                                       ▼                                 │
│                        ┌─────────────────────────┐                      │
│                        │     Secrets 解析引擎      │                     │
│                        │  ┌─────────────────────┐ │                     │
│                        │  │ 啟動時立即解析所有 ref │ │                     │
│                        │  │ 失敗即中止（fail-fast）│ │                     │
│                        │  └─────────────────────┘ │                     │
│                        └────┬───────┬───────┬─────┘                     │
│                             │       │       │                           │
│              ┌──────────────┼───────┼───────┼──────────────┐            │
│              ▼              ▼       │       ▼              │            │
│  ┌───────────────┐ ┌──────────────┐│┌──────────────────┐  │            │
│  │  env provider │ │ file provider│││  exec provider   │  │            │
│  ├───────────────┤ ├──────────────┤│├──────────────────┤  │            │
│  │ 環境變數讀取   │ │ json 模式    ││ │ 執行外部程式     │  │            │
│  │ 可選 allowlist │ │  (JSON Ptr)  │││ 固定 argv        │  │            │
│  │               │ │ singleValue  │││ 最小 env         │  │            │
│  │  $MY_API_KEY  │ │  模式        │││ timeout 限制     │  │            │
│  │               │ │ 路徑安全檢查  │││ 拒絕 symlink     │  │            │
│  └───────────────┘ └──────────────┘│└────────┬─────────┘  │            │
│                                    │         │            │            │
│              ┌─────────────────────┘         │            │            │
│              │                               ▼            │            │
│              │              ┌──────────────────────────┐  │            │
│              │              │  可串接外部 CLI 工具：     │  │            │
│              │              │  ├─ vault kv get ...     │  │            │
│              │              │  ├─ aws secretsmanager   │  │            │
│              │              │  ├─ op read (1Password)  │  │            │
│              │              │  └─ az keyvault ...      │  │            │
│              │              │  ⚠ 非原生整合，透過 exec  │  │            │
│              │              └──────────────────────────┘  │            │
│              └───────────────────────────────────────────-┘            │
│                                       │                                 │
│                                       ▼                                 │
│                        ┌─────────────────────────┐                      │
│                        │    執行期記憶體快照        │                     │
│                        │  ┌─────────────────────┐ │                     │
│                        │  │ 原子性啟用／切換     │ │                     │
│                        │  │ reload 失敗保留舊值  │ │                     │
│                        │  │ 永不序列化回設定檔   │ │                     │
│                        │  └─────────────────────┘ │                     │
│                        └────────────┬────────────┘                      │
│                                     │                                   │
│                                     ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        CLI 子命令                                 │   │
│  │  openclaw secrets audit      ← 檢查目前 secrets 狀態             │   │
│  │  openclaw secrets configure  ← 設定 provider 與 ref 對應         │   │
│  │  openclaw secrets apply      ← 套用遷移計畫，清除明文            │   │
│  │  openclaw secrets reload     ← 執行期重新載入（原子性）           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

*參考：[v2026.2.26 Release Notes](https://github.com/openclaw/openclaw/releases/tag/v2026.2.26)*
