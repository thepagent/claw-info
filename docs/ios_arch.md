# iOS 架構文檔

## TL;DR

- iOS app 同時扮演**客戶端**與 **Gateway**，可內建或連接遠端 gateway
- Apple Watch 透過 WatchConnectivity 與 iOS 通訊，無法直連遠端 gateway
- 提供 `watch.status` 與 `watch.notify` 兩個 bridge 命令
- 支援兩種傳輸模式：`sendMessage`（即時）與 `transferUserInfo`（排隊）
- Gateway 使用與桌面版相同的 WebSocket protocol 與 capability 系統
- 適用於行動裝置本地能力（相機、位置、通知）與跨裝置 agent 會話

## 使用情境

**何時使用內建 Gateway：**
- 獨立行動使用，無需與其他裝置共享會話
- 需要低延遲存取本地能力（相機、位置）
- 無穩定網路連線至遠端 gateway

**何時使用遠端 Gateway：**
- 需要跨裝置（Mac/iOS/Android）共享 agent 會話
- 集中管理 gateway 配置與 agent 狀態
- 透過 Tailscale/VPN 安全存取家中或辦公室 gateway

**Apple Watch 通知使用場景：**
- 會議提醒、任務提醒等時效性通知
- 快速可瞥見的狀態更新
- 緊急警報（帶觸覺回饋）

## 概述

OpenClaw iOS app 扮演雙重角色：
1. **客戶端** - 與 AI agent 互動的使用者介面
2. **Gateway** - 裝置能力與 agent 後端之間的橋樑

## iOS Gateway 架構

### 內建 vs 遠端 Gateway

**內建 Gateway（預設）**
- Gateway 運行於 iOS app 程序內
- 直接連接至 agent 後端
- 本地能力延遲較低
- 適合獨立行動使用

**遠端 Gateway（進階）**
- iOS app 連接至外部 gateway（Mac/伺服器）
- 集中式 gateway 管理
- 跨裝置共享 agent 會話
- 需要網路連線

### Gateway 模式比較

```
┌─────────────────────────────────────────────────────────────────┐
│              OpenClaw 架構：本地 vs 遠端 Gateway                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  方案一：本地 Gateway（iOS 內建）                                 │
│  ┌──────────┐                                                   │
│  │  Watch   │                                                   │
│  └────┬─────┘                                                   │
│       │ WatchConnectivity                                       │
│       ↓                                                         │
│  ┌──────────────────────┐                                       │
│  │     iOS App          │                                       │
│  │  ┌────────────────┐  │                                       │
│  │  │ Built-in       │  │                                       │
│  │  │ Gateway        │──┼──→ Agent (Cloud)                      │
│  │  └────────────────┘  │                                       │
│  └──────────────────────┘                                       │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  方案二：遠端 Gateway（Mac/Server）                               │
│  ┌──────────┐                                                   │
│  │  Watch   │                                                   │
│  └────┬─────┘                                                   │
│       │ WatchConnectivity                                       │
│       ↓                                                         │
│  ┌──────────────────────┐      WebSocket                        │
│  │     iOS App          │─────────────────┐                     │
│  │  (Thin Client)       │                 │                     │
│  └──────────────────────┘                 ↓                     │
│                                      ┌──────────────────┐       │
│                                      │  Remote Gateway  │       │
│                                      │  (Mac/Server)    │───→ Agent
│                                      └──────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 配置

**內建 Gateway**
- 無需配置
- 隨 app 自動啟動

**遠端 Gateway**
- 於 app 設定中設置 gateway URL
- 完成配對流程以進行身份驗證
- 支援 Tailscale/VPN 以進行安全遠端存取

## Apple Watch 整合

### 概述

Apple Watch 伴侶 app 透過 WatchConnectivity 框架從 iOS 接收通知。於 [PR #20054](https://github.com/openclaw/openclaw/pull/20054) 引入。

### 架構

```
┌─────────────────────────────────────────────────────────┐
│           iOS ↔ Apple Watch 通訊架構                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  iPhone                        Apple Watch             │
│  ┌──────────────────┐          ┌──────────────────┐    │
│  │ iOS App          │          │ watchOS App      │    │
│  │                  │          │                  │    │
│  │ Gateway          │          │ WatchInboxView   │    │
│  │   ↓              │          │   ↑              │    │
│  │ watch.status ────┼──────────┼──→ Status        │    │
│  │ watch.notify ────┼──────────┼──→ Notification  │    │
│  │   ↓              │          │   ↓              │    │
│  │ WatchMessaging   │  WCSession  │ Connectivity    │    │
│  │ Service          │◄─────────►│ Receiver        │    │
│  │                  │          │   ↓              │    │
│  │                  │          │ WatchInboxStore  │    │
│  │                  │          │   ↓              │    │
│  │                  │          │ Local Notify 🔔  │    │
│  └──────────────────┘          └──────────────────┘    │
│                                                         │
│  Transport:                                             │
│  • sendMessage (即時，手錶可達時)                        │
│  • transferUserInfo (排隊，手錶不可達時)                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Bridge 命令

#### `watch.status`

查詢 Apple Watch 連接狀態。

**請求：**
```typescript
await callGateway({
  command: 'watch.status'
})
```

**回應：**
```typescript
{
  supported: boolean,        // WatchConnectivity 可用
  paired: boolean,           // 手錶已配對
  appInstalled: boolean,     // OpenClaw watch app 已安裝
  reachable: boolean,        // 手錶目前可達
  activationState: string    // "activated" | "inactive" | "notActivated"
}
```

#### `watch.notify`

發送通知至 Apple Watch。

**請求：**
```typescript
await callGateway({
  command: 'watch.notify',
  params: {
    title: string,
    body: string,
    priority?: 'active' | 'passive' | 'timeSensitive'
  }
})
```

**回應：**
```typescript
{
  deliveredImmediately: boolean,  // 透過 sendMessage 發送
  queuedForDelivery: boolean,     // 透過 transferUserInfo 排隊
  transport: string               // "sendMessage" | "transferUserInfo"
}
```

### 傳輸模式

**sendMessage（即時）**
- 手錶可達時使用
- 需要活躍連接
- 立即傳送並帶有回覆處理器
- 失敗時回退至 transferUserInfo

**transferUserInfo（排隊）**
- 手錶不可達時使用
- 排隊等待稍後傳送
- 手錶可用時傳送
- 保證傳送

### 關鍵元件

#### iOS 端

#### iOS 端

**[GatewayConnectionController.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Sources/Gateway/GatewayConnectionController.swift)**
- 管理 gateway 生命週期
- 若支援則註冊 `watch` capability
- 於 permissions 中暴露 watch 狀態

**[WatchMessagingService.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Sources/Services/WatchMessagingService.swift)**
- 實作 `WatchMessagingServicing` protocol
- 管理 `WCSession` delegate
- 處理訊息發送與回退邏輯
- 提供狀態快照

**[NodeAppModel.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Sources/Model/NodeAppModel.swift)**
- 路由 `watch.status` 與 `watch.notify` 命令
- 驗證訊息內容（拒絕空白訊息）
- 回傳適當的錯誤碼

#### watchOS 端

**[WatchConnectivityReceiver.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/WatchExtension/Sources/WatchConnectivityReceiver.swift)**
- 接收來自 iPhone 的訊息
- 解析通知 payload
- 支援所有 WatchConnectivity 傳輸方法

**[WatchInboxStore.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/WatchExtension/Sources/WatchInboxStore.swift)**
- 持久化訊息至 UserDefaults
- 透過 delivery key 去重複訊息
- 透過 `UNUserNotificationCenter` 發送本地通知
- 可觀察的狀態供 UI 更新

**[WatchInboxView.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/WatchExtension/Sources/WatchInboxView.swift)**
- 顯示最新通知
- 顯示標題、內容與時間戳記
- 基於 SwiftUI 的介面

### Capability 註冊

iOS 於支援時自動註冊 `watch` capability：

### Capability 註冊

iOS 於支援時自動註冊 `watch` capability：

```swift
// GatewayConnectionController.swift
if WatchMessagingService.isSupportedOnDevice() {
    caps.append(OpenClawCapability.watch.rawValue)
}
```

Gateway 於裝置 permissions 中暴露 watch 狀態：

```typescript
{
  watchSupported: true,
  watchPaired: true,
  watchAppInstalled: true,
  watchReachable: true
}
```

### 使用場景

- **會議提醒** - Agent 發送時效性通知
- **任務提醒** - 重要待辦事項推送至手錶
- **狀態更新** - 快速可瞥見的資訊
- **緊急通知** - 帶有觸覺回饋的關鍵警報

### 限制

- WatchConnectivity 僅支援 iPhone ↔ Watch 直接連接
- Watch 訊息無法繞過 iOS app 到達遠端 gateway
- 通知需要手錶已配對且 app 已安裝
- 訊息大小限制適用（使用簡潔內容）

## Bridge 命令與 Capabilities

### Capability 系統

iOS gateway 根據裝置支援註冊 capabilities：

### Capability 系統

iOS gateway 根據裝置支援註冊 capabilities：

```swift
var caps: [String] = []
caps.append("screen")
caps.append("camera")
if locationMode != .off { 
    caps.append("location") 
}
if WatchMessagingService.isSupportedOnDevice() {
    caps.append("watch")
}
caps.append("photos")
caps.append("contacts")
caps.append("calendar")
// ... 更多 capabilities
```

### 命令註冊

命令按 capability 註冊：

```swift
// Watch 命令
if caps.contains("watch") {
    commands.append("watch.status")
    commands.append("watch.notify")
}

// Photo 命令
if caps.contains("photos") {
    commands.append("photos.latest")
}

// Location 命令
if caps.contains("location") {
    commands.append("location.current")
    commands.append("location.track")
}
```

### Protocol 相容性

iOS gateway 使用與桌面 gateway 相同的 WebSocket protocol：
- `BridgeInvokeRequest` / `BridgeInvokeResponse` 訊息格式
- 基於 JSON 的參數編碼
- 一致的錯誤碼（`invalidRequest`、`unavailable` 等）
- 連接時的 capability 協商

## 配置範例

### 遠端 Gateway 設定

1. **於 Mac/伺服器：**
   ```bash
   openclaw gateway start
   openclaw status  # 記下 gateway URL
   ```

2. **於 iOS：**
   - 開啟設定 → Gateway
   - 輸入 gateway URL（例如 `ws://192.168.1.100:18789`）
   - 完成配對流程
   - 驗證連接狀態

3. **使用 Tailscale：**
   - 於兩個裝置上安裝 Tailscale
   - 使用 Tailscale IP 作為 gateway URL
   - 透過 VPN 的安全連接

### 配對機制

- iOS 產生包含裝置資訊的配對請求
- Gateway 顯示配對碼
- 使用者於 iOS 上確認配對碼
- 建立共享 token 以進行身份驗證
- Token 持久化以供未來連接

## 測試

### 單元測試

Watch 整合包含完整測試：

**[NodeAppModelInvokeTests.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Tests/NodeAppModelInvokeTests.swift)**
- `handleInvokeWatchStatusReturnsServiceSnapshot` - 狀態查詢
- `handleInvokeWatchNotifyRoutesToWatchService` - 通知路由
- `handleInvokeWatchNotifyRejectsEmptyMessage` - 輸入驗證
- `handleInvokeWatchNotifyReturnsUnavailableOnDeliveryFailure` - 錯誤處理

### 手動測試

1. **Watch 狀態：**
   ```bash
   # 透過 gateway 命令
   openclaw invoke watch.status
   ```

2. **發送通知：**
   ```bash
   # 透過 gateway 命令
   openclaw invoke watch.notify --title "測試" --body "你好 Watch"
   ```

3. **於 Watch 上驗證：**
   - 檢查 WatchInboxView 更新
   - 確認本地通知出現
   - 驗證觸覺回饋

## Troubleshooting

### 症狀：Watch 通知未送達

**可能原因：**
1. Watch 未配對或 OpenClaw watch app 未安裝
2. Watch 不可達且 transferUserInfo 佇列已滿
3. 訊息內容為空（title 與 body 皆空白）

**處理方式：**
```bash
# 1. 檢查 watch 狀態
openclaw invoke watch.status

# 2. 確認輸出
# - paired: true
# - appInstalled: true
# - reachable: true (若為 false，訊息會排隊)

# 3. 若 appInstalled 為 false，於 iPhone 上開啟 Watch app 安裝 OpenClaw
```

### 症狀：遠端 Gateway 連接失敗

**可能原因：**
1. Gateway URL 錯誤或 gateway 未啟動
2. 防火牆阻擋 WebSocket 連接
3. 配對 token 過期或無效

**處理方式：**
```bash
# 1. 於 Mac/伺服器確認 gateway 運行
openclaw status
# 確認 Gateway 欄位顯示 "running"

# 2. 測試連線
curl -v ws://<gateway-ip>:18789

# 3. 重新配對
# iOS: 設定 → Gateway → 移除配對 → 重新配對
```

### 症狀：Capability 未註冊

**可能原因：**
1. 裝置不支援該 capability（如 WatchConnectivity）
2. 權限未授予（如位置、相機）
3. Gateway 連接時 capability 檢測失敗

**處理方式：**
```bash
# 1. 檢查裝置 permissions
openclaw invoke device.info
# 查看 permissions 欄位

# 2. iOS 設定中授予必要權限
# 設定 → OpenClaw → 權限

# 3. 重新連接 gateway
# iOS: 關閉 app → 重新開啟
```

### 症狀：sendMessage 失敗回退至 transferUserInfo

**可能原因：**
1. Watch 暫時不可達（螢幕關閉、藍牙斷線）
2. WCSession 尚未完全啟動

**處理方式：**
- 這是正常行為，訊息會排隊等待 watch 可達時傳送
- 若需立即傳送，確保 watch 螢幕開啟且 iPhone 在附近
- 檢查 watch.status 的 `reachable` 欄位

## 安全注意事項

- **配對 token**：妥善保管配對 token，不要分享或提交至版本控制
- **遠端 Gateway**：使用 Tailscale/VPN 而非直接暴露 gateway 至公網
- **權限最小化**：僅授予 app 必要的裝置權限
- **訊息內容**：避免在 watch 通知中包含敏感資訊（通知可能顯示於鎖定畫面）

## 版本相容性

- **iOS**: 需 iOS 15.0+
- **watchOS**: 需 watchOS 11.0+
- **Gateway Protocol**: 與 OpenClaw desktop gateway 2026.2.x+ 相容
- **WatchConnectivity**: 使用 Apple 原生框架，向後相容

## 參考資料

- [PR #20054: iOS Apple Watch companion MVP](https://github.com/openclaw/openclaw/pull/20054)
- [OpenClaw 主要儲存庫](https://github.com/openclaw/openclaw)
- [Apple WatchConnectivity Framework](https://developer.apple.com/documentation/watchconnectivity)
