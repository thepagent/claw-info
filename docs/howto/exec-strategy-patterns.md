# OpenClaw Exec 權限策略模式

## 為什麼需要這篇

自 **OpenClaw `2026.4.1`** 起，`exec` 的 approval / allowlist 行為被更一致地落實，相關 release notes 也明確提到多項 **Exec/approvals** 修正。這讓使用者能更清楚地依照實際 policy 來控制 agent 的執行能力，而不是依賴較模糊或偶然的舊行為。

換句話說，OpenClaw 讓使用者可以更明確地：

- 用 `exec-approvals.json` 管理可執行命令的 trust / allowlist
- 將 approval 與 ask policy 套用到不同風險層級的操作
- 區分 host / sandbox / node 等不同執行邊界
- 針對 chat-facing main agent、ACP、sub-agent 採取不同權限模型

這是好事，但也讓很多人第一次更明顯地意識到：

- `tools.exec.security = "full"`

**不等於**「agent 幾乎什麼都能執行」。

實際上，是否真的跑得動，還取決於：

- `exec-approvals.json` 中已存在的 allowlist / durable trust
- approval / ask policy
- host / sandbox / node 的執行位置
- 當前 session 或 agent 的有效工具策略

因此，自 `2026.4.1` 之後，更需要一份實務導向的指引，幫助使用者設計自己的 exec 權限模型，而不是只看單一設定欄位來猜測系統行為。

常見症狀就是：

- `exec denied: allowlist miss`

這通常不是單純「壞掉」，而是你實際採用的 exec 權限模型，比你以為的更保守。

---

## 三種常見策略

### A. 保守型（Conservative）

**做法：**
只放行極少數命令；其他一律擋下，或保留人工審批。

**特徵：**
- allowlist 很小
- 權限邊界清楚
- agent 能做的事有限

**優點：**
- 風險最低
- 最不容易誤傷 host
- 適合高度敏感環境

**缺點：**
- 很容易遇到 `allowlist miss`
- 新任務常要補規則
- 使用體驗比較卡

**適合：**
- 很少使用 `exec`
- 系統安全遠比自動化便利更重要
- 可以接受較多人工確認

---

### B. 便利型（Convenience）

**做法：**
預設放行大量常用命令，甚至接近全開，讓 agent 幾乎想跑就能跑。

**特徵：**
- allowlist 很大
- 執行能力最強
- 最少被權限卡住

**優點：**
- 體驗最順
- 很適合快速開發、原型與實驗
- 對 coding / automation 友善

**缺點：**
- 風險最高
- agent 若誤判，影響面較大
- 不適合直接暴露在高風險聊天入口

**適合：**
- 隔離良好的 dev box
- 高度信任的本機環境
- 願意用較高風險換取效率

---

### C. 混合型（Hybrid）

**做法：**
放行低風險、常用命令；高風險操作保留審批；複雜長任務交給 ACP / sub-agent。

**特徵：**
- allowlist 中等大小
- 日常任務夠順
- 危險操作仍有閘門

**優點：**
- 可用性與安全最平衡
- main chat agent 可以做事，但不至於權限過大
- 比較適合長期維護

**缺點：**
- 仍需維護 allowlist
- 需要自己定義「低風險 / 高風險」邊界
- 偶爾仍要補新命令

**適合：**
- 會在 Telegram / Discord / chat 中直接使用 main agent
- 想讓 agent 有日常工作能力，但不希望 host 幾乎全開
- 想把複雜任務分流到 ACP / sub-agent

---

## 怎麼選

可以用這個簡單判斷：

- **我幾乎不用 exec** → A
- **這台機器本來就是開發沙盒** → B
- **這是 chat-facing 的主 agent，要平衡安全與可用性** → C

如果沒有很強的反例，**C 通常是最實際的預設值**。

---

## C 方案的實務分流

### 1. 日常開發 / 查檔 / 常見 shell 工作

交給 main agent 直接執行。

例如：
- `bash`
- `sh`
- `env`
- `python3`
- `git`
- `node`
- `npm`

### 2. 低風險檔案 / 文字工具

通常也可以直接放行：
- `cat`
- `ls`
- `find`
- `grep`
- `sed`
- `tee`

### 3. 高風險或系統級操作

建議不要預設放行，例如：
- `sudo`
- `docker`
- `systemctl`
- 破壞性檔案操作
- 系統層級權限 / 網路 / 服務管理命令

這些更適合：
- approval
- 人工確認
- 或專門 agent / ACP session 執行

### 4. 複雜長任務

例如：
- 大型 code 變更
- 長時間除錯
- 多步驟修 repo
- 需要持續觀察輸出的工作

這類更適合分流到：
- ACP harness
- sub-agent
- sandboxed coding flow

也就是讓 main agent 保持「夠能做事」，但不要承擔所有高權限或長任務。

---

## 範例 allowlist 分層

### Tier 1：常見開發工具

- `bash`
- `sh`
- `env`
- `python3`
- `git`
- `node`
- `npm`

### Tier 2：低風險檔案 / 文字工具

- `cat`
- `ls`
- `find`
- `grep`
- `sed`
- `tee`

### Keep gated：保留審批

- `sudo`
- `docker`
- `systemctl`
- 破壞性檔案與系統管理工具

一個實用原則是：**先從 Tier 1 開始，依實際使用再慢慢補 Tier 2。**

---

## 常見誤解

### 誤解 1：`security = "full"` 代表什麼都能跑

不一定。

在 OpenClaw 中，`tools.exec.security = "full"` 只是整體執行策略的一部分。若 `exec-approvals.json` 中沒有對應 allowlist / trust，仍可能出現：

- `exec denied: allowlist miss`

### 誤解 2：只要 agent 有 exec，就應該直接給很多命令

不一定。

對 chat-facing main agent 來說，能力過大通常不是好事。很多時候更合理的做法是：

- main agent：保留日常工作能力
- 高風險工作：approval
- 複雜工作：ACP / sub-agent

### 誤解 3：一直補 allowlist 就好

只補 allowlist 可以解問題，但不一定能解「策略」。

如果你的使用模式已經明顯分成：
- 日常小任務
- 高風險 host 任務
- 長任務 / 複雜任務

那就應該明確分流，而不是把所有能力都堆給同一個 main agent。

---

## 推薦結論

對大多數有聊天入口（Telegram / Discord / Slack）且真的會讓 agent 幹活的環境，建議預設採用：

## **C. 混合型**

一句話就是：

- **低風險常用命令直接放行**
- **高風險命令保留審批**
- **複雜任務交給 ACP / sub-agent**

這通常是長期最穩、也最符合實際使用的配置。

---

## 可選：ASCII 決策圖

```text
==============================
OpenClaw exec 三種策略
==============================

            [你想怎麼管理 exec 權限？]
                        |
        +---------------+---------------+
        |               |               |
        v               v               v
        A               B               C
     保守型          便利型          混合型

A = 安全第一，但常卡
B = 效率第一，但風險高
C = 日常命令放行，危險操作保留閘門
```

