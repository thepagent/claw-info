# Linux（systemd）上的 OpenClaw Gateway：重啟、Port 衝突與 Model 設定踩坑

## TL;DR

- 在 Ubuntu/Debian 這類 systemd 環境，如果用 systemd 管理 `openclaw-gateway`，**重啟後卡住/無限重試**，常見原因是：舊的子行程沒被殺掉，繼續占用 **TCP 18789**。
- systemd 的預設 `KillMode=process` 可能只會結束主行程；建議改成 **`KillMode=control-group`**，確保整個 cgroup 內的行程都停止。
- 另一個常見坑：即使你設定了 `agents.defaults.model.primary`，如果該模型 **不在 `agents.defaults.models`** 裡，OpenClaw 可能會**默默略過**並改用其他 fallback。

---

## 使用情境（Use cases）

- 你在 Linux 上用 systemd（user service 或 system service）把 OpenClaw Gateway 當 daemon 跑。
- 你遇到以下狀況之一：
  - `openclaw gateway restart` 後 gateway 起不來
  - `systemctl --user restart openclaw-gateway` 後一直 retry
  - log 顯示 bind/listen 失敗、port already in use
  - 你明明設定了 primary model，但實際跑起來卻用另一個 model

---

## 問題 1：Gateway restart 造成 port 18789 衝突

### 現象（Symptoms）

- systemd 反覆重啟服務（Restart loop）
- 你會看到類似「port 已被占用」的錯誤（示意）：

```text
listen tcp :18789: bind: address already in use
```

### 根因（Root cause）

在部分 systemd 配置下，預設：

- `KillMode=process`：只 kill systemd 追蹤的「主行程（main process）」
- gateway 內部若有子行程（child processes）仍存活，可能持續占用 18789
- systemd 再次啟動時就會撞到 port 衝突，進而無限 retry

> 這個問題是 **Linux/systemd 特有**；macOS 的 launchd 不一定會遇到同樣行為。

### 建議修正（推薦做法）

如果你使用的是 **systemd user service**（常見路徑：`~/.config/systemd/user/openclaw-gateway.service`），可以加入以下設定：

```ini
# 目的：重啟/停止時，確保整個 service 的子行程都被停止，避免 port 18789 被殘留行程占用。

#（可選）啟動前先清理占用 port 18789 的行程。
# 注意：這是 workaround；更根本的是 KillMode=control-group。
ExecStartPre=/bin/sh -c 'kill $(lsof -ti:18789) 2>/dev/null; sleep 1; true'

# 關鍵：停止時 kill 整個 cgroup
KillMode=control-group

# 讓停止流程有合理的時間完成
TimeoutStopSec=15
```

#### 套用設定

```bash
# 重新載入 user units
systemctl --user daemon-reload

# 重啟服務
systemctl --user restart openclaw-gateway

# 觀察狀態
systemctl --user status openclaw-gateway --no-pager

# 觀察 log
journalctl --user -u openclaw-gateway -n 200 --no-pager
```

### Troubleshooting

- **症狀**：重啟後仍然 `address already in use`
  - **可能原因**：仍有殘留行程占用 18789
  - **處理方式**：

```bash
# 找出誰占用 18789
lsof -nP -iTCP:18789 -sTCP:LISTEN

# 或
ss -ltnp | grep 18789 || true
```

- **症狀**：`lsof` 不存在
  - **可能原因**：系統未安裝 `lsof`
  - **處理方式**（Debian/Ubuntu）：

```bash
sudo apt-get update && sudo apt-get install -y lsof
```

---

## 問題 2：primary model 可能被「默默跳過」

### 現象（Symptoms）

- 你在 config 裡設定：
  - `agents.defaults.model.primary = "openai-codex/gpt-5.2"`
- 但實際執行時，OpenClaw 卻選了另一個 model（例如 fallback），且不一定有明顯錯誤。

### 根因（Root cause）

OpenClaw 會從可用的 model 清單中做選擇。
如果你只設定了 `agents.defaults.model.primary`，但沒有把該 model 同步列在 `agents.defaults.models`，就可能出現：

- primary model 不在 candidates → 直接略過 → 用下一個可用 model

### 建議修正（推薦做法）

確保 **primary + 所有 fallback** 都有列在 `agents.defaults.models`：

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai-codex/gpt-5.2"
      },
      "models": {
        "openai-codex/gpt-5.2": {
          "alias": "GPT-5.2 (Codex)"
        }
      }
    }
  }
}
```

### Troubleshooting

- **症狀**：你不確定現在到底用哪個 model
  - **處理方式**：
    - 先檢查 runtime log（gateway / agent log）是否會列出 model selection
    - 再檢查你的 config 是否同時包含 `model.primary` 與 `models.<model-id>`

---

## See also

- `docs/core/gateway-lifecycle.md` — gateway 生命週期與重啟/排障概念
- Issue: https://github.com/thepagent/claw-info/issues/58
