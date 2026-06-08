---
layout: post
title: "caddy ingress migration 2026"
date: 2026-06-08 00:00:00 +0800
categories: [General]
tags: []
---

# 🚀 Kubernetes 網關革命：從 Cloudflare Tunnel 直連遷移至 Caddy Ingress + cert-manager 實戰

本指南詳細記錄了將 Kubernetes 叢集中的服務從 **Cloudflare Tunnel 直連模式**，安全無痛遷移至 **Caddy Ingress Controller + cert-manager (DNS-01 挑戰驗證)** 萬用字元網關的完整實戰過程。

這套架構實現了：
* **本地隨插即用**：新增服務時，完全不需修改 Cloudflare Tunnel 設定，也不需手動新增 DNS。
* **SSL 終止本地化**：透過 Let's Encrypt DNS-01 挑戰，自動核發與續期本地 `*.3pm.lol` 萬用字元證書。
* **安全隔離**：API 控制面（`k8s.3pm.lol`）直連，其餘 Web 服務統一由 Caddy 安全反代。

---

## 📐 架構示意圖 (Architecture)

```mermaid
graph TD
    subgraph "網際網路 (Internet)"
        User["使用者瀏覽器<br/>(wp.3pm.lol / jelly.3pm.lol)"]
        Kubenav["kubenav App<br/>(k8s.3pm.lol)"]
    end

    subgraph "Cloudflare Edge (安全防護網)"
        CFDNS["Cloudflare DNS<br/>(*.3pm.lol CNAME 指向 Tunnel)"]
        CFTunnel["Cloudflare Tunnel<br/>(分流路由)"]
    end

    subgraph "Kubernetes 叢集 (本地端)"
        cloudflared["cloudflared (Tunnel Agent)"]
        Caddy["Caddy Ingress Controller<br/>(解密 TLS / 執行反向代理)"]
        APIServer["Kubernetes API Server<br/>(API 控制中心)"]
        
        WordPress["WordPress Pod"]
        Jellyfin["Jellyfin Pod"]
    end

    User --> CFDNS
    CFDNS --> CFTunnel
    Kubenav --> CFTunnel
    CFTunnel -->|Secure Pipe| cloudflared

    %% 控制面直連
    cloudflared -->|1. k8s.3pm.lol 直連 (Passthrough)| APIServer

    %% Web 流量分流至 Caddy
    cloudflared -->|2. *.3pm.lol 轉發| Caddy
    
    %% Caddy 路由
    Caddy -->|wp.3pm.lol| WordPress
    Caddy -->|jelly.3pm.lol| Jellyfin
```

---

## 🛠️ 事前準備 (Prerequisites)

1. **Cloudflare API Token 申請**：
   * 前往 **My Profile > API Tokens > Create Token > Create Custom Token**：
     * **Permissions**:
       * `Account` → `Cloudflare Tunnel` → `Edit`
       * `Zone` → `DNS` → `Edit`
       * `Zone` → `Zone` → `Read`
     * **Zone Resources**: 選擇特定的主網域（如 `3pm.lol`）。
2. **本地金鑰存放**：
   * 將 Token 與 Account ID 寫入 K8s 節點的環境變數檔（例如 `.secrets.env`）。

---

## 🏁 步驟一：安裝 `cert-manager`

`cert-manager` 負責在本地向 Let's Encrypt 自動申請並續期憑證。

1. **使用 Helm 安裝**：
   ```bash
   helm repo add jetstack https://charts.jetstack.io
   helm repo update
   helm install cert-manager jetstack/cert-manager \
     --namespace cert-manager \
     --create-namespace \
     --set crds.enabled=true
   ```

2. **💡 本地 DNS 自檢修復（Homelab 常見坑）**：
   在內網（OrbStack）環境中，`cert-manager` 在挑戰 DNS-01 時會因為本地 DNS 無法解析 SOA 紀錄而卡在 `Pending`。
   **解決方法**：修改 `cert-manager` 部署，強制其使用公網 DNS 進行自我檢測：
   ```bash
   kubectl patch deployment cert-manager -n cert-manager --type='json' -p='[
     {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--dns01-recursive-nameservers=1.1.1.1:53,8.8.8.8:53"},
     {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--dns01-recursive-nameservers-only=true"}
   ]'
   ```

---

## 🏁 步驟二：配置 Let's Encrypt 簽發器 (Issuer)

1. **將 Cloudflare Token 存入 K8s Secret**：
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: cloudflare-api-token-secret
     namespace: cert-manager
   type: Opaque
   stringData:
     api-token: <您的 Cloudflare API Token>
   ```

2. **建立全域憑證簽發器 (`ClusterIssuer`)**：
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-prod
   spec:
     acme:
       server: https://acme-v02.api.letsencrypt.org/directory
       email: <您的 Email>
       privateKeySecretRef:
         name: letsencrypt-prod-account-key
       solvers:
       - dns01:
           cloudflare:
             email: <您的 Email>
             apiTokenSecretRef:
               name: cloudflare-api-token-secret
               key: api-token
   ```

---

## 🏁 步驟三：申請並同步 `*.3pm.lol` 萬用字元憑證

1. **建立 `Certificate` 資源**：
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: Certificate
   metadata:
     name: wildcard-3pm-lol
     namespace: gateway
   spec:
     secretName: wildcard-3pm-lol-tls
     issuerRef:
       name: letsencrypt-prod
       kind: ClusterIssuer
     commonName: 3pm.lol
     dnsNames:
     - "3pm.lol"
     - "*.3pm.lol"
   ```
   *套用後，`cert-manager` 會在 Cloudflare 自動新增臨時 `TXT` 驗證記錄。通過後，會在 `gateway` 命名空間產生名為 `wildcard-3pm-lol-tls` 的 Secret。*

2. **💡 憑證跨 Namespace 共享的解決方案**：
   Kubernetes Ingress 限制憑證（Secret）必須與 Ingress 資源處於相同的命名空間。
   **做法**：將該 TLS Secret 複製到各個需要使用的服務命名空間中（如 `web-apps`, `jellyfin`, `nextcloud`）：
   ```bash
   kubectl get secret wildcard-3pm-lol-tls -n gateway -o yaml | sed 's/namespace: gateway/namespace: web-apps/' | kubectl apply -f -
   ```

---

## 🏁 步驟四：安裝 Caddy Ingress Controller

我們在 `gateway` 命名空間安裝 Caddy，做為資料平面的網關。

```bash
helm install caddy-ingress caddy/caddy-ingress-controller \
  --namespace gateway
```
*這會建立一個名為 `caddy-ingress-caddy-ingress-controller` 的 Service，監聽 `443` 連接埠。*

---

## 🏁 步驟五：為應用程式建立 Ingress 資源

以 WordPress 為例，建立 `ingressClassName: caddy` 的 Ingress，並關聯剛才複製過來的 TLS Secret。

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: wordpress-ingress
  namespace: web-apps
spec:
  ingressClassName: caddy
  tls:
  - hosts:
    - wp.3pm.lol
    secretName: wildcard-3pm-lol-tls
  rules:
  - host: wp.3pm.lol
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: wordpress-service
            port:
              number: 80
```
*套用後，Caddy 會自動掃描並載入憑證，將 `wp.3pm.lol` 的流量反代至 `wordpress-service:80`.*

---

## 🏁 步驟六：配置 Cloudflare Tunnel 萬用字元路由

利用 Cloudflare API，將原先的多個子域名直連條目全部移除，簡化為以下配置：

```json
{
  "config": {
    "ingress": [
      {
        "service": "https://kubernetes.default:443",
        "hostname": "k8s.3pm.lol",
        "originRequest": {
          "noTLSVerify": true
        }
      },
      {
        "service": "https://caddy-ingress-caddy-ingress-controller.gateway.svc.cluster.local:443",
        "hostname": "*.3pm.lol",
        "originRequest": {
          "noTLSVerify": true,
          "originServerName": "3pm.lol"
        }
      },
      {
        "service": "http_status:404"
      }
    ],
    "warp-routing": {
      "enabled": true
    }
  }
}
```
### 💡 關鍵設定說明：
* **`originServerName: "3pm.lol"`**：
  這是本架構的精髓。Cloudflare Tunnel 在發送 `*.3pm.lol` 流量到 Caddy 時，會強制將 SNI（Server Name Indication）設為 `3pm.lol`。
  Caddy 收到 `3pm.lol` 的 SNI 後，會取出 `wildcard-3pm-lol-tls` 憑證進行解密。解密成功後，再根據 HTTP Host Header 中的實際子網域（如 `wp.3pm.lol`）導向對應的 Pod。
  如果不加此設定，Caddy 會因為收到不認得的內部網域名稱 SNI 而回傳 `tls: internal error`。

---

## 🏁 步驟七：DNS 整合大掃除

在 Cloudflare DNS 管理介面中，我們不需要再為每一個服務新增獨立的 CNAME 記錄：

1. **刪除舊記錄**：將原有的 `wp`、`jelly`、`nextcloud`、`dify`、`n8n` 等獨立 CNAME 記錄全部刪除。
2. **新增萬用字元 CNAME**：
   * **名稱 (Name)**：`*`
   * **目標 (Target)**：`[您的Tunnel-ID].cfargotunnel.com`
   * **Proxy (橘色雲)**：`開啟 (Proxied)`
3. **保留控制面 CNAME**：
   * **名稱 (Name)**：`k8s`
   * **目標 (Target)**：`[您的Tunnel-ID].cfargotunnel.com`
   * **Proxy (橘色雲)**：`開啟 (Proxied)`

---

## 🎉 成果與未來維護流程

大功告成！現在您的 DNS 列表非常乾淨（只有 `*` 與 `k8s` 兩條 CNAME），並且服務的路由與加密完全由本地 Caddy Ingress 控制。

### 🔄 未來新增服務的流程（範例）：
當您在 K8s 中部署了一個新服務（如 `my-app`），想透過外網 `https://my-app.3pm.lol` 存取：
1. **Cloudflare DNS**：❌ 完全不用動。
2. **Cloudflare Tunnel**：❌ 完全不用動。
3. **K8s 內部**：🟢 寫一份簡單的 Ingress YAML，指定 `host: my-app.3pm.lol` 並 apply。
4. **結果**：服務立刻在全世界生效！
