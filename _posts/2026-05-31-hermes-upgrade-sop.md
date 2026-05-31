---
title: "Hermes Agent Upgrade SOP"
date: 2026-05-31 09:00:00 +0800
categories:
  - Hermes
  - DevOps
tags:
  - hermes
  - upgrade
  - CI/CD
  - SSH
---

## Overview

每次升級 Hermes Agent 到新版本時，遵循以下流程確保安全、可追蹤。

## 升級流程

### Step 1: Fetch 官方最新資訊

```bash
git fetch origin --tags
```

確保拿到官方最新的 tags。

### Step 2: 建立新 branch

```bash
git checkout -b my-config-v2026.x.x <new-official-tag>
```

例如：
```bash
git checkout -b my-config-v2026.5.29.2 v2026.5.29.2
```

### Step 3: 帶入 Custom Commits

檢查相對於舊版的 custom commits：

```bash
# 查看從舊版到新版有多少 custom commits
git log --oneline old-tag..my-config-old --ancestry-path | grep -v "Merge"
```

常見的 custom commits：
- SSH 設定 (entrypoint-ssh.sh, Dockerfile)
- PYTHONPATH for faster-whisper
- .env HERMES_IMAGE 版本
- .github/workflows/ghcr-publish.yml

#### Step 3a: 先嘗試 Rebase

```bash
git rebase official/v2026.x.x
```

如果衝突少，繼續 rebase --continue。

如果衝突太多（超過 10 個），放棄並用 Step 3b。

#### Step 3b: 改用 Cherry-pick

```bash
# 從最舊的 custom commit 開始，一個一個 cherry-pick
git cherry-pick <commit-1>
git cherry-pick <commit-2>
# ... 繼續
```

遇到衝突時選擇保留 ours（我們的版本），除非官方有新功能需要。

### Step 4: 更新 .env 版本

```bash
# 確認 .env 是正確的新版本
HERMES_IMAGE=ghcr.io/kuniakil/hermes-agent:v2026.x.x
```

### Step 5: Commit + Push

```bash
git add . && git commit -m "chore: upgrade to v2026.x.x"
git push -u origin my-config-v2026.x.x
```

把 branch 推到 remote 作為備份。

### Step 6: Trigger Build

```bash
gh workflow run ghcr-publish.yml -f tag_name=v2026.x.x --ref my-config-v2026.x.x
```

使用 API 指定 ref：
```bash
curl -s -X POST -H "Authorization: Bearer $(gh auth token)" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/kuniakil/hermes-agent/actions/workflows/ghcr-publish.yml/dispatches \
  -d '{"ref":"my-config-v2026.x.x","inputs":{"tag_name":"v2026.x.x"}}'
```

### Step 7: 測試

#### 7a: Mac 測試 (OrbStack/K3s)

```bash
# 確認 YAML 設定正確
kubectl get deployment hermes-agent -n hermes -o yaml | grep image

# 看 logs
kubectl logs -n hermes -l app=hermes-agent --tail=50

# SSH 測試
ssh -p 2222 hermes@localhost
```

#### 7b: Zeabur 測試

更新 Zeabur deployment 的 image 版本後重啟。

SSH key 可能改變，如果出現警告：
```bash
ssh-keygen -R "[hostname]:2222"
```

## 常見問題

### Q: 忘記 ssh-keygen 密鑰怎麼辦？

```bash
ssh-keygen -R "[hostname]:2222"
```

### Q: Mac 和 Zeabur 誰先用？

先用 Mac 測試，確認沒問題後再上 Zeabur。

### Q: 如果測試失敗怎麼辦？

```bash
# 回到舊版
kubectl rollout undo deployment/hermes-agent -n hermes

# 或者手動 pull 舊版 image
docker pull ghcr.io/kuniakil/hermes-agent:v2026.x.x-old
```

## Branch 命名規則

```
my-config-v2026.5.29.2   → 升級到 v2026.5.29.2
my-config-v2026.5.16     → 升級到 v2026.5.16
...
```

每次升級都留一個 branch，萬一需要 rollback 可以回去。