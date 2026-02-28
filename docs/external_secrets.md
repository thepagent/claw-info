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

# 阿里雲 Secrets Manager (使用 JSON 輸出更穩健)
aliyun kms GetSecretValue \
  --SecretName my-secret \
  --region cn-hangzhou \
  --output json | jq -r '.Data.SecretData'

# 注意：Aliyun CLI/API 回應格式可能因版本/區域而異
# 建議先查看完整 JSON 回應再調整 jq 解析欄位
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

## 實戰範例：阿里雲 Secrets Manager

以下為將 `ollama-cloud` provider 的 `apiKey` 遷移至阿里雲 Secrets Manager（凭据管家）的完整流程。

### 架構圖

```text
┌─────────────────────────────────────────────────────────────────┐
│                        openclaw gateway                         │
│                                                                 │
│  openclaw.json                                                  │
│  ┌─────────────────────────────────────────┐                   │
│  │ ollama-cloud.apiKey:                    │                   │
│  │   { source: "exec",                     │                   │
│  │     provider: "aliyun_secrets_manager", │                   │
│  │     id: "ollama-cloud-apikey" }         │                   │
│  └────────────────────┬────────────────────┘                   │
│                       │ 啟動時解析 SecretRef                    │
│                       ▼                                         │
│  ┌────────────────────────────────────────┐                    │
│  │         Secrets 解析引擎               │                    │
│  │  1. 找到 provider: aliyun_secrets_mgr  │                    │
│  │  2. 執行 command (exec source)         │                    │
│  └────────────────────┬───────────────────┘                    │
│                       │ spawn                                   │
│                       ▼                                         │
│  ┌────────────────────────────────────────┐                    │
│  │       ~/bin/aliyun-wrapper.sh          │                    │
│  │  (user-owned, chmod 700)               │                    │
│  │                                        │                    │
│  │  aliyun kms GetSecretValue             │                    │
│  │    --SecretName openclaw/secrets       │                    │
│  └────────────────────┬───────────────────┘                    │
│                       │ stdout                                  │
└───────────────────────┼─────────────────────────────────────────┘
                        │ Aliyun API call
                        ▼
          ┌─────────────────────────────────────┐
          │    阿里雲 Secrets Manager           │
          │    (凭据管家)                       │
          │    secret: openclaw/secrets         │
          │  ┌────────────────────────────┐     │
          │  │ {                          │     │
          │  │  "ollama-cloud-            │     │
          │  │    apikey": "sk-..."       │     │
          │  │ }                          │     │
          │  └────────────────────────────┘     │
          └─────────────────────────────────────┘
                        │
                        │ JSON response
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  aliyun-wrapper.sh 輸出（exec protocol v1）：                    │
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

### 1. 安裝阿里雲 CLI

```bash
# macOS
brew install aliyun-cli

# Linux
curl -O https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz
tar xzf aliyun-cli-linux-latest-amd64.tgz
sudo mv aliyun /usr/local/bin/
```

配置認證：

```bash
aliyun configure
# 輸入 Access Key ID、Access Key Secret、Region ID（如 cn-hangzhou）
```

### 2. 建立 Secret（JSON 格式，可存多個 key）

```bash
# 建立通用凭据
aliyun kms CreateSecret \
  --SecretName "openclaw/secrets" \
  --SecretData '{"ollama-cloud-apikey": "your-api-key-here"}' \
  --VersionId "v1" \
  --SecretDataType "text" \
  --region cn-hangzhou
```

> 建議用單一 JSON secret 存放所有 openclaw 相關 key，方便統一管理。

### 3. 建立 exec provider wrapper script

openclaw exec provider 要求 `command` 必須由當前使用者擁有（不可為 root 擁有或 symlink）。建立 wrapper：

```bash
cat > ~/bin/aliyun-wrapper.sh << 'EOF'
#!/bin/bash
set -euo pipefail

# OpenClaw exec provider wrapper for Aliyun Secrets Manager
# Reads secrets and outputs in OpenClaw exec protocol format

SECRET_NAME="${1:-openclaw/secrets}"
REGION="${2:-cn-hangzhou}"

# Fetch secret value as JSON
# Note: Aliyun CLI/API response format may vary by version/region
RAW=$(aliyun kms GetSecretValue \
  --SecretName "$SECRET_NAME" \
  --region "$REGION" \
  --output json 2>/dev/null) || {
  echo '{"protocolVersion":1,"values":{},"errors":{"_resolver":{"message":"Failed to fetch secret"}}}' 
  exit 1
}

# Extract SecretData using jq (more robust than parsing table output)
SECRET_DATA=$(echo "$RAW" | jq -r '.Data.SecretData // empty')

if [ -z "$SECRET_DATA" ]; then
  echo '{"protocolVersion":1,"values":{},"errors":{"_resolver":{"message":"SecretData field not found"}}}' 
  exit 1
fi

# Output in OpenClaw exec protocol format
# Assumes SecretData is already a JSON object with key-value pairs
echo "$SECRET_DATA" | jq -c '{protocolVersion: 1, values: .}'
EOF
chmod 700 ~/bin/aliyun-wrapper.sh
```

> **為什麼用 `--output json` + `jq`？**  
> 表格輸出 (`cols/rows`) 對多行內容、CLI 版本差異、錯誤訊息非常敏感。JSON 解析更穩健，且 `jq` 廣泛預裝於現代 Linux/macOS。

exec provider 期望 stdout 輸出格式：

```json
{ "protocolVersion": 1, "values": { "ollama-cloud-apikey": "..." } }
```

> **注意**：Aliyun CLI/API 回應格式可能因版本或區域而異。若 `jq` 解析失敗，建議先執行 `aliyun kms GetSecretValue --output json` 查看完整回應結構，再調整 `.Data.SecretData` 路徑。

### 4. 設定 exec provider（`openclaw.json`）

```json
{
  "secrets": {
    "providers": {
      "aliyun_secrets_manager": {
        "source": "exec",
        "command": "/home/user/bin/aliyun-wrapper.sh",
        "timeoutMs": 5000,
        "jsonOnly": false
      }
    }
  }
}
```

### 5. 套用 SecretRef（`secrets apply` plan）

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
        "provider": "aliyun_secrets_manager",
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

### 6. 套用後的 `openclaw.json`（apiKey 欄位）

```json
{
  "models": {
    "providers": {
      "ollama-cloud": {
        "baseUrl": "https://ollama.com/v1",
        "apiKey": {
          "source": "exec",
          "provider": "aliyun_secrets_manager",
          "id": "ollama-cloud-apikey"
        },
        "api": "openai-completions"
      }
    }
  }
}
```

### 7. 驗證

```bash
openclaw secrets audit  # plaintext=0 即成功
```

### RAM 權限需求

使用阿里雲 RAM（資源訪問管理）授權時，需要以下權限：

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kms:GetSecretValue",
        "kms:CreateSecret",
        "kms:PutSecretValue",
        "kms:DescribeSecret",
        "kms:ListSecrets"
      ],
      "Resource": [
        "acs:kms:cn-hangzhou:*:secret/openclaw/*"
      ]
    }
  ]
}
```

建立自定義策略並附加至 RAM 用戶或角色：

```bash
# 建立自定義策略
aliyun ram CreatePolicy \
  --PolicyName OpenClawSecretsAccess \
  --PolicyDocument '{
    "Version": "1",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["kms:GetSecretValue", "kms:CreateSecret", "kms:PutSecretValue", "kms:DescribeSecret"],
      "Resource": ["acs:kms:cn-hangzhou:*:secret/openclaw/*"]
    }]
  }'

# 附加策略至 RAM 用戶
aliyun ram AttachPolicyToUser \
  --PolicyType Custom \
  --PolicyName OpenClawSecretsAccess \
  --UserName your-username
```

> 建議使用 RAM 角色（Role）搭配 STS 臨時憑證，避免長期憑證洩漏風險。


## Cloudflare Workers Secrets 介接注意事項

Cloudflare Workers 提供內建的 [Secrets](https://developers.cloudflare.com/workers/configuration/secrets/) 機制（透過 `wrangler secret put` 設定），資料加密存放，僅於 Worker runtime 內以環境變數形式可讀。這是 Cloudflare 官方推薦的秘密管理方式。

### 挑戰

- **Secrets 僅限 runtime 讀取**：Cloudflare Secrets 設計上只能在 Worker 執行時存取，本地 CLI 環境無法直接透過 `wrangler` 讀取 secret 明文值，因此難以直接作為 `exec` provider 的資料來源。
- **KV 並非秘密管理工具**：雖然技術上可透過 KV 存放並以 `wrangler kv:key get` 讀取，但 KV 資料未加密存放，任何有讀取權限者皆可見明文，不建議用於存放敏感資訊。
- **API 限制**：Cloudflare API 的 secrets endpoint 不回傳明文值，僅能列出 secret 名稱。

### 建議

若需在本地 openclaw 啟動時注入 Cloudflare 相關的 API key，建議使用 `env` source 或系統 keychain 等本地秘密管理方案，而非繞道 Cloudflare 遠端服務。

---

*參考：[v2026.2.26 Release Notes](https://github.com/openclaw/openclaw/releases/tag/v2026.2.26)*
