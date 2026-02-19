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

## 5) AWS SSO / Bedrock Token expired

症狀：呼叫 Bedrock 的模型時失敗，提示 token expired。

修復：

```bash
aws sso login
```

（若你有 profile）

```bash
aws sso login --profile <name>
```

預防：

- 用 cron 每小時跑一次 refresh 腳本（如果你有，例如 `sso-refresh.sh`）

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
