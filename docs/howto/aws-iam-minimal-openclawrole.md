# OpenClaw AWS IAM 最小權限配置（OpenClawRole）

本文說明我們在 OpenClaw 中使用 AWS 的情境，以及對應的最小 IAM 權限配置。

## 我們使用 AWS 的情境

| 情境 | 用途 | 必要 |
|------|------|------|
| AWS Secrets Manager | 作為 external secrets provider，openclaw 啟動時讀取 API key | ✅ 必要 |
| AWS Cost Explorer | 查詢帳單與每日費用 | 選用 |
| Amazon Bedrock AgentCore Browser | 瀏覽器自動化工具 | 選用 |
| Amazon Bedrock model inference | **不使用** — 模型透過其他 provider 存取 | ❌ 不需要 |

> 詳細 external secrets 設定請參考 [external_secrets.md](../external_secrets.md)。

---

## 角色：OpenClawRole

透過 AWS IAM Identity Center（SSO）permission set 管理。

---

## AWS 託管策略（Managed Policies）

| Policy | 用途 | 必要 |
|--------|------|------|
| `AWSBillingReadOnlyAccess` | Cost Explorer 帳單查詢 | 選用 |
| `CloudWatchReadOnlyAccess` | CloudWatch 監控唯讀 | 選用 |

---

## 內嵌策略（Inline Policy）

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:<region>:<account-id>:secret:openclaw/*"
    },
    {
      "Sid": "AgentCoreBrowserMinimal",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:StartBrowserSession",
        "bedrock-agentcore:ConnectBrowserAutomationStream",
        "bedrock-agentcore:StopBrowserSession",
        "bedrock-agentcore:ConnectBrowserLiveViewStream",
        "bedrock-agentcore:GetBrowserProfile",
        "bedrock-agentcore:SaveBrowserSessionProfile"
      ],
      "Resource": "*"
    }
  ]
}
```

> 將 `<region>` 與 `<account-id>` 替換為實際值。

**注意：不需要 `bedrock:InvokeModel` 或 `bedrock:InvokeModelWithResponseStream`** — 我們不透過 openclaw 直接呼叫 Bedrock model inference。

---

## 各 Statement 說明

### SecretsManagerRead
openclaw external secrets provider 在 gateway 啟動時呼叫，用於解析 `openclaw.json` 中的 SecretRef。Resource 限定 `openclaw/*` 前綴。

### AgentCoreBrowserMinimal
供 openclaw 的 browser 工具使用。若不需要特定功能可移除：
- 不需要 Live View → 移除 `ConnectBrowserLiveViewStream`
- 不需要跨 session 保留 cookies/localStorage → 移除 `GetBrowserProfile`、`SaveBrowserSessionProfile`

---

## 給 Agent 的 Prompt

```text
請根據這份文件，用 AWS CLI 產生「OpenClawRole」的建立操作指南，內容需包含：
1) 建立 permission set（AWS IAM Identity Center）
2) 附加 inline policy（JSON 如文件所示）
3) 選用：附加 AWSBillingReadOnlyAccess、CloudWatchReadOnlyAccess
4) 將 permission set 指派給對應的 SSO user 並 provision
5) 驗證步驟：測試 secretsmanager get-secret-value 與 agentcore start/stop session

注意：在我確認之前，不要直接對 AWS 執行任何寫入操作；先輸出所有指令讓我 review。
文件：https://github.com/thepagent/claw-info/blob/main/docs/howto/aws-iam-minimal-openclawrole.md
```

---

## 參考

- [OpenClaw External Secrets 文件](../external_secrets.md)
- [Amazon Bedrock AgentCore 權限清單](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonbedrockagentcore.html)
- [AWS Secrets Manager 權限清單](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awssecretsmanager.html)
