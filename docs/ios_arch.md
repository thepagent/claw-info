# iOS Architecture Documentation

OpenClaw iOS architecture covering gateway modes, Apple Watch integration, and communication patterns.

## Overview

OpenClaw iOS app serves dual roles:
1. **Client** - User interface for interacting with AI agent
2. **Gateway** - Bridge between device capabilities and agent backend

## iOS Gateway Architecture

### Embedded vs Remote Gateway

**Embedded Gateway (Default)**
- Gateway runs inside iOS app process
- Direct connection to agent backend
- Lower latency for local capabilities
- Suitable for standalone mobile usage

**Remote Gateway (Advanced)**
- iOS app connects to external gateway (Mac/Server)
- Centralized gateway management
- Shared agent sessions across devices
- Requires network connectivity

### Gateway Modes Comparison

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

### Configuration

**Embedded Gateway**
- No configuration needed
- Automatically starts with app

**Remote Gateway**
- Set gateway URL in app settings
- Complete pairing flow for authentication
- Supports Tailscale/VPN for secure remote access

## Apple Watch Integration

### Overview

Apple Watch companion app receives notifications from iOS via WatchConnectivity framework. Introduced in [PR #20054](https://github.com/openclaw/openclaw/pull/20054).

### Architecture

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

### Bridge Commands

#### `watch.status`

Query Apple Watch connection status.

**Request:**
```typescript
await callGateway({
  command: 'watch.status'
})
```

**Response:**
```typescript
{
  supported: boolean,        // WatchConnectivity available
  paired: boolean,           // Watch is paired
  appInstalled: boolean,     // OpenClaw watch app installed
  reachable: boolean,        // Watch currently reachable
  activationState: string    // "activated" | "inactive" | "notActivated"
}
```

#### `watch.notify`

Send notification to Apple Watch.

**Request:**
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

**Response:**
```typescript
{
  deliveredImmediately: boolean,  // Sent via sendMessage
  queuedForDelivery: boolean,     // Queued via transferUserInfo
  transport: string               // "sendMessage" | "transferUserInfo"
}
```

### Transport Modes

**sendMessage (Immediate)**
- Used when watch is reachable
- Requires active connection
- Immediate delivery with reply handler
- Falls back to transferUserInfo on failure

**transferUserInfo (Queued)**
- Used when watch is unreachable
- Queued for later delivery
- Delivered when watch becomes available
- Guaranteed delivery

### Key Components

#### iOS Side

**[GatewayConnectionController.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Sources/Gateway/GatewayConnectionController.swift)**
- Manages gateway lifecycle
- Registers `watch` capability if supported
- Exposes watch status in permissions

**[WatchMessagingService.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Sources/Services/WatchMessagingService.swift)**
- Implements `WatchMessagingServicing` protocol
- Manages `WCSession` delegate
- Handles message sending with fallback logic
- Provides status snapshots

**[NodeAppModel.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Sources/Model/NodeAppModel.swift)**
- Routes `watch.status` and `watch.notify` commands
- Validates message content (rejects empty messages)
- Returns appropriate error codes

#### watchOS Side

**[WatchConnectivityReceiver.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/WatchExtension/Sources/WatchConnectivityReceiver.swift)**
- Receives messages from iPhone
- Parses notification payloads
- Supports all WatchConnectivity transport methods

**[WatchInboxStore.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/WatchExtension/Sources/WatchInboxStore.swift)**
- Persists messages to UserDefaults
- Deduplicates messages via delivery key
- Posts local notifications via `UNUserNotificationCenter`
- Observable state for UI updates

**[WatchInboxView.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/WatchExtension/Sources/WatchInboxView.swift)**
- Displays latest notification
- Shows title, body, and timestamp
- SwiftUI-based interface

### Capability Registration

iOS automatically registers `watch` capability when supported:

```swift
// GatewayConnectionController.swift
if WatchMessagingService.isSupportedOnDevice() {
    caps.append(OpenClawCapability.watch.rawValue)
}
```

Gateway exposes watch status in device permissions:

```typescript
{
  watchSupported: true,
  watchPaired: true,
  watchAppInstalled: true,
  watchReachable: true
}
```

### Use Cases

- **Meeting reminders** - Agent sends time-sensitive notifications
- **Task alerts** - Important todo items pushed to watch
- **Status updates** - Quick glanceable information
- **Emergency notifications** - Critical alerts with haptic feedback

### Limitations

- WatchConnectivity only supports iPhone ↔ Watch direct connection
- Watch messages cannot bypass iOS app to reach remote gateway
- Watch must be paired and app installed for notifications
- Message size limits apply (use concise content)

## Bridge Commands & Capabilities

### Capability System

iOS gateway registers capabilities based on device support:

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
// ... more capabilities
```

### Command Registration

Commands are registered per capability:

```swift
// Watch commands
if caps.contains("watch") {
    commands.append("watch.status")
    commands.append("watch.notify")
}

// Photo commands
if caps.contains("photos") {
    commands.append("photos.latest")
}

// Location commands
if caps.contains("location") {
    commands.append("location.current")
    commands.append("location.track")
}
```

### Protocol Compatibility

iOS gateway uses same WebSocket protocol as desktop gateway:
- `BridgeInvokeRequest` / `BridgeInvokeResponse` message format
- JSON-based parameter encoding
- Consistent error codes (`invalidRequest`, `unavailable`, etc.)
- Capability negotiation on connection

## Configuration Examples

### Remote Gateway Setup

1. **On Mac/Server:**
   ```bash
   openclaw gateway start
   openclaw status  # Note the gateway URL
   ```

2. **On iOS:**
   - Open Settings → Gateway
   - Enter gateway URL (e.g., `ws://192.168.1.100:18789`)
   - Complete pairing flow
   - Verify connection status

3. **With Tailscale:**
   - Install Tailscale on both devices
   - Use Tailscale IP for gateway URL
   - Secure connection over VPN

### Pairing Mechanism

- iOS generates pairing request with device info
- Gateway displays pairing code
- User confirms code on iOS
- Shared token established for authentication
- Token persisted for future connections

## Testing

### Unit Tests

Watch integration includes comprehensive tests:

**[NodeAppModelInvokeTests.swift](https://github.com/openclaw/openclaw/blob/main/apps/ios/Tests/NodeAppModelInvokeTests.swift)**
- `handleInvokeWatchStatusReturnsServiceSnapshot` - Status query
- `handleInvokeWatchNotifyRoutesToWatchService` - Notification routing
- `handleInvokeWatchNotifyRejectsEmptyMessage` - Input validation
- `handleInvokeWatchNotifyReturnsUnavailableOnDeliveryFailure` - Error handling

### Manual Testing

1. **Watch Status:**
   ```bash
   # Via gateway command
   openclaw invoke watch.status
   ```

2. **Send Notification:**
   ```bash
   # Via gateway command
   openclaw invoke watch.notify --title "Test" --body "Hello Watch"
   ```

3. **Verify on Watch:**
   - Check WatchInboxView updates
   - Confirm local notification appears
   - Verify haptic feedback

## References

- [PR #20054: iOS Apple Watch companion MVP](https://github.com/openclaw/openclaw/pull/20054)
- [OpenClaw Main Repository](https://github.com/openclaw/openclaw)
- [Apple WatchConnectivity Framework](https://developer.apple.com/documentation/watchconnectivity)
