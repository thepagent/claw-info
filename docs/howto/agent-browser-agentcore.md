# How-to：Build agent-browser（PR #397）並連線 AWS Bedrock AgentCore Browser

> 目的：讓你從原始碼 build 出包含 **`-p agentcore`** provider 的 `agent-browser`（對應 PR #397），並在本機用最短步驟連上 **AWS Bedrock AgentCore Browser**。
>
> 對應實作來源：vercel-labs/agent-browser PR #397
> - https://github.com/vercel-labs/agent-browser/pull/397

---

## TL;DR（最短成功路徑）

```bash
# 1) build 這個 PR 的版本（npm）
git clone https://github.com/vercel-labs/agent-browser.git
cd agent-browser

git fetch origin pull/397/head:pr-397
git checkout pr-397

npm install
npm run build
npm i -g .

# 2) 下載 Chromium（第一次需要）
agent-browser install

# 3) 連 AWS Bedrock AgentCore Browser（需要 AWS credentials）
export AGENTCORE_REGION=us-east-1
agent-browser -p agentcore open https://x.com/home --timeout 30000 2>&1

# 4) 收尾
agent-browser close
```

---

## 0. 你會得到什麼（這個 PR 做了什麼）

PR #397 主要新增：

1. **AgentCore provider**：`agent-browser -p agentcore ...`
   - 會用 **SigV4** 呼叫 AgentCore REST API 建立 session，然後用帶簽章的 headers 連到 CDP WebSocket。
   - 支援 `AGENTCORE_PROFILE_ID` 做 **profile persistence**（cookies / localStorage 可跨 session 保留）。
2. **CDP 自訂 headers**：`agent-browser connect ... --headers '{...}'`
   - 讓需要驗證 headers 的 CDP 服務（例如 AgentCore）可用低階方式連線。

---

## 1. Prerequisites（前置條件）

### 1.1 系統工具

- Node.js（建議用 LTS；至少需能跑 `npm install` / `npm run build`）
- npm
- （可選）Rust toolchain（如果你要 build native Rust CLI）：https://rustup.rs

### 1.2 AWS / Bedrock AgentCore 端

- 你需要有權限使用 **AWS Bedrock AgentCore Browser**。
- 你需要可用的 AWS credentials（任一標準方式均可）：
  - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`
  - `~/.aws/credentials` + `AWS_PROFILE`
  - EC2/ECS/IAM Role 等

本指南預設 region 使用 `us-east-1`（可改）。

### 1.4（可選但推薦）用 AWS CLI 先做一次 API 驗證

在使用 `agent-browser` 之前，你可以先用 AWS CLI 直接打 AgentCore API，確認：

- AWS credentials / region 正確
- `bedrock-agentcore:StartBrowserSession` 權限沒問題
- 指定的 profile identifier 能被接受

範例（請依你的 `--profile` 調整，下面示範用 `botreadonly`）：

```bash
aws bedrock-agentcore start-browser-session \
  --browser-identifier aws.browser.v1 \
  --profile-configuration '{"profileIdentifier":"pahudnet_gmail-attEctm8Qe"}' \
  --session-timeout-seconds 3600 \
  --region us-east-1 \
  --profile botreadonly
```

> 注意：請勿把輸出中的 `sessionId` 等資訊直接貼到公開 issue/PR。

### 1.3 IAM 權限（執行 agent-browser 的身份都需要）

不論你是 **真人在終端機操作**、或是 **由 Agent/自動化流程呼叫 `agent-browser`**，只要使用的是同一組 AWS credentials / role / permission set，該「執行身份」就必須具備本節列出的 `bedrock-agentcore:*` 權限，否則會在 start session / connect stream / stop session 任一步驟遇到 `403 Forbidden`。

`agent-browser -p agentcore` 在背後會做三件事：

1. **Start session**（REST API）
2. **Connect automation stream**（WebSocket / CDP）
3. **Stop session**（REST API）

因此最小權限通常需要：

- `bedrock-agentcore:StartBrowserSession`
- `bedrock-agentcore:ConnectBrowserAutomationStream`
- `bedrock-agentcore:StopBrowserSession`

若你還要在 AWS Console 看 **Live View**：

- `bedrock-agentcore:ConnectBrowserLiveViewStream`

若你要用 `AGENTCORE_PROFILE_ID` 做 **profile persistence**（cookies/localStorage 跨 session 保留）：

- `bedrock-agentcore:GetBrowserProfile`
- `bedrock-agentcore:SaveBrowserSessionProfile`

#### 建議做法：建立一個 customer managed policy（先跑通，再收斂）

先用 `Resource: "*"` 跑通；確認可用後再依你們的 browser / browser-profile ARN 收斂範圍。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AgentCoreBrowserMinimal",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:StartBrowserSession",
        "bedrock-agentcore:ConnectBrowserAutomationStream",
        "bedrock-agentcore:StopBrowserSession"
      ],
      "Resource": "*"
    }
  ]
}
```

> 權限清單（官方）：https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonbedrockagentcore.html

#### 如何讓使用者/Agent 自行確認

- 直接跑一次（建議加 timeout，避免網站載入/跳轉較慢時誤判）：
  - `agent-browser -p agentcore open https://x.com/home --timeout 30000 2>&1`
  - 若缺權限通常會看到 `403 Forbidden` 或類似 `Failed to start AgentCore browser session`。
- 若你們組織允許，可用 **AWS Policy Simulator**（Console）針對上述 actions 測試是否 Allow。

---

## 2. 取得 PR #397 原始碼

建議使用 PR ref（最穩，不怕 branch 改名）：

```bash
git clone https://github.com/vercel-labs/agent-browser.git
cd agent-browser

git fetch origin pull/397/head:pr-397
git checkout pr-397
```

---

## 3. Build（npm 版本）

### 3.1 安裝依賴 + build TypeScript

```bash
npm install
npm run build
```

> 註：這會產出 `dist/`（Node.js fallback / daemon）。

### 3.2 安裝到全域（預設）

```bash
npm i -g .
```

驗證：

```bash
agent-browser --help
# 你應該能在 provider 列表看到 agentcore
```

### 3.3（可選）用 npm link（方便本機迭代）

如果你要改 code 然後立即測：

```bash
npm link
```

> 解除 link：`npm unlink -g agent-browser`（或依 npm 版本略有差異）。

### 3.4（可選）Build native Rust CLI

如果你想要原生 Rust binary（效能最佳），需要 Rust：

```bash
npm run build:native
```

---

## 4. 安裝 Chromium（第一次必做）

```bash
agent-browser install
```

Linux 若缺系統依賴可用：

```bash
agent-browser install --with-deps
# 或 npx playwright install-deps chromium
```

---

## 5. 用 AgentCore provider 連線（推薦）

### 5.1 最小命令

```bash
export AGENTCORE_REGION=us-east-1
agent-browser -p agentcore open https://x.com/home --timeout 30000 2>&1
```

> 註：`--timeout 30000` 可避免網站載入/跳轉較慢時，CLI 早回報造成誤判；`2>&1` 則方便把 stderr（包含 Live View）一併收集。

成功時通常會看到類似輸出（PR 內會印到 stderr）：

- `Session: <session-id>`
- `Live View: https://<region>.console.aws.amazon.com/...`

你可以再確認能控制頁面：

```bash
agent-browser eval "document.title"
agent-browser snapshot
```

結束時請記得 close（會呼叫 sessions/stop）：

```bash
agent-browser close
```

### 5.2 啟用 Profile Persistence（跨 session 保留登入）

```bash
export AGENTCORE_REGION=us-east-1
export AGENTCORE_PROFILE_ID=my-profile-id

agent-browser -p agentcore open https://x.com/home
```

> `AGENTCORE_PROFILE_ID` 會讓 AgentCore 用指定 profile 保存 cookies / localStorage。

---

## 6. 常用環境變數（AgentCore）

| 變數 | 說明 | 預設 |
|---|---|---|
| `AGENTCORE_REGION` | AgentCore region（也會 fallback `AWS_REGION` / `AWS_DEFAULT_REGION`） | `us-east-1` |
| `AGENTCORE_BROWSER_ID` | Browser identifier | `aws.browser.v1` |
| `AGENTCORE_SESSION_TIMEOUT` | session timeout（秒） | `3600` |
| `AGENTCORE_PROFILE_ID` | profile id（持久化 cookies/localStorage） | （無） |

---

## 7. Troubleshooting

### 7.1 `Failed to start AgentCore browser session` / 403 / Forbidden

- 通常是 **AWS credentials 不正確** 或 **沒有 Bedrock AgentCore 權限**。
- 請先用 AWS CLI 確認你目前身份：

```bash
aws sts get-caller-identity
```

> 注意：此命令輸出會包含 AWS Account / ARN 等識別資訊；若要貼到公開 issue/PR，請先打碼或移除敏感欄位。

### 7.2 CDP 連線失敗（`Failed to connect to AgentCore browser session via CDP`）

- 常見原因：region 不對、網路限制、或 session 啟動後立刻失效。
- 先確認你設定的 `AGENTCORE_REGION` 正確。
- 看 `Live View` 連結能否打開（AWS Console）。

### 7.3 忘了 close，session 沒有 stop

- 建議每次用完都跑 `agent-browser close`。
- 若你在程式/腳本中使用，務必做 try/finally 確保 close 被呼叫。

---

## 附錄：低階 CDP 直連（不走 provider）

此 PR 也新增 `connect --headers`，你可以自行提供 WebSocket endpoint 與 headers：

```bash
agent-browser connect "wss://..." --headers '{"Authorization":"AWS4-HMAC-SHA256...","X-Amz-Date":"..."}'
```

但大多數情況下建議用：

```bash
agent-browser -p agentcore open https://x.com/home --timeout 30000 2>&1
```
