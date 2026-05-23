---
title: "Hermes SSH 包裝：將 OpenSSH Server 包進 Docker Image"
date: 2026-04-27 10:00:00 +0800
categories:
  - AI
tags:
  - Hermes
  - Docker
  - SSH
  - TUI
---

## 根本問題：Shift+Enter 在 Hermes TUI 無法換行

### 症狀
在 Mac Docker Desktop 環境下，使用 `docker exec hermes hermes --tui` 進入 Hermes TUI 時：
- 按 `Shift+Enter` 應該換行，卻直接送出訊息
- `Alt+Enter` 正常換行
- 直接在 Mac 的 iTerm2 跑 Gemini CLI，Shift+Enter 正常

### 調查過程

**懷疑環節 1：Docker PTY normalize**

一開始以為是 Docker Desktop 的 PTY 層把修飾鍵剝掉了。查了 GitHub：
- Issue #15824（kuniaki 開的）：回覆說是「duplicate of #5346 — Docker PTY normalizes modifier+Enter to plain Enter, platform limitation」
- 但這個說法有問題——如果 Docker PTY 真的 normalize，iTerm2 + Gemini CLI 應該也會爛，但它沒壞

**懷疑環節 2：Hermes TUI 本身不處理 Shift+Enter**

PR #15643 的標題精確描述了問題：
> "fix(ui-tui): Shift+Enter inserts newline instead of submitting"

內容指出 `ink-text-input` 的 `useInput` handler 只處理了 `Alt+Enter`（newline），但 Shift+Enter 被當成普通 Enter 直接 submit 了。PR 還沒 merge（目標 `NousResearch:main`）。

**結論**：問題不在 Docker PTY，也不在 macOS/iTerm2，而在 Hermes TUI（`ink-text-input` 層）壓根不支援 Shift+Enter。官方 PR 尚未 merge，v2026.4.23 未包含此修復。

---

## 我們做的 SSH 包裝

### 目標
既然 Shift+Enter 問題一時半刻無法靠官方解決，我們先解決另一個痛點：
**用 SSH 取代 `docker exec` 進入 container**，獲得乾淨的 TTY 體驗。

### 做法
在 container 內安裝 `openssh-server`，讓 Mac 可以：
```bash
ssh -t -p 2222 hermes@localhost
```
直連 container，不用 `docker exec`。

### 修改的檔案（相對於官方 v2026.4.23）
在 branch `my-config-v2026.4.23` → `ssh` 裡新增/修改：

1. **`Dockerfile`** — 安裝 `openssh-server`
2. **`docker/entrypoint-ssh.sh`** — SSH 環境初始化：
   - `usermod -s /bin/bash hermes`（讓 SSH 用 bash）
   - 建立 `.bashrc`/`.profile`，自動 source `.env`、export PATH
   - `cp /opt/data/config.yaml /opt/data/.hermes/config.yaml`（同步 gateway 和 TUI 的 config）
   - 處理 `SSH_PUBLIC_KEY` 含空格的問題（用 `set -a` + dot source + `unset`）
3. **`docker-compose.yml`** — port mapping `2222:22`，`command: gateway run`

### SSH 連線驗證
- Container 跑 `v2026.4.23-ssh` image
- Mac SSH 進去，key 認證成功，無需密碼
- 環境變數正確帶入（`.bashrc` source 了 `.env`）
- `hermes --tui` 可執行，TUI 正常

---

## 現在的狀態

| 項目 | 狀態 |
|------|------|
| SSH server 包裝 | ✅ 完成 |
| Shift+Enter 修復 | ❌ 官方問題，我們沒辦法修 |
| 分支 | `ssh`（實驗分支） |
| 下一步 | 合併回 `my-config-v2026.4.23` |

---

## 關鍵技術細節

- **hermes user home**: `/opt/data`
- **hermes config**: `/opt/data/.hermes/config.yaml`（TUI 吃這個）
- **gateway config**: `/opt/data/config.yaml`（gateway 吃這個，兩者要同步）
- **hermes binary**: `/opt/hermes/.venv/bin/hermes`
- **SSH port**: 2222（container 內 port 22，映射到 2222）
- **SSH command**: `ssh -t -p 2222 hermes@localhost`
- **SSH key 格式**：`.env` 裡的 `SSH_PUBLIC_KEY` 不能用雙引號包，否則 `authorized_keys` 會多出 `\"` 字元

## 關鍵連結
- 官方 Shift+Enter PR（非 merge）：https://github.com/NousResearch/hermes-agent/pull/15643
- Issue #15824（我們開的）：https://github.com/NousResearch/hermes-agent/issues/15824