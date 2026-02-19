# Start / Onboarding（最小可行）

> 目標：讓你在 **15–30 分鐘內**把 OpenClaw 跑起來（daemon 常駐、能收訊息、能跑工具）。
>
> 本文件偏「操作手冊」，不是完整產品文件。

---

## 0) 你需要準備什麼

- 一台會常開的機器（本機或 VPS）
- 一個模型供應商（例如 Bedrock / OpenAI / Gemini / MiniMax…依你的配置）
- 至少一個 channel（最常見：Telegram bot token）

> 建議：先只接 **一個 channel + 一個模型**。跑順再加第二個。

---

## 1) 安裝與啟動 Gateway（daemon）

> 以下以 macOS/Linux 為主；Windows 請依官方 docs。

1. 安裝 OpenClaw

```bash
npm i -g openclaw
```

2. 進入 onboarding（並安裝 daemon）

```bash
openclaw onboard --install-daemon
```

3. 驗證 daemon 是否正常

```bash
openclaw gateway status
```

常見輸出：running / stopped。

---

## 2) 連接模型（Provider）

在 onboarding 過程中依提示選擇 provider、填入 API key。

### Bedrock 使用者（常見）

- 如果遇到 **SSO token expired**：先跑

```bash
aws sso login
```

- 或使用你環境中的 refresh 腳本（若有）

> 建議把「SSO refresh」放到 cron（每小時一次），避免半夜過期。

---

## 3) 連接 Channel（以 Telegram 為例）

1. 到 @BotFather 建立 bot，取得 token。
2. 在 onboarding 選 Telegram，貼上 token。
3. 跟你的 bot 開始對話，確認能收發。

> 若你看到 bot 沒回：先看 `docs/troubleshooting.md` 的「收不到訊息」段。

---

## 4) Pairing（把手機/節點配上）

若你要使用 nodes（例如手機截圖、錄影、定位、遠端執行），在 TUI/CLI 會看到 pairing key。

流程（概念）：

- 取得 pairing key（像 `123456:ABCDEFG...`）
- 把 pairing key 貼到你配置的 channel（通常是 Telegram 的 bot 對話）
- Gateway 會把該裝置加入 paired nodes

驗證：

```bash
openclaw nodes status
```

---

## 5) 快速驗證清單（Checklist）

到這一步，下面 5 個都應該成立：

1. `openclaw gateway status` 顯示 running
2. Telegram bot 能收到你訊息
3. agent 能回覆（不一定要很聰明，先能動就好）
4. `exec` 可在 sandbox 跑簡單指令（例如 `pwd`）
5. cron 能被建立並觸發（測一個 1 分鐘後提醒）

---

## 6) 下一步建議

- 先建立 1–2 個最常用 workflows：
  - cron reminder
  - issue triage / PR review
  - 每日摘要
- 先把安全邊界設好：
  - `message` / `exec` / `nodes` 要求更高門檻

參考：
- `docs/core/tooling-safety.md`
- `docs/cron.md`
- `docs/nodes.md`
