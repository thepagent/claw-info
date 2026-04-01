---
last_validated: 2026-04-02
---

# AWS SSO Token 刷新策略

在運行 OpenClaw 機器時，AWS 憑證建議使用 AWS Identity Center（SSO）搭配 `aws sso login` 取得暫時性憑證。這些憑證數小時後到期，因此需要一套刷新策略來將停機時間降到最低。

## Token 架構

```
          (interactive device login)
Human ───────────────────────────────────────────────┐
                                                     ▼
                                             ┌─────────────────┐
                                             │  refresh token   │  (長效/可續)
                                             └───────┬─────────┘
                                                     │
                                                     │  auto refresh
                                                     ▼
┌─────────────────┐   expires ~1h   ┌──────────────────────────┐
│  access token    │───────────────▶│ new access token (rotates)│
└───────┬─────────┘                 └───────────┬──────────────┘
        │                                       │
        │ used to fetch STS creds               │
        ▼                                       ▼
┌──────────────────────────┐          ┌─────────────────────────┐
│ STS role credentials      │          │ AWS API calls (Bedrock) │
│ (AccessKey/Secret/Token)  │─────────▶│ via AWS CLI/SDK         │
│ valid up to SessionDuration│         └─────────────────────────┘
└──────────────────────────┘
```

重點說明：

- `~/.aws/sso/cache` 的 access token TTL ~1h 是**正常的**，不代表需要人工重新登入
- 只要 refresh token 仍有效，AWS CLI 會自動輪換 access token（無感續命）
- Refresh token 的到期時間**無法從 cache 檔案得知**，無法預測何時失效
- 唯一的訊號是 AWS API 呼叫失敗：`Token has expired and refresh failed`

## 策略：Probe-First

不要用固定時間觸發重新登入（會造成不必要的打擾），改用 **probe-first** 方式：

1. 定期用真實 AWS 呼叫來探測
2. 成功 → 不做任何事
3. 失敗且屬於 token/refresh 錯誤 → 觸發 device login 並通知

```
┌─────────────────┐
│  cron */10 min  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐     ┌──────────┐
│ aws sts get-caller-identity │─OK─▶│  exit 0  │
└─────────────┬───────────────┘     └──────────┘
              │ FAIL
              ▼
┌─────────────────────────┐         ┌──────────┐
│ token/refresh 類錯誤？  │──否────▶│  exit 0  │
└─────────────┬───────────┘         └──────────┘
              │ 是
              ▼
┌──────────────────────────────────┐
│ aws sso login --use-device-code  │
└─────────────┬────────────────────┘
              │
              ▼
┌──────────────────────────────────┐
│ 推送授權 URL 至 Telegram         │
└─────────────┬────────────────────┘
              │
              ▼
┌──────────────────────────────────┐
│ 人工點連結完成授權               │
└─────────────┬────────────────────┘
              │
              ▼
┌──────────────────────────────────┐
│ 取得新 token，服務恢復正常       │
└──────────────────────────────────┘
```

## 為何使用 OS cron 而非 OpenClaw cron

OpenClaw 本身也支援 cron job，但此場景應使用 **OS cron**，原因如下：

| | OS cron | OpenClaw cron |
|---|---|---|
| Gateway 掛掉時仍能執行 | ✅ | ❌ |
| 能偵測並通知 token 失效 | ✅ | ❌（gateway 可能因 token 失效而掛） |
| 能重啟 gateway | ✅ | ❌ |

Token 失效往往正是導致 gateway 不穩定的原因。若用 OpenClaw cron，gateway 一旦掛掉，probe 也跟著停，無法通知人工。OS cron 的生命週期獨立於 gateway，是唯一可靠的選擇。

## 實作（僅 PoC 示範）

> ⚠️ `aws sso login --use-device-code --no-browser` 本質上是 interactive 的 — 它會印出 URL 後持續 polling，等待人工在瀏覽器完成授權才返回。因此腳本需以背景執行方式處理，避免 cron job 卡住。

> 社群有人用 Puppeteer/headless browser 自動填表（如 [aldokkani/aws-sso-refresh](https://github.com/aldokkani/aws-sso-refresh)），可完全無人工介入，但需要將 IdP 帳密存在本機，有安全疑慮。對於生產環境，建議採用下方的 probe-first + 人工授權通知方式。

儲存為 `~/.openclaw/scripts/sso-refresh.sh`：

```bash
#!/bin/bash
export PATH="/usr/local/bin:/usr/bin:/bin"

PROFILE="bedrock-only"
OPENCLAW="$HOME/.npm-global/bin/openclaw"

# Probe first — token 有效則靜默退出
aws sts get-caller-identity --profile "$PROFILE" &>/dev/null && exit 0

# 只在 token/refresh 類錯誤時才重新登入
ERR=$(aws sts get-caller-identity --profile "$PROFILE" 2>&1)
echo "$ERR" | grep -qiE "token has expired|refresh failed|SSOTokenProviderFailure" || exit 0

# 觸發重新登入，非同步執行，從輸出抓 URL 後推送通知
TMPLOG=$(mktemp)
aws sso login --profile "$PROFILE" --use-device-code --no-browser >"$TMPLOG" 2>&1 &
SSO_PID=$!

# 等待 URL 出現（最多 15 秒）
URL=""
for i in $(seq 1 15); do
  sleep 1
  URL=$(grep -o 'https://[^ ]*user_code=[^ ]*' "$TMPLOG" | head -1)
  [ -n "$URL" ] && break
done
rm -f "$TMPLOG"

$OPENCLAW message send --channel telegram --account <your-account> --target <your-chat-id> \
  -m "⚠️ AWS SSO refresh 失敗，請點連結授權：$URL"
# SSO_PID 繼續在背景等待人工授權完成
```

加入 cron（每 10 分鐘執行一次）：

```
*/10 * * * * $HOME/.openclaw/scripts/sso-refresh.sh >> $HOME/.openclaw/logs/sso-refresh.log 2>&1
```

## 預期停機時間

最壞情況 = cron 偵測週期（10 分鐘）+ 人工完成 device login 的時間。

若 Telegram 通知即時查看，實際停機通常不超過 2 分鐘。
