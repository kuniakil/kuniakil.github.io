---
title: "Hermes SSH 除錯紀錄：環境變數、Config 同步與 Shell 設定"
date: 2026-04-27 15:00:00 +0800
categories:
  - AI
tags:
  - Hermes
  - Docker
  - SSH
  - Debug
---

## 目標

把 OpenSSH server 包進 Docker image，讓 SSH 可以直接進 container，繞過 Docker exec 的 PTY 修飾鍵問題（Shift+Enter 被 normalize 成普通 Enter）。

---

## 遇到的問題

### 問題 1：SSH 進來沒有環境變數

**症狀**：`hermes --tui` 報 "no API key found"，但 Telegram bot 正常回覆。

**原因**：
- `docker exec bash` 是互動式 non-login shell，環境變數直接來自 container runtime
- SSH 是 login shell，只繼承 sshd daemon 的環境，不繼承 Docker 的 env vars
- SSH login shell 用 `/bin/sh`，不吃 `.bashrc`

**確診方法**：
```bash
ssh -t -p 2222 hermes@localhost
env | grep MINIMAX  # 空
docker exec hermes-agent env | grep MINIMAX  # 有
```

**解法**：在 `.bashrc` 和 `.profile` 裡自動 source `/opt/data/.env`

---

### 問題 2：SSH_PUBLIC_KEY 含雙引號，export 報 "bad variable name"

**症狀**：
```
export: AAAAC3NzaC1lZDI1NTE5AAAAIIVQah...: bad variable name
```

**原因**：
`.env` 裡 `SSH_PUBLIC_KEY="ssh-ed25519 ... mlee-macbook"` 包了雙引號，直接 `source .env` 或 `export` 時，shell 把雙引號視為變數值的一部分，導致 key 後面的 comment（`mlee-macbook`）被當成另一個變數名。

**解法**：
- 在 `entrypoint-ssh.sh` 用 `sed 's/^"//;s/"$//'` 先去除頭尾雙引號再寫入 `authorized_keys`
- 在 `.bashrc`/.profile 裡 `unset SSH_PUBLIC_KEY` 避免 export 時炸掉

---

### 問題 3：TUI 吃不到 MiniMax config，顯示 claude-sonnet-4

**症狀**：SSH 進 TUI 後，模型顯示 claude-sonnet-4，不是 MiniMax-M2.7。

**原因**：
- gateway 吃的 config：`/opt/data/config.yaml`
- TUI（hermes CLI）吃的 config：`/opt/data/.hermes/config.yaml`（由 `hermes config path` 返回）
- `/opt/data/.hermes/config.yaml` 不存在，所以 TUI 用預設值（claude-sonnet-4）

**確診方法**：
```bash
/opt/hermes/.venv/bin/hermes config path
# 輸出：/opt/data/.hermes/config.yaml

ls /opt/data/.hermes/config.yaml
# 輸出：No such file or directory
```

**解法**：在 `entrypoint-ssh.sh` 裡啟動 sshd 前，先：
```bash
cp /opt/data/config.yaml /opt/data/.hermes/config.yaml
```

---

### 問題 4：hermes --tui 路徑不對

**症狀**：`hermes --tui` → `command not found`

**原因**：`/opt/hermes/.venv/bin` 不在 SSH login session 的 PATH 裡（`hermes` 安裝在 venv 裡）

**解法**：在 `.bashrc` 和 `.profile` 加：
```bash
export PATH="/opt/hermes/.venv/bin:$PATH"
```

---

## 關鍵檔案位置（container 內）

| 檔案 | 用途 |
|------|------|
| `/opt/data/.env` | API keys 和 SSH_PUBLIC_KEY |
| `/opt/data/config.yaml` | gateway 吃的 config |
| `/opt/data/.hermes/config.yaml` | TUI/hermes CLI 吃的 config |
| `/opt/data/.ssh/authorized_keys` | SSH 公鑰 |
| hermes user home | `/opt/data`（不是 `/home/hermes`）|

---

## 發現的有用指令

```bash
# 查 hermes 實際讀哪個 config
/opt/hermes/.venv/bin/hermes config path

# 查 hermes user 登入 shell
grep hermes /etc/passwd

# SSH 後直接執行 TUI
. /opt/data/.env 2>/dev/null; unset SSH_PUBLIC_KEY; /opt/hermes/.venv/bin/hermes --tui
```