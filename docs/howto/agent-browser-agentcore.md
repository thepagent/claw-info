# How-to：Build agent-browser（PR #397）並連線 AWS Bedrock AgentCore Browser

## 背景：為何要把 agent-browser × AgentCore Browser 串起來？

在 OpenClaw 的使用情境裡，**讓 Agent 能穩定操作瀏覽器**（打開網站、登入、點擊、輸入、擷取資料、產生摘要/報告）一直是非常核心、且高頻的需求。

這份文件展示如何結合兩個重要技術，讓「可被驗證、可被封裝成 Skill、可被 Agent 重複使用」的瀏覽器能力落地：

### 1) agent-browser 是什麼？為什麼重要？

`agent-browser` 是一個面向 AI/Agent 的瀏覽器自動化 CLI：

- 它提供一致的命令介面（`open/click/type/snapshot/eval/...`），適合被 Agent 程式化調用。
- 它可以用「refs/snapshot」這種對 AI 友善的方式探索與操作頁面。
- 它把複雜的 Playwright/瀏覽器控制封裝成短命令，降低整合成本。

### 2) Amazon Bedrock AgentCore Browser 是什麼？為什麼重要？

Amazon Bedrock AgentCore Browser 提供「雲端可控的遠端瀏覽器 session」：

- 透過 AWS 的 SigV4 身分驗證與權限控管，能在企業環境更容易治理。
- 支援 browser profile persistence（cookies/localStorage），讓登入狀態可跨 session 重用。
- 提供 Live View（Console），方便人類在必要時介入完成登入/驗證等步驟。

### 3) 串在一起後，你會得到什麼？

#### Architecture / Data Flow（元件串接圖）

```text
User / Agent
   |
   | (commands: open/click/type/snapshot/eval/close)
   v
agent-browser CLI (provider: agentcore)
   |
   | 1) REST (SigV4): StartBrowserSession
   |    - profileIdentifier=<AGENTCORE_PROFILE_ID>
   v
Amazon Bedrock AgentCore Browser
   |\
   | \ 2a) WebSocket (SigV4 headers): Automation Stream (CDP)
   |  \
   |   \ 2b) Live View Stream (Console)
   |
   | 3) (optional) SaveBrowserSessionProfile
   v
Profile persistence (cookies/localStorage)
```

本文件會帶你走完一條建議的落地路徑：

1) 先用 **AWS CLI** 驗證 AgentCore Browser 的 session/profile 機制可用
2) 再用 **agent-browser** 驗證 CLI 操作可用（進入 `https://x.com/home`）
3) 最後把流程封裝成 **Skill**，並在新的 agent session 裡驗證可重用

```
┌──────────────────────────────────────────────────────────────────────┐
│ (1) AWS CLI：驗證 AgentCore Browser / profile persistence            │
│     start-browser-session → Live View 登入 → save-browser-session... │
└───────────────┬──────────────────────────────────────────────────────┘
                │
                v
┌──────────────────────────────────────────────────────────────────────┐
│ (2) agent-browser：驗證 CLI 能穩定進入 https://x.com/home            │
│     agent-browser -p agentcore open ... --timeout 30000              │
└───────────────┬──────────────────────────────────────────────────────┘
                │
                v
┌──────────────────────────────────────────────────────────────────────┐
│ (3) Skill：讓 Agent 產生並封裝自己的 SKILL.md                        │
│     prerequisites / commands / guardrails / troubleshooting          │
└───────────────┬──────────────────────────────────────────────────────┘
                │
                v
┌──────────────────────────────────────────────────────────────────────┐
│ (4) New Agent Session：只依賴 Skill 重跑，確認可重用                  │
└──────────────────────────────────────────────────────────────────────┘
```

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

範例（變數用 `<>` 表示，且使用**全大寫**；請依你的 `--profile` / region 調整）：

```bash
aws bedrock-agentcore start-browser-session \
  --browser-identifier aws.browser.v1 \
  --profile-configuration '{"profileIdentifier":"<AGENTCORE_PROFILE_ID>"}' \
  --session-timeout-seconds 3600 \
  --region <AGENTCORE_REGION> \
  --profile <AWS_PROFILE_NAME>
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

## 5. 第一次使用：用 AWS CLI 建立並驗證可持久化的 Profile（推薦）

這段流程的目標是：在你開始用 `agent-browser` 前，先用 AWS CLI + Console 確認 **AgentCore Browser 的 session / Live View / Profile persistence** 都正常。

### 5.1 Step 1：用 AWS CLI 開一個 session（綁定 `<AGENTCORE_PROFILE_ID>`）

> 注意：Bedrock AgentCore 的 Data Plane CLI **沒有** `create-browser-profile`；`<AGENTCORE_PROFILE_ID>` 是你自行決定的 identifier。

```bash
aws bedrock-agentcore start-browser-session \
  --browser-identifier aws.browser.v1 \
  --profile-configuration '{"profileIdentifier":"<AGENTCORE_PROFILE_ID>"}' \
  --session-timeout-seconds 3600 \
  --region <AGENTCORE_REGION> \
  --profile <AWS_PROFILE_NAME> \
  --output json
```

輸出重點欄位：

- `sessionId`
- `browserIdentifier`（預期是 `aws.browser.v1`）

### 5.2 Step 2：印出 Live View URL（點進去手動登入）

從 `start-browser-session` 輸出中取出 `<SESSION_ID>` 後，Live View（Console）URL 格式如下：

```
https://<AGENTCORE_REGION>.console.aws.amazon.com/bedrock-agentcore/browser/aws.browser.v1/session/<SESSION_ID>#
```

打開後：

1. 在 Live View 內操作瀏覽器登入 `https://x.com`
2. 登入完成後，於 Console 介面點選 **Save to profile**（把 cookies/localStorage 存回 `<AGENTCORE_PROFILE_ID>`）

### 5.3 Step 3（可用 CLI 取代 Console 按鈕）：用 AWS CLI 儲存 session state 到 profile

如果你希望全程用 CLI，也可以直接呼叫：

```bash
aws bedrock-agentcore save-browser-session-profile \
  --profile-identifier <AGENTCORE_PROFILE_ID> \
  --browser-identifier aws.browser.v1 \
  --session-id <SESSION_ID> \
  --region <AGENTCORE_REGION> \
  --profile <AWS_PROFILE_NAME>
```

> 注意：`save-browser-session-profile` 需要 session 仍在 active 狀態。

### 5.4 Step 4：重新開一個新 session 驗證持久化

再次執行 Step 1（同一個 `<AGENTCORE_PROFILE_ID>`），然後在 Live View 直接開 `https://x.com/home`，應該能看到已登入的 Home timeline，不再跳 login flow。

---

## 6. 用 agent-browser 連線（推薦）

### 6.1 最小命令

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

### 6.2 啟用 Profile Persistence（跨 session 保留登入）

```bash
export AGENTCORE_REGION=us-east-1
export AGENTCORE_PROFILE_ID=my-profile-id

agent-browser -p agentcore open https://x.com/home --timeout 30000 2>&1
```

> `AGENTCORE_PROFILE_ID` 會讓 AgentCore 用指定 profile 保存 cookies / localStorage。

---

## 7. 常用環境變數（AgentCore）

---

## 8. 把流程變成 Skill（讓 Agent 自己可重用）

當你確認 **AWS CLI 流程可用**、且 **手動 agent-browser 命令可用** 後，下一步才建議把它封裝成一個 Skill，讓 Agent 能在未來的工作中穩定重複使用。

### 8.1 流程順序（建議）

```
(1) AWS CLI：手動驗證 AgentCore 可用
    - start-browser-session + Live View + save-browser-session-profile
        |
        v
(2) agent-browser：手動驗證可用
    - open https://x.com/home --timeout 30000
        |
        v
(3) 讓 Agent 產生「給自己用的 Skill」
    - 寫 skills/<skill-name>/SKILL.md
    - 把必要的 env vars / commands / guardrails 寫清楚
        |
        v
(4) 開一個新的 agent session
    - 在新 session 只依賴該 Skill
    - 呼叫 skill 的 Quick Start / recipe
    - 驗證能正確進入 https://x.com/home
```

### 8.2 SKILL.md 建議內容（最小集合）

可參考：`docs/core/skills-system.md`（Skill 打包與 SKILL.md 撰寫規範）。

你的 Skill（例如 `agentcore-x` / `twitter`）至少要包含：

- **What it does**：用 AgentCore + `agent-browser` 開啟 X（`x.com/home`），並確保使用持久化 profile。
- **Prerequisites**：
  - `agent-browser` 已安裝且版本支援 `-p agentcore`
  - AWS credentials / SSO 已登入
  - IAM 權限（本文件 1.3 節）
  - `<AGENTCORE_PROFILE_ID>` 已按第 5 節流程完成保存
- **Quick Start（可直接複製）**：
  - 建議固定帶 `--timeout 30000 2>&1`
  - 明確要求：先 `agent-browser close` 再開，避免殘留 session
- **Safety / guardrails**：
  - 不要在公開管道貼 `sessionId` / 任何含帳號識別的輸出
  - 如果要做發文/按讚等動作，需先詢問或限定在 dry-run
- **Troubleshooting**：
  - 403 → IAM 權限
  - 被導到 login flow → profile 未保存 / session 失效 / timeout 太短

### 8.3 新 session 驗證（最重要）

完成 Skill 後，請務必開一個全新 agent session（乾淨上下文）做驗證：

- 讓 Agent 僅依 Skill 的 Quick Start 執行
- 觀察是否成功進入 `https://x.com/home`
- 若失敗，再回頭補齊 Skill 的 prerequisites / commands / timeout / close 流程

| 變數 | 說明 | 預設 |
|---|---|---|
| `AGENTCORE_REGION` | AgentCore region（也會 fallback `AWS_REGION` / `AWS_DEFAULT_REGION`） | `us-east-1` |
| `AGENTCORE_BROWSER_ID` | Browser identifier | `aws.browser.v1` |
| `AGENTCORE_SESSION_TIMEOUT` | session timeout（秒） | `3600` |
| `AGENTCORE_PROFILE_ID` | profile id（持久化 cookies/localStorage） | （無） |

---

## 9. Troubleshooting

### 9.1 `Failed to start AgentCore browser session` / 403 / Forbidden

- 通常是 **AWS credentials 不正確** 或 **沒有 Bedrock AgentCore 權限**。
- 請先用 AWS CLI 確認你目前身份：

```bash
aws sts get-caller-identity
```

> 注意：此命令輸出會包含 AWS Account / ARN 等識別資訊；若要貼到公開 issue/PR，請先打碼或移除敏感欄位。

### 9.2 CDP 連線失敗（`Failed to connect to AgentCore browser session via CDP`）

- 常見原因：region 不對、網路限制、或 session 啟動後立刻失效。
- 先確認你設定的 `AGENTCORE_REGION` 正確。
- 看 `Live View` 連結能否打開（AWS Console）。

### 9.3 忘了 close，session 沒有 stop

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
