---
title: "SSH Image entrypoint-ssh.sh Bug 修復：\"$@\" 參數傳遞問題"
date: 2026-04-27 14:00:00 +0800
categories:
  - AI
tags:
  - Hermes
  - Docker
  - SSH
  - Debug
---

## 問題描述

### Bug：`entrypoint-ssh.sh` 漏掉 `"$@"`，導致 `gateway run` 參數被吃掉

**根本原因**：
docker-compose.yml 定義了 `command: gateway run`，但 `entrypoint-ssh.sh` 最後一行是：

```bash
exec /opt/hermes/docker/entrypoint.sh   # 缺少 "$@"
```

`"$@"` 是把所有命令列參數（原樣）往下傳。沒有它，`gateway run` 這個參數就消失了，Hermes 進了互動模式（CLI/TUI）而不是 Gateway 模式。

**正確版本**：
```bash
exec /opt/hermes/docker/entrypoint.sh "$@"
```

**症狀**：
- `docker compose up -d` 後，Telegram bot 沒反應
- Docker Desktop log 顯示直接進入了 `hermes tui`（互動模式）
- Gemini 手動在運行中的 container 裡修了 `entrypoint-ssh.sh`，現在正常了

---

## 背景知識

- **為什麼 `gateway run` 會不見**：Dockerfile ENTRYPOINT 是 `entrypoint-ssh.sh`，docker-compose `command` 是 `gateway run`。`entrypoint-ssh.sh` 最後必須把 `"$@"`（包括 `gateway run`）往下傳給 `entrypoint.sh`。`entrypoint.sh` 會把參數傳給 `hermes` CLI，最後 Hermes 啟動 Gateway 模式而不是 TUI 模式。
- **`exec` 的意義**：`exec` 置換當前 shell 程序，不 fork 新 process，確保 PID 不變、Signal 傳遞正確。
- **`"$@"` 的意義**：保留所有參數的完整性（包含空白字元），每個參數分開傳遞。不用 `"$@"` 的話，參數會全部 merge 成一個字串。

---

## 修復步驟

### Step 1：確認當前 `entrypoint-ssh.sh` 的問題行

在 `my-config-v2026.4.23` branch 的 `docker/entrypoint-ssh.sh`，最後一行應該是：

```bash
exec /opt/hermes/docker/entrypoint.sh
```

要把這行改成：

```bash
exec /opt/hermes/docker/entrypoint.sh "$@"
```

### Step 2：用 GitHub API 修改檔案

```bash
gh api \
  -X GET /repos/kuniakil/hermes-agent/contents/docker/entrypoint-ssh.sh \
  -q '.content' | base64 -d | \
  sed 's|exec /opt/hermes/docker/entrypoint.sh$|exec /opt/hermes/docker/entrypoint.sh "$@"|' | \
  gh api \
  -X PUT /repos/kuniakil/hermes-agent/contents/docker/entrypoint-ssh.sh \
  --field message="fix: pass \"\$@\" to entrypoint.sh so 'gateway run' is not lost" \
  --field branch="my-config-v2026.4.23" \
  --field content@- \
  --encoding base64
```

### Step 3：觸發 GitHub Actions rebuild

```bash
gh workflow run ghcr-publish.yml \
  -f docker_tag=v2026.4.23-ssh \
  --repo kuniakil/hermes-agent
```

---

## 驗證檢查清單

- [ ] `docker/entrypoint-ssh.sh` 最後一行包含 `"$@"`
- [ ] GitHub commit 已 push 到 `my-config-v2026.4.23`
- [ ] GitHub Actions build 已完成，沒有錯誤
- [ ] `ghcr.io/kuniakil/hermes-agent:v2026.4.23-ssh` 已更新
- [ ] Mac 上 `docker compose down && up -d` 後 Telegram 正常