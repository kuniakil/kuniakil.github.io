---
title: "Mac、Oracle VPS 與 GitHub 協作流程"
date: 2026-05-24 13:30:00 +0800
categories:
- 技術文章
tags:
- rclone
- GitHub
- 學習筆記
---

# Mac、Oracle VPS 與 GitHub 協作流程

## 背景

本文件的目的是記錄一種在多種環境下協作管理專案資料的工作流程，適用於以下情境：

- 在本機 Mac 編寫設定檔（使用 Claude Code AI 輔助）
- 在 Oracle VPS（1GB RAM）上實際操作 Kubernetes（k0s + k9s）
- 將專案備份到 GitHub 個人倉庫
- 未來轉移到新主機時可以快速恢复環境

## 目錄結構對應

| 機器 | 路徑 | 說明 |
|------|------|------|
| Mac | `~/oracle-projects/` | 本地工作目錄 |
| Oracle | `/home/ubuntu/projects/` | 對應 `oracle-remote:projects` |
| GitHub | `kuniakil/kuniakil.github.io` | 備份倉庫（`_posts/` 目錄放文章） |

## 工具與設定

### 1. Mac 端

**已設定的工具：**

- `rclone`（官方 binary，含 cmount 標籤）位於 `~/bin/rclone`
- SSH Key 用於連線到 Oracle 和 GitHub
- PAT（Personal Access Token）用於 GitHub 操作

**同步腳本（置於 `~/oracle-projects/`）：**

- `push-to-oracle.sh` — 將本地專案同步到 Oracle
- `pull-from-oracle.sh` — 將 Oracle 的專案拉回 Mac

**使用方式：**

```bash
# Mac → Oracle
cd ~/oracle-projects
./push-to-oracle.sh

# Mac → Oracle（指定子資料夾）
./push-to-oracle.sh k0s-config

# Oracle → Mac
./pull-from-oracle.sh

# Oracle → Mac（指定子資料夾）
./pull-from-oracle.sh k0s-config
```

### 2. Oracle VPS 端

**已安裝的工具：**

- Git
- k0s（Kubernetes 發行版）
- k9s（文字版 Kubernetes 控制台）
- Neovim（文字編輯器）

**GitHub 認證設定：**

```bash
# 設定 Git 使用者資訊
git config --global user.name "Your Name"
git config --global user.email "your@email.com"

# 讓 Git 記住 PAT
git config --global credential.helper store
```

之後第一次 `git push` 會要求輸入帳號和 PAT，之後就會自動記住。

## 工作流程

### 流程一：在 Mac 寫設定檔，部署到 Oracle

1. 在 Mac 的 `~/oracle-projects/` 下建立或編輯專案資料夾
2. 使用 Claude Code 幫忙寫 YAML 或設定檔
3. 執行 `./push-to-oracle.sh` 將檔案同步到 Oracle
4. 連線到 Oracle（VS Code Remote SSH 或 SSH 終端機）
5. 在 Oracle 上執行 `kubectl apply -f xxx.yaml` 或使用 k9s

### 流程二：個人網站文章發布

1. 在 Mac 的 `~/oracle-projects/` 下的 `_posts/` 目錄建立 `.md` 檔案
2. 格式：`YYYY-MM-DD-標題.md`
3. 確保 front matter 正確（title, date, categories, tags）
4. Git push 到 `kuniakil/kuniakil.github.io`
5. GitHub Actions 會自動發布到 https://new.3pm.lol/

### 流程三：Oracle 修改後同步回 Mac

1. 在 Oracle 的 `/home/ubuntu/projects/` 下修改檔案
2. 執行 `git push` 將變更推到 GitHub（可選）
3. 在 Mac 執行 `./pull-from-oracle.sh` 將變更拉回本地

## 注意事項

- 每次重開機後，Mac 的 ssh-agent 需要重新載入 SSH Key：
  ```bash
  ssh-add ~/.ssh/id_ed25519
  ```
- `rclone sync` 是單向同步，不會自動雙向
- 如果兩邊都有修改，先手動決定要以哪邊為主，再執行對應的 push 或 pull

## 未來擴展

當取得更大容量、記憶體的主機時：

1. 在新主機 clone GitHub 倉庫
2. 或使用 `rclone sync` 從 Mac 或 Oracle 同步專案資料
3. 參考本文檔重新設定工作流程