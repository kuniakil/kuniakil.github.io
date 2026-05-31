---
title: "Project Upgrade SOP (General)"
date: 2026-05-31 10:00:00 +0800
categories:
  - DevOps
  - Git
tags:
  - upgrade
  - git
  - CI/CD
  - best-practices
---

## Overview

每次升級任一專案到新版本時，遵循以下流程確保安全、可追蹤。

## 適用專案

- Hermes Agent
- OpenClaw
- 其他類似的 Git-based 專案

## 升級流程

### Step 1: Fetch 官方最新資訊

```bash
git fetch origin --tags
```

確保拿到官方最新的 tags。

### Step 2: 確認升級目標

```bash
# 列出所有可用 tags
git tag -l | grep <version-pattern>

# 查看目前所在的 branch 和 commit
git branch -v
```

### Step 3: 建立新 Branch

```bash
git checkout -b <project>-config-<new-version> <official-tag>
```

例如：
```bash
# Hermes
git checkout -b my-config-v2026.5.29.2 v2026.5.29.2

# OpenClaw
git checkout -b openclaw-config-v2026.6.1 v2026.6.1
```

### Step 4: 找出 Custom Commits

檢查相對於舊版的 custom commits：

```bash
# 查看從舊版到現在有多少 custom commits
git log --oneline <old-tag>..HEAD --ancestry-path | grep -v "Merge"
```

### Step 5: 帶入 Custom Commits

#### Step 5a: 先嘗試 Rebase

```bash
git rebase <official-tag>
```

- 如果衝突少 → 繼續 `git rebase --continue`
- 如果衝突多（超過 10 個）→ 放棄，改用 Step 5b

#### Step 5b: 改用 Cherry-pick

```bash
# 從最舊的 custom commit 開始，依序 cherry-pick
git cherry-pick <oldest-commit-hash>
git cherry-pick <next-commit-hash>
# ... 繼續
```

**衝突時的處理原則：**
| 情況 | 處理 |
|------|------|
| 官方完全移除某檔案（如 entrypoint-ssh.sh） | 保留 ours（我們的版本） |
| 官方有新功能 | 評估是否需要 blend |
| 只是風格/格式不同 | 保留 ours |

### Step 6: 更新版本設定

檢查並更新 `.env` 或對應的版本檔案：

```bash
# 確認版本正確
cat .env | grep IMAGE
# 或
grep version pyproject.toml
```

### Step 7: Commit + Push

```bash
git add . && git commit -m "chore: upgrade to <new-version>"
git push -u origin <branch-name>
```

把 branch 推到 remote 作為備份記錄。

### Step 8: Trigger Build

```bash
# 確認 workflow 名稱
gh workflow list

# 觸發 build（視專案而定）
gh workflow run <workflow-name> -f tag_name=<new-version> --ref <branch-name>
```

或使用 API：
```bash
curl -s -X POST -H "Authorization: Bearer $(gh auth token)" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/<workflow-file>/dispatches \
  -d '{"ref":"<branch-name>","inputs":{"tag_name":"<new-version>"}}'
```

### Step 9: 測試

#### 9a: 本地測試 (Docker/Kind/K3s)

```bash
# 確認 image 版本
kubectl get deployment -n <namespace> -o yaml | grep image

# 看 logs
kubectl logs -n <namespace> -l app=<app-name> --tail=50
```

#### 9b: 遠端測試 (Zeabur/VPS/Cloud)

部署到測試環境，確認功能正常。

### Step 10: SSH 測試（如有）

如果專案有 SSH 功能：

```bash
ssh -p <port> user@hostname
```

可能需要清除舊的 host key：
```bash
ssh-keygen -R "[hostname]:<port>"
```

## 常見問題

### Q: 如何決定用 rebase 還是 cherry-pick？

| 衝突數 | 建議方式 |
|--------|----------|
| 0-10 個 | rebase |
| 超過 10 個 | cherry-pick |

### Q: 如果測試失敗怎麼辦？

```bash
# 回到舊版 (K8s)
kubectl rollout undo deployment/<name> -n <namespace>

# 或者手動 pull 舊版 image
docker pull <registry>/<image>:<old-version>
```

### Q: 忘記 branch 名字怎麼辦？

```bash
git branch -a | grep "my-config\|config"
```

## Branch 命名規則

```
<project>-config-<version>   →  每次升級都留一個

例如：
my-config-v2026.5.29.2       →  Hermes v2026.5.29.2
my-config-v2026.5.16           →  Hermes v2026.5.16
openclaw-config-v2026.6.1      →  OpenClaw v2026.6.1
```

## 重要原則

| 原則 | 原因 |
|------|------|
| 每次升級前建立新 branch | 萬一失敗可 rollback |
| 每次 commit + push | 有記錄才能重建 |
| 先本地測試再上線 | 避免影響正式環境 |
| 衝突太多就換 cherry-pick | 不要堅持 rebase 而耗費大量時間 |

## 版本控制流程圖

```
Fetch 官方
     ↓
建立新 branch
     ↓
帶入 Custom Commits (rebase 或 cherry-pick)
     ↓
Commit + Push
     ↓
Trigger Build
     ↓
本地測試 → 失敗？→ 回到舊 branch
     ↓
遠端測試 → 失敗？→ 回到舊 branch
     ↓
完成！
```