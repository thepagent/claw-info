# ClawJacked 漏洞：原因、修復與安全性演進歷程

## 概述

「ClawJacked」（CVE 相關編號見下方）是指 2026 年初針對 OpenClaw Gateway 的關鍵安全性漏洞鏈。攻擊者可透過惡意網頁、跨來源 WebSocket 連線或注入惡意記憶，試圖「劫持」Agent 的執行權限與敏感資訊。本漏洞由 Oasis Security 發現並通報，OpenClaw 團隊在 24 小時內即釋出修復版本。

本文件記錄了從 `v2026.02.14` 到 `v2026.02.25` 的完整修復歷程，旨在為開發者提供安全性設計的背景參考。

---

## 攻擊流程

ClawJacked 的核心攻擊鏈如下：

```
惡意網站
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. JavaScript 開啟到 localhost 的        │
│    WebSocket 連線（瀏覽器不阻擋）          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 2. 暴力破解 Gateway 密碼                  │
│    （缺少速率限制機制）                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 3. 靜默註冊為受信任設備                   │
│    （Gateway 對 localhost 自動批准）      │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 4. 完全控制 AI Agent                     │
│    ・讀取配置與機密                       │
│    ・列舉已連線的 Nodes                   │
│    ・讀取應用程式日誌                     │
│    ・執行任意指令                         │
└─────────────────────────────────────────┘
```

**關鍵技術見解**：
> "Any website you visit can open one to your localhost. Unlike regular HTTP requests, the browser doesn't block these cross-origin connections." — Oasis Security

> "The gateway relaxes several security mechanisms for local connections - including silently approving new device registrations without prompting the user."

---

## 漏洞分析：為什麼會發生 ClawJacked？

核心問題在於 **「權限邊界模糊」** 與 **「來源信用過度擴張」**：

1. **記憶中毒 (Memory Poisoning)**：Agent 預設信任召回的內容為「事實」，攻擊者可透過注入指令來引發間接指令攻擊。
2. **跨來源連線 (Origin Takeover)**：Gateway 的 WebSocket 未嚴格限制 Origin，惡意網站可在後台發起連線並操作受害者已配對過的 Session。
3. **身分冒充與繞過 (Bypass)**：利用 IPv6 multicast/mapped-IPv4 地址、符號連結（Symlink）或 Shell 元字符，繞過 SSRF 檢查與 `execApproval` 批准機制。
4. **Log Poisoning（日誌中毒）**：攻擊者可透過 WebSocket 注入惡意內容到日誌，Agent 在讀取自身日誌進行除錯時可能被間接提示注入影響。

---

## 修復歷程與技術細節

### 🛑 階段一：防禦外部注入 (v2026.02.13 - v2026.02.14)

**v2026.02.13** - Log Poisoning 修復：
*   修復日誌中毒漏洞，防止攻擊者透過 WebSocket 注入惡意內容至日誌檔案。

**v2026.02.14** - 多項安全強化：
*   **記憶體去毒化**：將召回記憶（Recalled Memories）強制標記為 `untrusted` 內容。
*   **Webhook 強制驗證**：要求所有 Inbound Webhook（如 Telegram, Twilio）必須配置 `webhookSecret` 並進行簽名檢查，否則拒絕啟動。
*   **路徑邊界保護**：為 `apply_patch` 與 FS 工具強制執行工作區根目錄（Workspace-root）邊界檢查。

### 🛡️ 階段二：系統結構加固 (v2026.02.15)
*   **雜湊算法升級**：將沙箱緩存雜湊從 SHA-1 升級為 **SHA-256**。
*   **容器隔離強化**：明確禁止危險的 Docker 設定（如 host network、unconfined seccomp），防範容器逃逸。
*   **自動化遮罩**：在日誌與狀態回應中自動遮罩 Bot Token 與內部系統路徑。

### ⚓ 階段三：ClawJacked 核心修復 (v2026.02.25)
*   **WebSocket 跨來源防護（核心修復）**：
    *   對瀏覽器連線強制執行 **Origin Check** 與 **Password Throttling（密碼暴力破解節流）**。
    *   封鎖靜默自動配對（Silent Auto-pairing）路徑。
*   **指令路徑綁定**：將 `system.run` 的批准（Approval）與正規化後的執行絕對路徑與精確 argv 繫結，徹底防堵利用 Symlink 或空格路徑的繞過。
*   **反應事件授權 (Reaction Ingress)**：所有渠道（Signal, Discord, Slack 等）的反應事件在處理前，必須通過與訊息同等的 DM/Group 授權檢查。
*   **SSRF 防護完善**：將 IPv6 multicast 字面量（`ff00::/8`）納入封鎖範圍。

---

## CVE 編號對照表

| CVE 編號 | 嚴重程度 | 修復版本 | 說明 |
|----------|----------|----------|------|
| CVE-2026-25593 | High | v2026.2.2 | 遠端程式碼執行 |
| CVE-2026-24763 | Moderate-High | v2026.1.29 | 指令注入 |
| CVE-2026-25157 | Moderate | v2026.2.1 | SSRF |
| CVE-2026-25475 | Moderate | v2026.2.2 | 認證繞過 |
| CVE-2026-26319 | High | v2026.2.14 | 路徑遍歷 |
| CVE-2026-26322 | High | v2026.2.14 | 命令注入 |
| CVE-2026-26329 | High | v2026.2.14 | 遠端程式碼執行 |

---

## 經驗教訓與最佳實踐

1. **零信任原則 (Zero Trust)**：不再區分「內部記憶」或「外部訊息」，所有輸入在轉換為 Action 前皆必須視為不受信任。
2. **顯式選擇 (Explicit Opt-in)**：敏感功能（如 `autoCapture`）應預設關閉，並由使用者明確開啟。
3. **路徑正規化**：檔案與指令的路徑應在驗證前進行正規化（Normalization），以防止編碼或連結攻擊。
4. **安全失敗 (Fail-Closed)**：當安全性配置（如 Token）缺失時，系統應選擇停止服務（Fail-closed），而非降級運行。
5. **本機連線也需驗證**：永遠不要假設來自 localhost 的連線是可信的——瀏覽器的同源政策不阻擋 WebSocket 對 localhost 的連線。
6. **速率限制不可或缺**：即使是有密碼保護的服務，也必須實施暴力破解防護。

---

## 參考來源

- [The Hacker News: ClawJacked Flaw Lets Malicious Sites Hijack Local OpenClaw AI Agents](https://thehackernews.com/2026/02/clawjacked-flaw-lets-malicious-sites.html)
- [Oasis Security: OpenClaw Vulnerability Analysis](https://www.oasis.security/blog/openclaw-vulnerability)
- [Eye Security: Log Poisoning in OpenClaw](https://research.eye.security/log-poisoning-in-openclaw/)
- [Microsoft: Running OpenClaw Safely](https://www.microsoft.com/en-us/security/blog/2026/02/19/running-openclaw-safely-identity-isolation-runtime-risk/)

---

## 相關連結
- [OpenClaw v2026.02.13 發佈說明](../../release-notes/2026-02-13.md)
- [OpenClaw v2026.02.14 發佈說明](../../release-notes/2026-02-14.md)
- [OpenClaw v2026.02.15 發佈說明](../../release-notes/2026-02-15.md)
- [OpenClaw v2026.02.25 發佈說明](../../release-notes/2026-02-25.md)