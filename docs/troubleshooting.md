# Troubleshooting（常見故障排除）

> 這份文件假設你「已經跑起來一次」，但開始遇到：不回覆、收不到訊息、browser 接不上、cron 不跑、SSO 過期…

---

## 0) 先做三件事（80% 的問題在這裡）

1) 看 Gateway 是否活著

```bash
openclaw gateway status
```

2) 如果不是 running：重啟

```bash
openclaw gateway restart
```

3) 看最近 log（如果你有集中 logging）

- 先找「有沒有收到 inbound event」
- 再找「tool call 有沒有被 policy 拒絕」

---

## 1) Telegram/Channel 收不到訊息

症狀：你對 bot 說話，但 OpenClaw 沒任何反應。

檢查順序：

- bot token 是否正確（onboard 時貼的那個）
- Gateway 是否 running
- 有無被平台封鎖/限流（尤其是新 bot）

建議動作：

- 先重啟 gateway：`openclaw gateway restart`
- 若依然不行，重新 onboard channel（最小變動：只改 channel，不動模型）

---

## 2) 能收到訊息但不回覆

常見原因：

- 模型 provider 掛了 / key 無效 / 額度用完
- tool call 卡住（例如 browser relay 沒 attach tab）
- 被安全 policy 擋掉

快速診斷：

- 先用一個最簡單的 prompt 測：例如「回覆 1」
- 若仍不回，多半是 provider/權限。

---

## 3) Browser tool / Browser Relay 接不上

常見錯誤：

- 「Chrome extension relay is running, but no tab is connected」

處理：

1. 在 Chrome 打開你要自動化的頁面
2. 點 OpenClaw Browser Relay 擴充套件圖示，把該 tab attach（badge ON）
3. 再回到 OpenClaw 重試 browser snapshot/act

---

## 4) Cron 沒觸發 / 沒發提醒

檢查：

- cron scheduler 是否 running（gateway 要活著）
- job 是否 enabled
- delivery mode 是否正確（announce/webhook/none）

建議：

- 用 `cron list` 看 job 是否存在
- 手動 `cron run` 觸發一次，排除排程問題

---

## 5) AWS SSO / Bedrock Token expired（SSO refresh failed）

常見現象：

- `aws sts get-caller-identity --profile bedrock-only` 失敗
- 或呼叫 Bedrock 時失敗，並看到類似錯誤：
  - `Token has expired and refresh failed`
  - `Error when retrieving token from sso`

### 重要觀念

- `~/.aws/sso/cache/*.json` 裡的 **OIDC access token** `expiresAt` 常見約 **~1 小時**，屬正常。
- 真正需要你介入的是：**access token 過期後，refresh token 無法自動刷新**（也就是 refresh failed）。

### 修復（手動 re-auth）

```bash
aws sso login --profile bedrock-only
```

（headless 環境可用 device code）

```bash
aws sso login --profile bedrock-only --use-device-code --no-browser
```

### 預防（建議：probe-first cron）

與其用 TTL 低就通知（會很吵），建議改成「先 probe，再決定要不要 re-auth」：

- cron 每 10 分鐘跑一次
- 先跑：
  - `aws sts get-caller-identity --profile bedrock-only`
- 只有在 probe 失敗且錯誤屬 token/refresh 類型時，才觸發 `aws sso login` 並發通知

範例 crontab：

```cron
*/10 * * * * /path/to/sso-refresh.sh >> /tmp/sso-refresh.log 2>&1
```

> Tips：cron 的 PATH 跟互動式 shell 不同，script 內若要呼叫 `openclaw` 發 Telegram 訊息，建議用 openclaw 絕對路徑或在 script 開頭設定 PATH。
---

## 6) Auto-merge 沒動（PR 已 approved 但沒合）

常見原因：

- required checks 還沒綠
- GitHub 的 mergeability 狀態短暫飄忽（workflow 觸發當下不一致）

建議：

- 先看 PR checks 是否全綠
- 看 auto-merge workflow run log 末段原因
- 若卡住且你很確定可合：用 `gh pr merge <num> --squash --delete-branch` 手動合（作為保險絲）

---

## 7) 工具被拒絕（policy 阻擋）

症狀：agent 想用 `exec`/`message`/`nodes` 但被拒。

處理：

- 回到你的 tooling 安全規範：`docs/core/tooling-safety.md`
- 確認是否需要 explicit user confirmation
- 把工作拆成：先乾跑（plan / preview）→ 再確認 → 再執行

---

## 8) 要回報 bug

請提供：

- 問題發生時間
- 你做了什麼（最小可重現步驟）
- 相關 log（去除 token/個資）
- 你期望的行為 vs 實際結果
