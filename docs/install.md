# Install（安裝）

> 目標：用最少步驟把 OpenClaw 安裝好，並避免常見的 PATH / 權限 / Node 版本坑。
>
> 本文件偏「可操作」，不是全平台完整指南。

---

## TL;DR

```bash
# 1) 安裝 Node.js（建議用 nvm 或 Volta 管）
node -v
npm -v

# 2) 安裝 OpenClaw CLI
npm i -g openclaw

# 3) 啟動 onboarding + 安裝 daemon
openclaw onboard --install-daemon

# 4) 驗證
openclaw gateway status
```

---

## 1) 先決條件

- Node.js LTS（建議 >= 20）
- npm
- 可連外下載套件（公司網路可能要 proxy）

### 建議：不要用系統自帶 node

系統自帶 node 常常太舊，或權限/路徑容易混亂。

---

## 2) macOS 安裝

### 2.1 安裝 Node.js

（擇一）

- 用 Homebrew：

```bash
brew install node
```

- 或用 nvm（更好管理多版本）：

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install --lts
nvm use --lts
```

### 2.2 安裝 OpenClaw

```bash
npm i -g openclaw
openclaw --version
```

### 2.3 Onboard + daemon

```bash
openclaw onboard --install-daemon
openclaw gateway status
```

---

## 3) Linux 安裝

步驟同 macOS：先裝 Node.js，再 `npm i -g openclaw`。

若是 VPS/Headless 環境：

- 建議把 `openclaw gateway` 設成 systemd/daemon（onboard 的 `--install-daemon` 通常會處理）
- 防火牆先不要開外網入口（避免暴露管理介面）

---

## 4) 升級 / 釘版本

### 4.1 升級 CLI

```bash
npm i -g openclaw@latest
openclaw --version
```

### 4.2 釘版本（避免大改動）

```bash
npm i -g openclaw@<version>
```

---

## 5) 移除（Uninstall）

```bash
npm rm -g openclaw
```

daemon/service 如何移除取決於你的安裝方式（systemd/launchd）。

---

## 6) 常見安裝問題

### 6.1 `openclaw: command not found`

- 確認 `npm bin -g` 是否在 PATH
- 重新開新 shell

### 6.2 權限錯誤（EACCES）

- 不建議用 `sudo npm -g ...`
- 用 nvm/Volta 解決全域 npm 權限

### 6.3 Node 版本衝突

- `which node` / `node -v` 確認目前實際使用版本
- 若你用 nvm，確保 shell 有載入 nvm

---

## 下一步

- `docs/start.md`
- `docs/troubleshooting.md`
