---
layout: post
title: "traefik migration"
date: 2026-06-12 00:00:00 +0800
categories: [Concepts]
tags: []
---
# Caddy → Traefik 遷移紀錄

> **日期**：2026-06-12
> **原因**：Mac 系統升級重啟後，Caddy Ingress Controller 因 ACME HTTP-01 驗證在 Cloudflare Tunnel 架構下無法連線，導致外網訪問 `jelly.3pm.lol` 等服務全部回報 502 Bad Gateway。
> **結論**：移除 Caddy，改用 Traefik + cert-manager DNS-01 憑證，徹底將「憑證申請」與「流量轉發」解耦。

---

## 執行摘要

```
[Cloudflare Edge]
       ↓ (全程 HTTPS)
[cloudflared (Tunnel)]
       ↓ (HTTPS:443, noTLSVerify: true)
[Traefik Ingress (ClusterIP)] ➡️ 讀取 ➡️ [Secret: wildcard-3pm-lol-tls]
       ↓                                        ↑ (自動更新)
[應用 Pod (Jellyfin/WP/...)]            [cert-manager (DNS-01)]
                                              ↓
                                       [Cloudflare DNS API]
```

**Phase 執行順序**：移除 Caddy → 安裝 Traefik → 更新 Ingresses → 驗證和清理

---

## Phase 1: 移除 Caddy Ingress Controller ⚠️

### Step 1.1: 備份現有設定
```bash
# 備份 Caddy Helm values（以防萬一）
helm get values caddy-ingress -n gateway > gateway/caddy-ingress-values-backup.yaml

# 備份所有 Ingress 設定
kubectl get ingress -A -o yaml > gateway/ingresses-backup-$(date +%Y%m%d).yaml
```

### Step 1.2: 移除 Caddy Helm release
```bash
helm uninstall caddy-ingress -n gateway
# 確認移除完成
kubectl get pods -n gateway
# 應該只剩 cloudflared
```

### Step 1.3: 確認 Caddy resources 已移除
```bash
kubectl get all -n gateway | grep caddy
# 應該沒有 caddy 相關資源
```

---

## Phase 2: 安裝 Traefik

### Step 2.1: 安裝 Traefik CRDs
```bash
helm repo add traefik https://traefik.github.io/charts
helm repo update
helm show crds traefik/traefik | kubectl apply --server-side --force-conflicts -f -
```

### Step 2.2: 安裝 Traefik (gateway namespace)
```bash
helm install traefik traefik/traefik \
  --namespace gateway \
  --create-namespace
```

### Step 2.3: 確認 Traefik pod Ready
```bash
kubectl get pods -n gateway -w
# 等到 traefik-xxxxx pod 顯示 Running 1/1
# 按 Ctrl+C 退出
```

### Step 2.4: 確認 Traefik Service 已建立
```bash
kubectl get svc -n gateway
# 應該看到 traefik service (Port 80, 443)
```

---

## Phase 3: 更新 Ingresses

### Step 3.1: 更新 cloudflared config 指向 Traefik
```bash
kubectl edit configmap cloudflared-config -n gateway
```
修改 `*.3pm.lol` 的 service 為：
```json
"service": "https://traefik.gateway.svc.cluster.local:443"
```

> ⚠️ **重要**：必須用 `https://...:443`，不能用 `http://...:80`。錯誤設定會造成 WordPress 無限 redirect 迴圈（見下方根因分析）。

Cloudflare Tunnel 設定也要改為 `https://traefik.gateway.svc.cluster.local:443`。

### Step 3.2: 重啟 cloudflared
```bash
kubectl rollout restart deployment cloudflared -n gateway
kubectl get pods -n gateway -w
# 等 cloudflared 重啟完成後按 Ctrl+C
```

### Step 3.3: 測試單一 Ingress (jellyfin)
```bash
kubectl edit ingress jellyfin-ingress -n jellyfin
# 將 ingressClassName: caddy 改為 ingressClassName: traefik
```

### Step 3.4: 測試 jelly.3pm.lol
等待約 1-2 分鐘讓 DNS 傳播，然後測試：
```bash
curl -I https://jelly.3pm.lol
# 預期：HTTP 200 或 302 redirect
```

### Step 3.5: 全面更新所有 Ingress
如果 Step 3.4 成功，對以下每個 Ingress 執行 `kubectl edit` 並將 `ingressClassName: caddy` 改為 `ingressClassName: traefik`：

```
jellyfin namespace: jellyfin-ingress, sonarr-ingress, radarr-ingress, prowlarr-ingress, bazarr-ingress, qbittorrent-ingress
dify namespace: dify-ingress, dify-api-ingress
n8n namespace: n8n-ingress
nextcloud namespace: nextcloud-ingress
web-apps namespace: wordpress-ingress
immich namespace: immich-ingress
```

---

## Phase 4: 驗證和清理

### Step 4.1: 確認所有 site 正常
```bash
curl -sI https://jelly.3pm.lol | head -1
curl -sI https://wp.3pm.lol | head -1
curl -sI https://nextcloud.3pm.lol | head -1
curl -sI https://n8n.3pm.lol | head -1
curl -sI https://dify.3pm.lol | head -1
curl -sI https://photo.3pm.lol | head -1
curl -sI https://qb.3pm.lol | head -1
curl -sI https://radarr.3pm.lol | head -1
curl -sI https://sonarr.3pm.lol | head -1
curl -sI https://prowlarr.3pm.lol | head -1
curl -sI https://bazarr.3pm.lol | head -1
```

### Step 4.2: Git commit
```bash
git add -A && git commit -m "gateway: migrate from Caddy to Traefik ingress controller

- Remove Caddy ingress controller (ACME broken)
- Install Traefik via Helm
- Update all Ingress to use traefik ingressClassName
- Update cloudflared to route to Traefik service
- Continue using cert-manager wildcard-3pm-lol-tls certificate"
```

---

## 根因分析：WordPress 無限 redirect 迴圈

### 問題現象
WordPress `/wp-admin/` 和 `/wp-login.php` 出現 `ERR_TOO_MANY_REDIRECTS`。

### 根本原因：TLS 終止位置設定衝突

**錯誤設定（Flexible 模式）**：
```
Cloudflare Edge (TLS 終止)
    ↓ HTTP (明文)
cloudflared → Traefik (port 80)
    ↓
WordPress 收到 HTTP，但有 X-Forwarded-Proto: https header
    ↓
WordPress 困惑：收到 HTTP 但 header 說是 HTTPS
    ↓
WordPress 嘗試 redirect 到 HTTPS → 迴圈
```

**正確設定（Full 或 Full strict 模式）**：
```
Cloudflare Edge (不終止 TLS，全程加密)
    ↓ HTTPS
cloudflared → Traefik (port 443)
    ↓
Traefik 用 cert-manager wildcard-3pm-lol-tls 終止 TLS
    ↓ HTTPS
WordPress 收到乾淨的 HTTPS，無 header 衝突
```

### 正確 vs 錯誤設定組合

| 設定 | ✅ 正確值 | ❌ 錯誤值 |
|------|-----------|-----------|
| Cloudflare SSL/TLS 模式 | Full 或 Full (strict) | Flexible |
| Cloudflare Tunnel 目標 | `https://traefik.gateway.svc.cluster.local:443` | `http://traefik.gateway.svc.cluster.local:80` |
| cloudflared ConfigMap | `service: https://traefik.gateway.svc.cluster.local:443` | `service: http://...:80` |
| Traefik | port 443 用 cert-manager cert 終止 TLS | — |
| cloudflared originRequest | `noTLSVerify: true, originServerName: 3pm.lol` | — |

### WordPress 設定確認

確保以下設定一致（優先級從高到低）：

1. **wp-config.php**:
   ```php
   define('WP_HOME', 'https://wp.3pm.lol');
   define('WP_SITEURL', 'https://wp.3pm.lol');
   ```

2. **資料庫 wp_options**:
   ```
   home = https://wp.3pm.lol
   siteurl = https://wp.3pm.lol
   ```

3. **WORDPRESS_CONFIG_EXTRA** (環境變數):
   ```php
   define('WP_HOME', 'https://wp.3pm.lol');
   define('WP_SITEURL', 'https://wp.3pm.lol');
   ```

---

## 其他修正記錄

### dify-api-ingress Port 問題
- **問題**：Ingress 指向 port 5001，但 Service 實際是 8080
- **原因**：container targetPort 是 5001，但 Service port 是 8080
- **修正**：Ingress port 改為 8080

### Traefik Dashboard Basic Auth & svclb-traefik Pending
- **問題 1**：Dashboard 原先暴露於公網，缺乏 Basic Auth 防護
- **問題 2**：K3s 在 LoadBalancer 模式下產生的 `svclb-traefik` pod 因 Host Port (80/443/8080) 衝突而卡在 Pending
- **解決**：
  1. 修改 `traefik/values.yaml` 將服務類型改為 `ClusterIP`（Tunnel 直接解析 Service 域名，不需 LoadBalancer）
  2. 在 `gateway/traefik-dashboard.yaml` 手動定義 `Middleware` (Basic Auth) 與 `IngressRoute`（限 `websecure` 埠，帳號 `admin`）

---

## 驗證結果 (2026-06-12)

| Site | 狀態 | 備註 |
|------|------|------|
| jelly.3pm.lol | ✅ 302 | 正常 (jellyfin namespace) |
| qb.3pm.lol | ✅ 200 | 正常 (jellyfin namespace) |
| radarr.3pm.lol | ✅ 401 | 正常，需認證 (jellyfin namespace) |
| sonarr.3pm.lol | ✅ 401 | 正常，需認證 (jellyfin namespace) |
| prowlarr.3pm.lol | ✅ 401 | 正常，需認證 (jellyfin namespace) |
| bazarr.3pm.lol | ✅ 200 | 正常 (jellyfin namespace) |
| n8n.3pm.lol | ✅ 200 | 正常 (n8n namespace) |
| dify.3pm.lol | ✅ 307 | 正常，redirect to /apps (dify namespace) |
| dify-api.3pm.lol | ✅ 404 | 正常，API root 回 404 (dify namespace) |
| wp.3pm.lol | ✅ 200 | 正常 (web-apps namespace) |
| nextcloud.3pm.lol | ❌ 503 | nextcloud namespace 無 pods |
| photo.3pm.lol | ❌ 503 | immich namespace 無 pods |
| traefik.3pm.lol/dashboard/ | ✅ 401/200 | 正常，已啟用 Basic Auth 保護 (gateway namespace) |

---

## Traefik Dashboard

### 訪問方式
- **外部**：`https://traefik.3pm.lol/dashboard/`（注意結尾斜線 `/`）
- **臨時**：`kubectl port-forward -n gateway svc/traefik 9090:8080` → `http://localhost:9090/dashboard/`

### Dashboard IngressRoute 設定
詳見 [gateway/traefik-dashboard.yaml](file:///Users/mlee/kubernetes/gateway/traefik-dashboard.yaml)，包含 Basic Auth Middleware 與 IngressRoute 設定。

### Traefik Entrypoints

| Entrypoint | Port | 用途 |
|------------|------|------|
| METRICS | 9100 | Prometheus metrics |
| TRAEFIK | 8080 | Traefik API/Dashboard (內部) |
| WEB | 8000 | HTTP 流量入口 |
| WEBSECURE | 8443 | HTTPS 流量入口 |

### 常見問題
- **404 錯誤**：IngressRoute entryPoint 設錯了，Cloudflare → cloudflared → Traefik:443 → 必須用 `websecure`
- **Dashboard 唯讀**：只能看和監控，無法直接在畫面設定
- **Basic Auth 預設帳密**：`admin` / `123456`，在 `traefik-dashboard.yaml` 中配置

---

## 現有資源參考

### Tunnel Token
- Secret: `tunnel-token`（in gateway namespace），cloudflared 仍需使用，不需動

### cert-manager 資源（不需動）
- ClusterIssuer: `letsencrypt-prod`
- Certificate: `wildcard-3pm-lol-tls`（in gateway namespace, READY），有效期到 2026-09-06

### cloudflared ConfigMap
- Name: `cloudflared-config`（in gateway namespace）
- 需要修改：將 `*.3pm.lol` 的 service 指向 traefik

---

## 工作進度追蹤

| Phase | 狀態 | 完成時間 |
|-------|------|----------|
| Phase 1: 移除 Caddy | ✅ | 2026-06-12 10:00 |
| Phase 2: 安裝 Traefik | ✅ | 2026-06-12 10:02 |
| Phase 3: 更新 Ingresses | ✅ | 2026-06-12 10:25 |
| Phase 4: 驗證和清理 | ✅ | 2026-06-12 10:40 |
| Git commit | ✅ | 2026-06-12 10:45 |
| Dashboard Basic Auth & Service Type Fix | ✅ | 2026-06-12 16:12 |
