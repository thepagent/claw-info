---
last_validated: 2026-04-02
---

# Amazon Bedrock Authentication for OpenClaw

Two ways to authenticate with Amazon Bedrock.

## OPTION 1: AWS Identity Center (SSO) — Recommended

Use IAM role with minimal permissions via IAM Identity Center. This allows you to completely remove the api key from the main JSON.

### ~/.aws/config

```yaml
[profile bedrock-only]
sso_session = sso
sso_account_id = YOUR_AWS_ACCOUNT_ID
sso_role_name = BedrockInvokeOnly
region = us-east-1
```

### Permission for BedrockInvokeOnly

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvokeOnly",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    }
  ]
}
```

### AWS SSO Login

```sh
aws --profile bedrock-only sso login --use-device-code --no-browser
```

### ~/.openclaw/.env

```sh
AWS_PROFILE=bedrock-only
```

### openclaw.json (models section)

No `apiKey` needed. The AWS SDK auto-signs requests with SigV4.

```json
{
  "mode": "merge",
  "providers": {
    "amazon-bedrock": {
      "baseUrl": "https://bedrock-runtime.us-east-1.amazonaws.com",
      "api": "bedrock-converse-stream",
      "models": [
        {
          "id": "openai.gpt-oss-120b-1:0",
          "name": "GPT OSS 120B",
          "reasoning": true,
          "input": ["text"],
          "cost": { "input": 0.15, "output": 0.62, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 262144,
          "maxTokens": 8192
        }
      ]
    }
  }
}
```

## OPTION 2: Amazon Bedrock API Key

Specify `baseUrl`, `apiKey`, `auth` and `authHeader` as below:

### Generate API Key

```sh
# generate Bedrock API KEY at https://console.aws.amazon.com/bedrock/home#/api-keys
export AWS_BEARER_TOKEN_BEDROCK=xxxxxxxxx
```

Or add to `~/.openclaw/.env`:

```sh
AWS_BEARER_TOKEN_BEDROCK=xxxxxxxxx
```

### openclaw.json (models section)

```json
{
  "mode": "merge",
  "providers": {
    "bedrock": {
      "baseUrl": "https://bedrock-runtime.us-east-1.amazonaws.com",
      "apiKey": "${AWS_BEARER_TOKEN_BEDROCK}",
      "api": "bedrock-converse-stream",
      "auth": "api-key",
      "authHeader": true,
      "models": [
        {
          "id": "openai.gpt-oss-120b-1:0",
          "name": "GPT OSS",
          "reasoning": true,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 262144,
          "maxTokens": 8192
        }
      ]
    }
  }
}
```

### agents.defaults section

```json
{
  "model": {
    "primary": "bedrock/openai.gpt-oss-120b-1:0"
  },
  "models": {
    "bedrock/openai.gpt-oss-120b-1:0": {
      "alias": "gpt-oss-120b"
    }
  }
}
```

### Verify

```sh
openclaw gateway run --verbose  # make sure no errors
```

When you type `/new` in Telegram, you should see:

```
✅ New session started · model: bedrock/openai.gpt-oss-120b-1:0
```

## Comparison

```
┌─────────────────────────────────┬───────────────────────────────────────────┐
│         API Key 方式            │         AWS Identity Center (SSO)         │
├─────────────────────────────────┼───────────────────────────────────────────┤
│                                 │                                           │
│  ✅ 優點                        │  ✅ 優點                                   │
│  ─────                          │  ─────                                    │
│  • 設定簡單，一行搞定            │  • 無明文密鑰存檔                          │
│  • 永不過期（除非手動撤銷）       │  • 最小權限原則（僅 InvokeModel）          │
│  • 無需瀏覽器登入                │  • 自動過期（最長 12 小時）                │
│  • 離線環境可用                  │  • 可集中管理、稽核                        │
│                                 │  • 與其他 AWS 工具共用認證                 │
│                                 │  • 支援 MFA / 條件式存取                   │
│                                 │  • 可隨時撤銷，立即生效                    │
│                                 │                                           │
├─────────────────────────────────┼───────────────────────────────────────────┤
│                                 │                                           │
│  ❌ 缺點                        │  ❌ 缺點                                   │
│  ─────                          │  ─────                                    │
│  • 明文存檔（.env 或 plist）     │  • 需定期重新登入（每 12 小時）            │
│  • 洩漏風險高                    │  • 首次設定較複雜                          │
│  • 權限通常過大                  │  • 需要瀏覽器完成 OAuth                    │
│  • 難以稽核使用情況              │  • 背景服務需處理 token 刷新               │
│  • 撤銷需重新產生並更新所有地方   │  • 離線環境無法使用                        │
│                                 │                                           │
├─────────────────────────────────┼───────────────────────────────────────────┤
│                                 │                                           │
│  🎯 適用場景                    │  🎯 適用場景                               │
│  ─────────                      │  ─────────                                │
│  • 快速測試 / PoC               │  • 生產環境                                │
│  • 離線 / 隔離環境               │  • 多人共用帳號                            │
│  • CI/CD pipeline               │  • 需要稽核追蹤                            │
│  • 短期專案                      │  • 安全性要求高的場景                      │
│                                 │  • 長期使用的本機開發環境                  │
│                                 │                                           │
├─────────────────────────────────┼───────────────────────────────────────────┤
│                                 │                                           │
│  🔐 安全性評分                  │  🔐 安全性評分                             │
│  ─────────                      │  ─────────                                │
│                                 │                                           │
│      ██░░░░░░░░  2/10           │      █████████░  9/10                     │
│                                 │                                           │
└─────────────────────────────────┴───────────────────────────────────────────┘
```

> 💡 SSO is the recommended approach: no plaintext tokens stored, auto-expires in 12 hours, and uses least-privilege permissions. The only trade-off is running `aws sso login --profile bedrock-only` once per day.

## Reference

- [Original Gist](https://gist.github.com/pahud/8965bfeec441225009abfa96f4751f48)
