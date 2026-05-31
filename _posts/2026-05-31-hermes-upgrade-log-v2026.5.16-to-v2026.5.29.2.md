---
title: "Upgrade Log: v2026.5.16 → v2026.5.29.2"
date: 2026-05-31 11:00:00 +0800
categories:
  - Hermes
  - Upgrade
tags:
  - hermes
  - upgrade
  - changelog
  - zeabur
---

## Date: 2026-05-31

## Summary

成功升級 Hermes Agent 從 v2026.5.16 到 v2026.5.29.2（官方 v0.15.2）。

## Branch Structure

| Branch | Version | Status |
|--------|---------|--------|
| `my-config-v2026.5.16` | v2026.5.16 | 備份 branch |
| `my-config-v2026.5.29.2` | v2026.5.29.2 | 升級完成 |

## Official Changes (v0.15.0 - v0.15.2)

### v0.15.0 (2026-05-28) - Major Refactoring
- `run_agent.py` 從 16,083 行重構到 3,821 行（-76%）
- 拆成 14 個 `agent/*` 模組
- xAI Grok 支援（SuperGrok OAuth，grok-4.3 1M context）
- Kanban 有重大更新

### v0.15.1 (2026-05-29) - Hotfix
- 修復 Dashboard 無限重啟迴圈
- 修復 Kanban worker SIGTERM
- 統一 `/model` 選擇器
- 修復 `/yolo` session bypass

### v0.15.2 (2026-05-29) - Packaging Fix
- 修復 wheel/sdist 缺少的 plugin.yaml manifest

## Custom Commits Applied

| # | Commit | Description |
|---|--------|-------------|
| 1 | `c70f6b128` | integrate SSH into official s6-overlay architecture |
| 2 | `d497a69c9` | add entrypoint-ssh.sh for Zeabur compatibility |
| 3 | `ea40a0628` | handle non-PID 1 environment (Zeabur) |
| 4 | `aae3e3f8f` | use su-exec instead of main-wrapper.sh for Zeabur |
| 5 | `055bedfd6` | use su instead of su-exec for Zeabur |
| 6 | `939002121` | add .env with HERMES_IMAGE |
| 7 | `44edbb7e0` | add ghcr-publish workflow |
| 8 | `1342f3067` | restore docker-compose.yml |

## Key Technical Changes

### 1. Official Architecture (s6-overlay)

官方 v0.15.0 之後使用 s6-overlay 作為 PID 1：

```
/init (s6-overlay)
  → /etc/cont-init.d/01-hermes-setup (stage2-hook.sh)
  → supervised services (main-hermes, dashboard)
  → main-wrapper.sh
```

### 2. Zeabur Environment Issue

Zeabur 有自己的 PID 1（不是 s6-overlay），導致：

```
s6-overlay-suexec: fatal: can only run as pid 1
execlineb: fatal: unable to exec ifelse: No such file or directory
su-exec: not found
```

### 3. Solution for Zeabur

當 entrypoint-ssh.sh 不是 PID 1 時：

```bash
if [ $$ -eq 1 ]; then
    exec /init /opt/hermes/docker/main-wrapper.sh "$@"
else
    # Zeabur: skip s6-overlay, use su directly
    exec su -s /bin/sh hermes -c "exec /opt/hermes/.venv/bin/hermes $@"
fi
```

## Testing Results

| Environment | Status | Notes |
|-------------|--------|-------|
| Mac (OrbStack/K8s) | ✅ PASS | 使用 s6-overlay PID 1 |
| Zeabur | ✅ PASS | 使用 su 直接執行 |

## Lessons Learned

### 1. Branch per Upgrade
每次升級都建立新的 `my-config-v*` branch，確保可以 rollback。

### 2. Conflict Resolution
- 先嘗試 rebase，衝突少於 10 個時繼續
- 衝突太多時改用 cherry-pick
- 衝突時優先保留 ours（我們的 custom config）

### 3. Zeabur Environment
Zeabur 不是標準 K8s，有自己的 runtime wrapper。需確保 entrypoint-ssh.sh 可以處理 non-PID 1 情況。

### 4. CI/CD Trigger
`gh workflow run` 從 default branch 觸發，需用 API 指定 ref：
```bash
curl -X POST .../dispatches -d '{"ref":"my-config-v2026.5.29.2"}'
```

## Files Modified

- `Dockerfile` - 保留 SSH packages，NODE_OPTIONS
- `docker/entrypoint-ssh.sh` - Zeabur compatibility
- `docker/stage2-hook.sh` - SSH setup integrated
- `.env` - HERMES_IMAGE=v2026.5.29.2
- `.github/workflows/ghcr-publish.yml` - workflow file
- `docker-compose.yml` - restored from backup

## Next Upgrade SOP

1. `git fetch origin --tags`
2. `git checkout -b my-config-v<new-version> <official-tag>`
3. Cherry-pick custom commits (oldest first)
4. Test on Mac → Zeabur
5. Document in UPGRADE_LOG.md