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

## 實戰範例：環境變數（最簡單）

> 版本要求：v2026.2.26+

即使使用 `env` source，也**必須先定義 `secrets.providers` 區塊**，否則會報錯：
```
models.providers.<name>.apiKey: Invalid input
```

### 完整設定範例

```json
{
  "secrets": {
    "providers": {
      "env-provider": {
        "source": "env"
      }
    }
  },
  "models": {
    "providers": {
      "ollama-cloud": {
        "baseUrl": "https://ollama.com/v1",
        "apiKey": {
          "source": "env",
          "provider": "env-provider",
          "id": "OPENAI_API_KEY"
        },
        "api": "openai-completions"
      }
    }
  }
}
```

SecretRef 三個必填欄位：
- `source`: `"env"`
- `provider`: 對應 `secrets.providers` 中的 key
- `id`: 環境變數名稱

### Kubernetes Secret 整合

```bash
# 建立 Secret
kubectl create secret generic openclaw-env-secret -n openclaw \
  --from-literal=OPENAI_API_KEY=your-api-key-here
```

```yaml
# Helm values.yaml
app-template:
  controllers:
    main:
      containers:
        main:
          envFrom:
            - secretRef:
                name: openclaw-env-secret
```

---

## 實戰範例：AWS Secrets Manager

以下為將 `ollama-cloud` provider 的 `apiKey` 遷移至 AWS Secrets Manager 的完整流程。

### 架構圖

```text
┌─────────────────────────────────────────────────────────────────┐
│                        openclaw gateway                         │
│                                                                 │
│  openclaw.json                                                  │
│  ┌─────────────────────────────────────────┐                   │
│  │ ollama-cloud.apiKey:                    │                   │
│  │   { source: "exec",                     │                   │
│  │     provider: "aws_secrets_manager",    │                   │
│  │     id: "ollama-cloud-apikey" }         │                   │
│  └────────────────────┬────────────────────┘                   │
│                       │ 啟動時解析 SecretRef                    │
│                       ▼                                         │
│  ┌────────────────────────────────────────┐                    │
│  │         Secrets 解析引擎               │                    │
│  │  1. 找到 provider: aws_secrets_manager │                    │
│  │  2. 執行 command (exec source)         │                    │
│  └────────────────────┬───────────────────┘                    │
│                       │ spawn                                   │
│                       ▼                                         │
│  ┌────────────────────────────────────────┐                    │
│  │       ~/bin/aws-wrapper.sh             │                    │
│  │  (user-owned, chmod 700)               │                    │
│  │                                        │                    │
│  │  exec aws secretsmanager               │                    │
│  │    get-secret-value                    │                    │
│  │    --secret-id openclaw/secrets        │                    │
│  └────────────────────┬───────────────────┘                    │
│                       │ stdout                                  │
└───────────────────────┼─────────────────────────────────────────┘
                        │ AWS API call
                        ▼
          ┌─────────────────────────────┐
          │    AWS Secrets Manager      │
          │    secret: openclaw/secrets │
          │  ┌──────────────────────┐   │
          │  │ {                    │   │
          │  │  "ollama-cloud-      │   │
          │  │    apikey": "sk-..." │   │
          │  │ }                    │   │
          │  └──────────────────────┘   │
          └─────────────────────────────┘
                        │
                        │ JSON response
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  aws-wrapper.sh 輸出（exec protocol v1）：                       │
│  {                                                              │
│    "protocolVersion": 1,                                        │
│    "values": { "ollama-cloud-apikey": "sk-..." }               │
│  }                                                              │
│                       │                                         │
│                       ▼                                         │
│  Secrets 解析引擎取出 values["ollama-cloud-apikey"]              │
│  → 注入記憶體，永不寫回 openclaw.json                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1. 建立 Secret（JSON 格式，可存多個 key）

```bash
aws secretsmanager create-secret \
  --profile bedrock-only \
  --region us-east-1 \
  --name "openclaw/secrets" \
  --secret-string '{"ollama-cloud-apikey": "your-api-key-here"}'
```

> 建議用單一 JSON secret 存放所有 openclaw 相關 key，方便統一管理。

### 2. 建立 exec provider wrapper script

openclaw exec provider 要求 `command` 必須由當前使用者擁有（不可為 root 擁有或 symlink）。建立 wrapper：

```bash
cat > ~/bin/aws-wrapper.sh << 'EOF'
#!/bin/bash
RAW=$(/usr/local/bin/aws --profile bedrock-only secretsmanager get-secret-value \
  --region us-east-1 \
  --secret-id openclaw/secrets \
  --query SecretString --output text)
python3 -c "import json,sys; values=json.loads(sys.stdin.read()); print(json.dumps({'protocolVersion':1,'values':values}))" <<< "$RAW"
EOF
chmod 700 ~/bin/aws-wrapper.sh
```

exec provider 期望 stdout 輸出格式：

```json
{ "protocolVersion": 1, "values": { "ollama-cloud-apikey": "..." } }
```

### 3. 設定 exec provider（`openclaw.json`）

```json
{
  "secrets": {
    "providers": {
      "aws_secrets_manager": {
        "source": "exec",
        "command": "/home/pahud/bin/aws-wrapper.sh",
        "timeoutMs": 3000,
        "jsonOnly": false
      }
    }
  }
}
```

### 4. 套用 SecretRef（`secrets apply` plan）

```json
{
  "version": 1,
  "protocolVersion": 1,
  "targets": [
    {
      "type": "models.providers.apiKey",
      "path": "models.providers.ollama-cloud.apiKey",
      "providerId": "ollama-cloud",
      "ref": {
        "source": "exec",
        "provider": "aws_secrets_manager",
        "id": "ollama-cloud-apikey"
      }
    }
  ],
  "options": { "scrubEnv": true }
}
```

```bash
openclaw secrets apply --from /tmp/secrets-plan.json --dry-run  # 預覽
openclaw secrets apply --from /tmp/secrets-plan.json            # 套用
```

### 5. 套用後的 `openclaw.json`（apiKey 欄位）

```json
{
  "models": {
    "providers": {
      "ollama-cloud": {
        "baseUrl": "https://ollama.com/v1",
        "apiKey": {
          "source": "exec",
          "provider": "aws_secrets_manager",
          "id": "ollama-cloud-apikey"
        },
        "api": "openai-completions"
      }
    }
  }
}
```

### 6. 驗證

```bash
openclaw secrets audit  # plaintext=0 即成功
```

### IAM 權限需求

`BotBedrockRole`（或對應 permission set）需要：

```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:CreateSecret",
    "secretsmanager:PutSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:openclaw/*"
}
```

若使用 IAM Identity Center，需透過 `sso-admin put-inline-policy-to-permission-set` 附加，再 `provision-permission-set` 生效。

---

*參考：[v2026.2.26 Release Notes](https://github.com/openclaw/openclaw/releases/tag/v2026.2.26)*
