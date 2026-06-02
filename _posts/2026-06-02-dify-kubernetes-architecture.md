---
title: "Dify on Kubernetes — 架構、運作與操作手冊"
date: 2026-06-02 10:00:00 +0800
categories:
  - Dify
  - Architecture
tags:
  - dify
  - k8s
  - architecture
  - homelab
---

> 範圍：只涵蓋本 repo 的 `dify/` 部署（dify-bundle.yaml + nginx-proxy configmap + 此文件）。
> 對外入口：`https://dify.3pm.lol`（Cloudflare Tunnel → dify-nginx-proxy）。
> 完整 manifest：`dify/dify-bundle.yaml`。

---

## 1. 為什麼自己架 Dify

Dify 是開源 LLM App 平台（聊天機器人、RAG 知識庫、Agent workflow 都用它編）。
雲端版有免費額度，但自架的好處：
- 資料不出 home lab（文件、對話紀錄、API key 都在自己 Mac 上）
- 客製化（plugin、模型供應商、儲存路徑）
- 跟 n8n 串接方便（之後做 workflow）

---

## 2. 元件總覽

部署了 8 個 Pod，全部在 `dify` namespace：

| 元件 | 角色 | 技術 | 備註 |
|------|------|------|------|
| **dify-db** | 主資料庫 | PostgreSQL 15 + pgvector | 存 app、conversation、message、tenant key、文件區塊 embedding |
| **dify-redis** | 快取 + pub/sub | Redis 7 | SSE 串流通道、session、LLM response cache、Celery broker |
| **dify-broker** | 訊息佇列 | RabbitMQ | 給 worker 排非同步任務（建議問題、文件索引、webhook） |
| **dify-api** | 主要 API 服務 | Python / Flask + gunicorn | 處理所有 HTTP 請求、跟 LLM 對接 |
| **dify-worker** | 背景任務 worker | 跟 api 同 image，跑 `MODE=worker` | 從 broker 拉任務執行（長任務、批次） |
| **dify-web** | 前端 | Next.js (Node) | UI，build 完用 nginx 服務靜態檔 |
| **dify-nginx-proxy** | 反向代理 | nginx | 把 `/console/api/ /api/ /v1/ /` 路由到正確後端（**ClusterIP**，Cloudflare Tunnel 透過 in-cluster DNS 連入）|
| **dify-plugin-daemon** | Plugin runtime | **Go**（其他都是 Python） | 安裝/隔離/執行 plugin，呼叫外部 LLM API |

> 📌 **特別注意**：`dify-api` 和 `dify-worker` 共用 `langgenius/dify-api:latest` 同一個 image，
> 只是 entrypoint 跑不同：`MODE=api` 起 Flask，`MODE=worker` 起 Celery worker。
> 好處是 deploy/升級一次到位，schema 完全一致。

---

## 3. 網路拓樸

```
   你的瀏覽器
       │ HTTPS (dify.3pm.lol)
       ▼
   Cloudflare Tunnel (gateway namespace)
       │ HTTP
       ▼
┌────────────────────────────┐
│  dify-nginx-proxy :80      │  ← K8s service (ClusterIP，非 LoadBalancer)
└────────────────────────────┘
       │
   ┌───┴────┬──────────┬─────────────┐
   ▼        ▼          ▼             ▼
 /         /api/  /console/api/    /v1/
   │        │          │             │
   ▼        ▼          └─────┐       │
dify-web   dify-api ◄────────┘       │
   │           │                    │
   │           ├──► dify-db ─► pgvector (vector search)
   │           ├──► dify-redis (cache + SSE pub/sub)
   │           ├──► dify-broker ─► dify-worker
   │           └──► dify-plugin-daemon ─► MiniMax API
   │
   └─ 直接 build 好的靜態檔（不需要再跟 api 對話時）
```

---

## 3.5 (新手補充) 反向代理的各種選擇：Tunnel、LoadBalancer、nginx

> 之前跟其他 AI 討論時得到一個結論：「我們用了 Cloudflare Tunnel，
> 所以不需要 nginx / caddy 之類的反向代理」。這個結論對**單一元件**
> 服務（jellyfin、n8n）是對的，但對 Dify 這種**多元件 app 不對**——
> 我們確實需要內部 nginx。為什麼？而且 K8s 自己的 LoadBalancer 跟
> Ingress 也都是某種 reverse proxy，三者差別在哪？

### 三種（或四種）反向代理，差別是「用什麼當路由 key」

| 反向代理 | 跑在哪 | 路由鍵 | 角色 |
|---------|--------|--------|------|
| **Cloudflare Tunnel** | cluster 邊界（`gateway` namespace）+ Cloudflare edge | **hostname** | OS 層級：把 `dify.3pm.lol` 整個送進 cluster |
| **K8s LoadBalancer**（我們的 K3s 環境 = klipper-lb + iptables）| 每個 node 的 host port | **port** | OS 層級：同個 port 只能給一個 service |
| **dify-nginx-proxy** | Dify app 內部 | **URL path** | App 層級：把同一個 service 內 `/` 跟 `/api/` 拆給不同元件 |
| **K8s Ingress**（理論上，需要裝 Ingress Controller）| 獨立 controller pod | **hostname + path 雙重** | 可以取代 Tunnel + nginx 整個 stack——但我們沒裝 controller（見 § 5 那個被刪掉的 dead Ingress 就是證據）|

Cloudflare Tunnel 把外面請求送進 cluster 後就結束了，**它不會去管同一個
service 內 `/api/` 跟 `/` 該給誰**。這個工作必須在 cluster 內做——就是
nginx。

### Dify 為什麼必須要內部 nginx？

Dify 不是一個服務，是 **3 個獨立元件**組成的：

| 元件 | 角色 |
|------|------|
| `dify-web` (Next.js) | 瀏覽器 SPA 前端，純靜態檔 |
| `dify-api` (Flask) | 處理 `/console/api/`、`/api/`、`/v1/` 全部後端邏輯 |
| `dify-plugin-daemon` (Go) | plugin 沙箱（api 內部呼叫，不對瀏覽器）|

瀏覽器從 `https://dify.3pm.lol/` 進來，**同一個 hostname** 就要同時拿到：
- `/` → dify-web（前端 SPA）
- `/console/api/...` → dify-api（後台管理 API）
- `/api/...` → dify-api（app-level API）
- `/v1/...` → dify-api（公開 API）

這個「同一個 hostname，path 拆給不同 backend」就是 nginx 的工作。

### 走一條 request 看兩層怎麼接力

**範例 A**：打開 https://dify.3pm.lol/ 看首頁

```
瀏覽器 GET /
   ↓ TLS 終止（DDoS / WAF / IP 偽裝）
Cloudflare edge
   ↓ tunnel 私有通道
cloudflared pod
   ↓ 知道 dify.3pm.lol → service dify-nginx-proxy:80
kube-proxy (in-cluster DNS)
   ↓
dify-nginx-proxy 收到 GET /
   ↓ location / 匹配
   proxy_pass http://dify-web:80
   ↓
dify-web (Next.js) 回 index.html
```

**範例 B**：在 Chatbot 發訊息

```
瀏覽器 POST /console/api/apps/abc/chat-messages
   ↓ TLS 終止
Cloudflare edge
   ↓ tunnel
cloudflared pod
   ↓ 知道 dify.3pm.lol → service dify-nginx-proxy:80
kube-proxy
   ↓
dify-nginx-proxy 收到 POST /console/api/...
   ↓ location /console/api/ 匹配
   proxy_pass http://dify-api:8080/console/api/...
   ↓
dify-api (Flask) 處理
```

兩個範例，**前 4 層一模一樣**（瀏覽器 → Cloudflare → tunnel → nginx）。
分流從第 5 層（nginx）才開始。

### 為什麼不用 Cloudflare Tunnel 取代 nginx？

技術上 Cloudflare Tunnel 可以在 Zero Trust dashboard 設 path filter
做 path-routing。但我們不這樣做，理由：

1. **Dify 官方架構就是 nginx**——Docker Compose、Helm chart、Dify 源碼
   都假設有一個內部 nginx 做 path-routing。砍掉它就要改 Dify 的 entrypoint，
   之後升級 Dify 會變難維護
2. **設定會散落兩處**——hostname 規則在 Cloudflare dashboard，path 規則
   在 K8s 內部 ConfigMap。改 path 要動 dashboard；cluster reset 不會
   影響 dashboard（容易漏改）
3. **SSE 串流比較穩**——Dify 用 Server-Sent Events 串流回 token，
   nginx 對 SSE / chunked transfer 支援很成熟；Cloudflare Tunnel 對長
   連線偶爾有 edge case
4. **職責分離**——Cloudflare Tunnel 做「OS 層級」（host → service），
   nginx 做「app 層級」（path → backend）。每個做自己擅長的

### 那 K8s LoadBalancer 呢？我們的環境其實也不用

「Reverse proxy」這個詞在三個地方都有人用，容易混。**三者的差別是
「用什麼當路徑查找的 key」**：

| | Cloudflare Tunnel | K8s LoadBalancer（K3s 環境）| nginx（dify 內部）|
|---|---|---|---|
| **路由鍵** | 域名 (hostname) | **連接埠** (host port) | URL 路徑 (path) |
| **跑在哪** | cloudflared pod + Cloudflare edge | iptables 規則（klipper-lb 設的）| nginx process |
| **TLS 終止** | 有 | **沒有** | 沒有 |
| **DDoS 防護** | 有 | 沒有 | 沒有 |
| **能讓 100 個 service 共用 port 80？**| ✅（靠 hostname 區分）| ❌（port 80 全 cluster 只能有一個）| n/a |
| **能區分同 hostname 的不同 path？**| ✅（path filter）| ❌ | ✅ |

**K3s 的 LoadBalancer 在我們這個 OrbStack 環境**其實**不是真的 load balancer**——
它只是：

1. 你寫 `type: LoadBalancer`
2. K3s ServiceLB controller 自動生一個 `svclb-<svc>` DaemonSet
3. klipper-lb pod 起來時在 kernel iptables 設一條 **DNAT 規則**：
   ```
   -A PREROUTING -p tcp --dport 30594 -j DNAT --to-destination <dify-web-pod-ip>:3000
   ```
4. 設完規則 pod 就睡著了（甚至不算在做事）

**它根本不是 process 在做 proxy，是 iptables 規則**。沒有 hostname 認知、
沒有 health check、沒有 round-robin 邏輯——純粹是 kernel-level port 轉發。
「Load balancing」是 kube-proxy 自己在做，跟 klipper-lb 無關。

### 為什麼我們不用 K8s LoadBalancer？

如果 K8s LoadBalancer + Cloudflare Tunnel 同時用，會撞到 § 5 那個
**host port 80 衝突問題**——K8s LoadBalancer 不能區分 hostname，
100 個服務要搶 port 80，第一個搶到的贏，其他全部 Pending。
Cloudflare Tunnel 已經做了「hostname → service」這層路由，**K8s
LoadBalancer 是重複且會搶資源**，所以我們不開。

例外：dify-web / jellyfin-service / n8n-service 還是設成
`type: LoadBalancer`，但這不是 production 路徑——是** debug 後門**：

```bash
# Tunnel 掛了的時候，從 Mac 直接打 VM IP
curl http://192.168.139.2:30594/   # 直進 dify-web
curl http://192.168.139.2:30080/   # 直進 jellyfin
curl http://192.168.139.2:30948/   # 直進 n8n
```

這些高 port 是 K3s 自動配的（svclb 的 NodePort）。為了不撞 K3s 的
host port 80，這些 service 的 port 故意設成非 80 的數字（jellyfin 8096、
n8n 5678、hermes 2222）——所以 K3s 搶的是各自的 port，不是 80。

### 其他服務為什麼不需要內部 nginx？

| 服務 | 架構 | 要內部 nginx？ |
|------|------|---------------|
| `jellyfin` | Go monolithic（單一 process 處理所有路徑）| ❌ |
| `n8n` | Node monolithic | ❌ |
| `nextcloud` | PHP monolithic | ❌ |
| `immich` | 多元件 | **有**（它內建 reverse proxy）|
| `dify` | 3 元件 | **必須有**（用 nginx 做 path-routing）|

判斷原則：**app 是不是 monolithic**？是的話不需要內部 proxy；
multi-component 架構就需要。

### 進階：用 K8s Ingress 取代「Cloudflare Tunnel 多 hostname 規則 + 內部 nginx」

> 這是「如果未來服務很多、想單一 git repo 管所有 routing」的選項。
> 目前沒做，下面是設計稿。

#### 兩種「wildcard」差很多

| | 設定位置 | 影響 |
|---|---------|------|
| **DNS wildcard** `*.3pm.lol → tunnel` | Cloudflare DNS | 會把 `mail.3pm.lol` / `vpn.3pm.lol` / `jp.3pm.lol` 也導去 tunnel，外部服務全斷 |
| **Tunnel ingress catch-all** | cloudflared config | 只影響「已經走到 tunnel 的封包」。DNS 沒變的 hostname 不受影響 |

我們的 `3pm.lol` 底下其實有**兩類**服務：
- **自己管的**（K8s 內部）：`jelly`、`n8n`、`k8s`、`nextcloud`、`wp`、`photo`、`dify`
- **外部的**（DNS 各自指向外部）：`mail` (Oracle)、`vpn` (Cloudflare Worker)、`jp` (Zeabur)

**外部服務的 DNS 完全獨立**（mail → Oracle 公網 IP、vpn → Worker、jp → Zeabur），
根本不送進我們的 tunnel。所以 tunnel ingress 用 catch-all 也不會影響它們。

#### 提議的架構

```
mail.3pm.lol     → DNS → Oracle         ← 不碰 tunnel
vpn.3pm.lol      → DNS → Worker         ← 不碰 tunnel
jp.3pm.lol       → DNS → Zeabur         ← 不碰 tunnel

jelly.3pm.lol    → DNS → tunnel         ┐
n8n.3pm.lol      → DNS → tunnel         │
nextcloud.3pm.lol → DNS → tunnel        │  全部走同一個 tunnel
wp.3pm.lol       → DNS → tunnel         │  tunnel ingress 是 catch-all
photo.3pm.lol    → DNS → tunnel         │  ↓
dify.3pm.lol     → DNS → tunnel         ┘  Ingress Controller
                                            (Traefik) 看 Host header
                                            ↓
                                       各自 backend pod
```

Tunnel ingress（**不是 DNS wildcard**）：

```yaml
# 概念示意，實際上 Cloudflare 設在 dashboard 或 tunnel config
ingress:
  - service: http://traefik.kube-system.svc.cluster.local:80
    # 沒寫 hostname = catch-all
```

K8s Ingress（取代現在的 Service + dify-nginx-proxy）：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dify
  namespace: dify
spec:
  ingressClassName: traefik
  rules:
  - host: dify.3pm.lol
    http:
      paths:
      - path: /               # 前端 SPA
        pathType: Prefix
        backend:
          service: { name: dify-web, port: { number: 3000 } }
      - path: /console/api    # 後台
        pathType: Prefix
        backend:
          service: { name: dify-api, port: { number: 8080 } }
      - path: /api
        pathType: Prefix
        backend:
          service: { name: dify-api, port: { number: 8080 } }
      - path: /v1
        pathType: Prefix
        backend:
          service: { name: dify-api, port: { number: 8080 } }
```

#### 分階段 migrate（零風險）

| 階段 | 動作 | 風險 |
|------|------|------|
| Phase 0（現在）| 7 條 tunnel rule 各自指 service | 沒風險 |
| Phase 1 | 裝 Traefik，**新增** Ingress 物件但 tunnel 規則不動 | 沒風險（Ingress 沒被使用）|
| Phase 2 | 把 **1 個** 服務（建議先選最不重要的）改指 Traefik | 低風險（單一服務）|
| Phase 3 | 觀察幾天 OK，繼續換其他服務 | 漸進 |
| Phase 4 | 全部換完後，tunnel rule 精簡成 catch-all | 完成 |

**Dify 的特殊獎勵**：Phase 2 換 Dify 時，可以**順便拿掉 `dify-nginx-proxy`**——
Traefik 自己做 path-routing 取代 nginx，少一個元件。

#### 為什麼我們目前不做？

1. **沒迫切需求**——7 個服務 + 7 條 tunnel rule 還算單純
2. **要裝新元件**——Traefik / nginx-ingress-controller 是新東西要學要管
3. **一次切換風險**——Ingress Controller 預設 LoadBalancer 會搶 host port 80
   （雖然可以把 `dify-web` 改 ClusterIP 讓出來，但那要分階段做）

**什麼時候考慮做**：
- 服務數量到 10+ 個
- 想「只用 git 管所有 routing」，不想動 Cloudflare dashboard
- 想拿掉 dify-nginx-proxy

### 憑證：Cloudflare Tunnel 把整個問題解掉了

> 之前跟其他 AI 討論時還有個疑問：「如果自己架 reverse proxy，
> TLS 憑證怎麼辦？只知道 Caddy 會自動簽，其他不會。」——這裡把整個
> TLS 跟憑證的版圖講清楚。

#### 現況：TLS 只在前 2 層，cluster 內全部明文 HTTP

```
你的瀏覽器
   │  HTTPS (TLS 終止在 Cloudflare edge，Cloudflare 憑證)
   ▼
Cloudflare edge
   │  tunnel protocol (Cloudflare 私有加密通道)
   ▼
cloudflared pod        ← 在 cluster 內
   │  HTTP ⚠️ 從這裡開始全部明文
   ▼
dify-nginx-proxy
   │  HTTP
   ▼
dify-api / dify-web / dify-db / dify-redis
   (全部都 HTTP，K8s 內部元件之間也是 HTTP)
```

**我們 cluster 裡完全沒有任何 TLS 憑證**——0 個 Secret、0 個 cert-manager、
0 個 ACME。Cloudflare edge 處理了所有對外憑證。

**為什麼 cluster 內部可以用明文 HTTP？** ClusterIP 只能從 cluster 內的
pod 透過 kube-proxy 存取，外部網際網路碰不到。明文 OK 是因為**攻擊者
要先能進 cluster 才能看到流量**——而進 cluster 比繞過 Cloudflare 難太多。

#### 如果不要 Cloudflare Tunnel，自己架呢？

| 方案 | 憑證來源 | 自動續期？ | K8s 環境適用 |
|------|---------|-----------|-------------|
| **Cloudflare Tunnel**（現況）| Cloudflare 處理 | Cloudflare 處理 | ✅ 完全不用管 |
| **Caddy** | 內建 ACME，跟 Let's Encrypt 拿 | ✅ 自動 | ⚠️ 單機好用，K8s 較少人用 |
| **nginx** + certbot | 需手動接 Let's Encrypt | 半自動（要 cron）| ⚠️ 傳統做法，K8s 不太合 |
| **Traefik** | 內建 ACME | ✅ 自動 | ✅ K8s 標準選擇之一 |
| **K8s Ingress + cert-manager** | cert-manager 跟 Let's Encrypt 拿 | ✅ 自動 | ✅ **K8s 教科書做法** |

#### Caddy 為什麼特別？

Caddy 是**唯一**把 HTTPS 做成「預設行為」的 reverse proxy——你寫
`host example.com`，它會自動：
1. 偵測你沒憑證
2. 跟 Let's Encrypt 申請
3. 把 HTTPS 開起來
4. 過期前自動續

其他都要手動接 ACME client。但 Caddy 在 K8s 不主流——本來設計給單機用。

#### 我們 cluster 真要自己架，會撞到什麼？

1. **HTTP-01 challenge 不可行**——Let's Encrypt 要從 internet 訪問
   `http://<域名>/.well-known/acme-challenge/...`，但我們沒有對外 80
   （Cloudflare Tunnel 拿走了，LoadBalancer 配的也是高 port）
2. **必須用 DNS-01 challenge**——跟 Cloudflare API 拿 token，
   cert-manager 自動加 DNS TXT record 證明你擁有這個域名
3. **標準流程**：
   - 裝 cert-manager（K8s operator）
   - 給 cert-manager 一個 Cloudflare API token（只能改 DNS 的權限）
   - 創 ClusterIssuer 設定 DNS-01 用 Cloudflare plugin
   - 在 Ingress 加 `cert-manager.io/cluster-issuer: letsencrypt-prod` annotation
   - cert-manager 自動申請、自動 renew

**這在 K8s 是教科書做法**，可行，但**多一個元件**要管 + 一個 Cloudflare API token。

#### 為什麼我們目前不用煩這些？

| 我們要管的 | Cloudflare Tunnel 處理的 |
|-----------|-------------------------|
| Cloudflare tunnel 設定 | ✅ |
| 憑證過期時間 | ✅ Cloudflare 自動 |
| ACME challenge 機制 | ✅ Cloudflare 自動 |
| 憑證 renew | ✅ Cloudflare 自動 |
| K8s 內部元件之間的 TLS | ❌ 我們直接 HTTP，省事 |
| cert-manager / certbot | ❌ 不用裝 |

**結論**：在 homelab 規模 + Cloudflare Tunnel 架構下，**TLS 是零成本**的——
Cloudflare 處理外面，cluster 內部反正私有網路不需要加密。如果哪天要自架，
certs 是「多一個元件」的代價，不是技術上做不到。

---

## 4. 一次 chat 訊息的完整路徑

你打一句「你好」：

1. **瀏覽器** POST `https://dify.3pm.lol/console/api/apps/{id}/chat-messages`
2. **Cloudflare** 透過 tunnel 轉到 K8s → **dify-nginx-proxy** port 80
3. **nginx-proxy** 看到 `/console/api/` → 轉給 **dify-api:8080**（內部是 5001）
4. **dify-api**：
   - 從 cookie 認出你是 admin，查 `dify-db` 取 user/conversation/app config
   - 拿 conversation 的 `override_model_configs` 決定用哪個模型（MiniMax-m3）
   - 組 prompt → 呼叫 **dify-plugin-daemon** `POST /dispatch/llm/invoke`
5. **dify-plugin-daemon**：
   - 載入 MiniMax plugin（隔離環境）
   - 用你的 API key 打 MiniMax API
   - 串流 token 回傳給 dify-api
6. **dify-api**：
   - 邊收 token 邊 SSE 推回瀏覽器（透過 nginx-proxy）
   - 完整回應存進 `dify-db.messages.answer`
   - 順便 enqueue 一個「生成建議追問」任務到 **dify-broker**
7. **dify-worker**：
   - 從 broker 拉到任務
   - 再呼叫 plugin-daemon 一次生成建議問題
   - 結果寫回 db
8. 瀏覽器接著 GET `suggested-questions` → dify-api 從 db 撈出來顯示

---

## 5. 三個「為什麼」

- **為什麼要有 nginx-proxy？**
  Dify web 從瀏覽器發 `/console/api/*` 跟 `/api/*`，
  沒這層代理會撞 CORS / mixed-content。我們的 dify-web 服務是內部 ClusterIP，
  瀏覽器不會直接打到——所有 API 請求都透過 nginx-proxy 同源轉發。

- **為什麼 api 跟 worker 用同個 image？**
  同 codebase，只是 `MODE` 不同。這樣 deploy/升級一次到位，schema 完全一致。

- **為什麼 plugin-daemon 是 Go 不是 Python？**
  Plugin 是「裝進來跑使用者程式碼」的安全風險。
  Dify 用 Go 開 child process + seccomp 沙箱隔離 plugin，
  避免一個爛 plugin 把整個 API 容器拖下水。
  Python 端的 API 只負責 IPC。

- **為什麼 dify-nginx-proxy 是 ClusterIP 不是 LoadBalancer？**
  Cloudflare Tunnel 跑在同一個 cluster 內（`gateway` namespace），
  它透過 in-cluster DNS（`dify-nginx-proxy.dify.svc.cluster.local:80`）
  走 kube-proxy 連到 nginx-proxy，**完全不需要 host port**。
  設成 `LoadBalancer` 反而會觸發 K3s ServiceLB 試圖生 svclb pod 想 bind
  hostPort 80（K3s klipper-lb 的設計：host port 跟 service port 對齊，
  讓你可以用 `curl http://<node>:80` 直接打）。但**在我們這個 cluster
  裡，`dify-web` 已經是 `type: LoadBalancer` + port 80**，
  K3s 先幫它搶到了 host port 80（svclb-dify-web 1/1 Running）。
  第二個想要同樣組合的 Service 搶不到，svclb-dify-nginx-proxy
  就永遠 Pending。在單節點 K3s 上，所有 inbound 流量都靠
  Cloudflare Tunnel，**任何 Service 都應該是 ClusterIP**。
  對外 Hostname → Tunnel → ClusterIP 是這套架構的唯一路徑。

  **修正**：早期版本的文件曾誤以為 host port 80 是被 OrbStack 內部
  `hermes-agent` 佔的，實際上是 K3s 給 `dify-web` 配的，兩者完全不同。
  驗證方式：`kubectl get pods -A -o json` 找 `hostPort: 80` 的 pod 就是兇手。

---

## 5.5 (新手補充) K8s Service 對外開放的三個等級

> 這一節是給**第一次接觸 K8s networking**的人。看完你會懂為什麼
> `dify-nginx-proxy` 必須是 `ClusterIP`，以及那個 `svclb-dify-nginx-proxy`
> Pending 警告到底是怎麼回事。

### 公寓大樓比喻

把 K8s cluster 想像成一棟**公寓大樓**，每個 pod 是一個房間，Service 是房間的「分機號碼」。

| Service 類型 | 比喻 | 誰能打這個分機？ |
|--------------|------|-----------------|
| **ClusterIP**（預設） | 房間內分機 | **只有大樓內的住戶**（cluster 內的其他 pod） |
| **NodePort** | 大門門牌 (30000-32767 範圍) | 大樓外的路人，敲某個門牌號碼進來 |
| **LoadBalancer** | 雲端配公網 IP + 門牌 | 全世界（雲端會自動配 floating IP） |

不寫 `type:` 就是 ClusterIP（最安全）。K8s 看到你寫 `type: NodePort` 或
`type: LoadBalancer`，才會「開門」讓外面的人進來。

### 一張圖看流量怎麼走

```
   你的瀏覽器
       │
       │ HTTPS
       ▼
   Cloudflare edge
       │
       │ 走 tunnel 私有通道
       ▼
   ┌──────────────────────────────────────────────┐
   │  Cluster 內部（OrbStack Linux VM）          │
   │                                              │
   │  ┌────────────┐    打 "dify-api:8080"       │
   │  │ cloudflared│─────────────┐               │
   │  │   pod      │             │               │
   │  └─────┬──────┘             ▼               │
   │        │             ┌────────────┐         │
   │        │             │ dify-api   │         │
   │        │             │  pod       │         │
   │        ▼             └────────────┘         │
   │  ┌────────────┐                              │
   │  │ dify-nginx │── 房間內分機（ClusterIP）    │
   │  │ -proxy pod │                              │
   │  └────────────┘                              │
   │                                              │
   │  ─── Cluster 邊界 ───                        │
   │                                              │
   │  host port 80  ← 被 K3s 搶走了（給 dify-web）│
   │  (見下方「svclb 雞婆機制」解釋)              │
   └──────────────────────────────────────────────┘
```

重點：Cloudflare Tunnel 流量**完全不走** host port 80 這層，cluster 內
走 ClusterIP DNS 即可。但 host port 80 已經被 K3s 配給 `dify-web` 的
svclb 了，這就是 `dify-nginx-proxy` 改成 ClusterIP 的真正原因——
**不能再搶第二次**。

### 為什麼 K3s 會「雞婆」生 svclb pod？

K3s（K8s 的輕量發行版）有個「貼心」設計：你寫 `type: LoadBalancer`，
它會自動生一個 DaemonSet `svclb-<service-name>-<hash>`，裡面的 pod 用
`klipper-lb` image（超小，~1MB），角色是**當 iptables 轉發器**。

K3s klipper-lb 的設計：**host port 跟 service port 對齊**——你想要
`curl http://<node-ip>:80/` 直接打，就要讓 klipper-lb 監聽 host port 80。
所以 K3s 會試圖把每個 LoadBalancer Service 的 service port 也綁到 host。

```
   VM host port 80
        │  (K3s 想搶這個，因為 dify-nginx-proxy service port 是 80)
        ▼
   ┌──────────────────┐
   │ svclb-dify-      │  ← klipper-lb pod（搶不到，永遠 Pending）
   │   nginx-proxy    │
   └──────────────────┘
```

**為什麼搶不到**：host port 是 VM 層的 port，全 VM 只有 1 份。先建立的
Service 搶到，後面的就 Pending。在我們這個 cluster：

| Service | service port | K3s 想搶的 host port | 結果 |
|---------|-------------|---------------------|------|
| `dify-web` | 80 | **80** | ✅ 搶到（先到，1/1 Running）|
| `dify-nginx-proxy` | 80 | **80** | ❌ 搶不到（Pending）|
| `jellyfin-service` | 8096 | 8096 | ✅ 沒人搶，1/1 Running |
| `n8n-service` | 5678 | 5678 | ✅ 沒人搶，1/1 Running |
| `hermes-agent` | 2222 | 2222 | ✅ 沒人搶，1/1 Running |

> **常見誤解**：host port 80 是被 OrbStack 內部 `hermes-agent` 佔的。
> 錯。`hermes-agent` 用的是 service port 2222，NodePort 31862，跟 80
> 完全無關。真正的兇手是 K3s 自己給 `dify-web` 配的 klipper-lb pod。
> 驗證：
> ```bash
> kubectl get pods -A -o json | python3 -c "
> import json, sys
> for p in json.load(sys.stdin)['items']:
>   for c in p['spec'].get('containers', []):
>     for port in c.get('ports', []):
>       if port.get('hostPort') == 80:
>         print(p['metadata']['namespace'], p['metadata']['name'])
> "
> # 輸出：kube-system svclb-dify-web-84f17f11-qk8lt
> ```

### 跟我們這個 cluster 的對照

跑一下這個指令看看：

```bash
kubectl get svc -A | grep -E "dify|jellyfin|n8n"
```

你會看到：

| Service | type | 為什麼這樣設 |
|---------|------|------------|
| `dify-nginx-proxy` | **ClusterIP** | ✅ 正確。Cloudflare Tunnel 走 in-cluster DNS 連它 |
| `dify-api` / `dify-db` / `dify-redis` / `dify-broker` / `dify-plugin-daemon` | ClusterIP | ✅ 正確。內部元件，不該對外 |
| `dify-web` | **LoadBalancer** | ⚠️ 雞婆。沒人真的從外面打它（Cloudflare Tunnel 已經接管 80），是 K3s 自動配了 NodePort 30594 給 svclb-dify-web 當 debug 後門 |
| `jellyfin-service` / `n8n-service` | LoadBalancer | ⚠️ 同上，純粹是 debug 入口（`curl http://192.168.139.2:30080/` 直進 jellyfin） |

### 動手試試：證明 ClusterIP 從 cluster 內可達、從 cluster 外不可達

```bash
# 從 cluster 內（透過 kubectl exec 進去）打 ClusterIP
kubectl exec -n dify $(kubectl get pod -n dify -l app=dify-api \
  -o jsonpath='{.items[0].metadata.name}') -- \
  curl -sS -o /dev/null -w "%{http_code}\n" http://dify-nginx-proxy/

# 預期：307（轉址到登入頁）

# 從 Mac 端（cluster 外）打 ClusterIP
curl http://192.168.194.184/   # dify-nginx-proxy 的 ClusterIP
# 預期：連線 timeout 或 refused（從 Mac 看不到 cluster 內部 IP）
```

### 三個類型怎麼選？（決策表）

| 場景 | 用什麼 |
|------|--------|
| 只有 cluster 內其他 pod 需要打 | **ClusterIP**（預設） |
| 資料庫 / 快取 / 訊息佇列 | **ClusterIP**（永遠不要對外） |
| 對外服務，有 Cloudflare Tunnel 罩著 | **ClusterIP**（Tunnel 走 in-cluster DNS） |
| 對外服務，沒 Tunnel，要直接打 VM port debug | **LoadBalancer**（接受 K3s 隨機配的 NodePort） |
| 在 AWS / GCP 上有真的 Load Balancer | **LoadBalancer**（雲端會自動配 floating IP） |

**結論**：在 OrbStack 單節點 + Cloudflare Tunnel 架構下，**100% 的 Service
都應該是 ClusterIP**。我們留 `dify-web` / `jellyfin-service` / `n8n-service`
是 LoadBalancer 是「debug 後門」（用 `192.168.139.2:<NodePort>` 直進），
不是 production 路徑。

---

## 6. 資料流向一覽

```
              ┌─ pgvector: vector similarity search
              │
dify-db ◄─────┤  tables: apps, conversations, messages,
              │          datasets, embeddings, tenants, api_tokens
              │  files:  RSA private keys (/app/api/storage/privkeys/)
              │
dify-redis ◄──┤  pub/sub: SSE stream fan-out
              │  cache:   tenant_privkey, model credentials
              │  queue:   Celery broker(worker alternative)
              │
dify-broker ◄─┤  queue:   workflow runs, async tasks
              │           (suggested-questions, document indexing)
              │
dify-plugin-daemon ◄─ storage: plugin files, signatures
              │  cluster: master election (用 Redis)
              │
              └─ outbound: MiniMax / OpenAI / Anthropic APIs
```

---

## 7. Storage 路徑一覽（hostPath）

全部在 Mac 本機的 `~/dify-data/` 下，未來遷移直接 tar 帶走：

| 用法 | hostPath | 對應容器路徑 |
|------|----------|-------------|
| Postgres 資料 | `~/dify-data/db` | `/var/lib/postgresql/data` |
| Redis 資料 | `~/dify-data/redis` | `/data` |
| Dify API storage（**RSA private key 在這**） | `~/dify-data/api-storage` | `/app/api/storage` |
| Plugin daemon 檔案 | `~/dify-data/plugin-daemon` | `/app/storage` |

> ⚠️ `~/dify-data/api-storage/privkeys/<tenant_id>/private.pem` 是解密的私鑰，
> 沒這檔案 = tenant 任何 API 操作都 500。**備份時這個目錄是關鍵**。

---

## 8. 環境變數關鍵設定

`dify-api` 必設（沒設會 runtime 炸）：

- `VECTOR_STORE=pgvector` — 沒設的話 `/console/api/datasets/retrieval-setting` 直接 500
- `PLUGIN_DAEMON_URL=http://dify-plugin-daemon:5002`
- `PLUGIN_DAEMON_KEY=dify-plugin-daemon-key` — 跟 daemon 的 `SERVER_KEY` 對齊
- `SECRET_KEY=...` — 改自己的，否則 token 不安全
- `DB_HOST/PORT/USERNAME/PASSWORD/DATABASE` — 指向 `dify-db`
- `REDIS_HOST/PORT/PASSWORD` — 指向 `dify-redis`
- `CONSOLE_WEB_URL=https://dify.3pm.lol`
- `APP_WEB_URL=https://dify.3pm.lol`

`dify-plugin-daemon` 必設（每個都是踩過坑的）：

- `DB_HOST` (**不是** `DB_HOSTNAME`，會 silently 拒絕)
- `SERVER_KEY` (**不是** `PLUGIN_DAEMON_KEY`)
- `PLUGIN_DAEMON_TCP_HOST=0.0.0.0`
- `PLUGIN_DAEMON_TCP_PORT=5003`
- `PLUGIN_REMOTE_INSTALLING_HOST=0.0.0.0`
- `PLUGIN_REMOTE_INSTALLING_PORT=5003`
- `PLUGIN_WORKING_PATH=/app/storage/plugins`
- `PLUGIN_PACKAGE_PATH=/app/storage/packages`
- `PLUGIN_MEDIA_PATH=/app/storage/media`
- `DIFY_INNER_API_URL=http://dify-api:8080`
- `DIFY_INNER_API_KEY` / `DIFY_INNER_API_KEY_FOR_PLUGIN` — 跟 api 那邊對齊

---

## 9. 第一次使用流程

### 9.1 安裝模型供應商

1. 右上 **Settings → Model Provider**
2. 找 provider → 點 **Install**（plugin 模式）
3. 安裝完後同一頁填 API key
4. MiniMax 走 OpenAI 相容協議，plugin 會自動讀

### 9.2 建第一個 Chatbot

1. 頂部 **Studio** → 右上 **Create from Blank**
2. 選 **Chatbot** → 命名 → **Create**
3. 上方 **Orchestrate** 頁面 → 找 **Inference Model** 下拉 → 選 MiniMax 模型
4. 點 **Publish** 發布
5. 切回右側 **Debug / Preview** 就能打字聊了
6. 想正式對外：右上 **API Access** 看 endpoint，或 Cloudflare tunnel 開個子網域

### 9.3 建知識庫（RAG）

1. 頂部 **Knowledge** → **Create Knowledge**
2. 選資料來源（檔案 / Notion / 網頁爬蟲）
3. Embedding model 會用 tenant default（`tenant_default_models` 表格存）
4. 索引建好後在 Chatbot 的 context 區掛上 → 就有 RAG

---

## 10. 日常運維

### 10.1 怎麼看 log

```bash
# API 服務
kubectl logs -n dify -l app=dify-api --tail=100 -f

# Worker（看背景任務）
kubectl logs -n dify -l app=dify-worker --tail=100 -f

# Plugin daemon（看 plugin 載入 / LLM 呼叫）
kubectl logs -n dify -l app=dify-plugin-daemon --tail=100 -f

# 看所有 pod 狀態
kubectl get pods -n dify
```

### 10.2 怎麼重啟 / 更新

```bash
# 套用整包
kubectl apply -f dify/dify-bundle.yaml

# 只想重啟某個服務
kubectl rollout restart deployment/dify-api -n dify
kubectl rollout restart deployment/dify-worker -n dify
kubectl rollout restart deployment/dify-plugin-daemon -n dify
```

### 10.3 怎麼看 DB 內容

```bash
DB_POD=$(kubectl get pod -n dify -l app=dify-db -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n dify $DB_POD -- psql -U dify -d dify

# 常用查詢
\dt                                          # 列出所有表
SELECT * FROM apps;                          # 列出所有 app
SELECT id, query, answer FROM messages 
  ORDER BY created_at DESC LIMIT 5;          # 最近的對話
SELECT * FROM tenant_default_models;         # 預設模型設定
```

### 10.4 怎麼看 redis / rabbitmq 內容

```bash
REDIS_POD=$(kubectl get pod -n dify -l app=dify-redis -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n dify $REDIS_POD -- redis-cli
> KEYS tenant_privkey:*        # 看私鑰快取
> FLUSHDB                       # 清快取（解 schema 變更的 stale 問題）

BROKER_POD=$(kubectl get pod -n dify -l app=dify-broker -o jsonpath='{.items[0].metadata.name}')
# RabbitMQ 管理介面在 :15672，預設 guest/guest（容器內部網路限定）
```

### 10.5 升級 Dify 版本

1. 備份 `~/dify-data/db` 和 `~/dify-data/api-storage`（私鑰！）
2. 改 `dify-bundle.yaml` 裡的 image tag（`langgenius/dify-api:latest` → `:1.x.y`）
3. `kubectl apply -f dify/dify-bundle.yaml`
4. 看 `kubectl get pods -n dify` 全綠
5. **第一次升級前先看 release notes**——Dify 1.14 加了 `annotation_reply`、`more_like_this`、`agent_mode.prompt` 三個 schema 必填欄位，舊 conversation 沒這些會 500（見第 11 節）

---

## 11. 踩過的坑（疑難排解）

### 11.1 「failed to request plugin daemon」每秒跳

**原因**：`dify-plugin-daemon` 沒部署。
**修法**：套 `dify-bundle.yaml` 裡的 plugin-daemon section，api/worker 加 `PLUGIN_DAEMON_URL`。
**為什麼 `:latest` 失敗**：該 image 沒 `:latest` tag，要用 `:main-local`。

### 11.2 「Vector store type is not configured」

**原因**：`VECTOR_STORE` env 沒設，或 Postgres 沒裝 pgvector extension。
**修法**：
- api/worker 加 `VECTOR_STORE=pgvector`
- Postgres image 改 `pgvector/pgvector:0.8.2-pg15`（不是 `postgres:15-alpine`）

### 11.3 「InternalServerError」+ 右上角瘋狂轉圈

**原因 1**：tenant 沒 RSA 私鑰（手動建 admin 帳號繞過安裝精靈時會這樣）。
**修法**：
```bash
API_POD=$(kubectl get pod -n dify -l app=dify-api -o jsonpath='{.items[0].metadata.name}')
DB_POD=$(kubectl get pod -n dify -l app=dify-db -o jsonpath='{.items[0].metadata.name}')
TENANT_ID="<你的 tenant uuid>"

# 1) 生成 keypair
kubectl exec -n dify $API_POD -- python <<EOF
from Crypto.PublicKey import RSA
import os
priv = RSA.generate(2048); pub = priv.publickey()
target = f'/app/api/storage/privkeys/$TENANT_ID'
os.makedirs(target, exist_ok=True)
with open(f'{target}/private.pem','wb') as f: f.write(priv.export_key())
with open('/tmp/new_pub.pem','w') as f: f.write(pub.export_key().decode())
EOF

# 2) 寫回 DB
kubectl cp dify/$API_POD:/tmp/new_pub.pem /tmp/new_pub.pem
kubectl cp /tmp/new_pub.pem dify/$DB_POD:/tmp/new_pub.pem
kubectl exec -n dify $DB_POD -- psql -U dify -d dify -c \
  "UPDATE tenants SET encrypt_public_key = pg_read_file('/tmp/new_pub.pem') WHERE id = '$TENANT_ID';"

# 3) 清 redis 負快取
kubectl exec -n dify dify-redis-774df44f56-ps8gg -- redis-cli FLUSHDB
```

**原因 2**：`/app/api/storage` 沒掛 hostPath，pod 重啟私鑰就丟。
**修法**：bundle 已修，永久化到 `~/dify-data/api-storage`。

**原因 3**（升級 Dify 1.14 後）：conversation 的 `override_model_configs` 缺三個 schema 必填欄位。
**修法**：
```bash
DB_POD=$(kubectl get pod -n dify -l app=dify-db -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n dify $DB_POD -- psql -U dify -d dify -c "
UPDATE conversations SET override_model_configs = jsonb_set(
  jsonb_set(
    jsonb_set(
      override_model_configs::jsonb,
      '{annotation_reply}', '{\"enabled\": false}'::jsonb, true),
    '{more_like_this}',   '{\"enabled\": false}'::jsonb, true),
  '{agent_mode,prompt}', '\"\"'::jsonb, true)
::text
WHERE override_model_configs IS NOT NULL
  AND (override_model_configs::jsonb ? 'annotation_reply' = false
    OR override_model_configs::jsonb ? 'more_like_this' = false
    OR override_model_configs::jsonb->'agent_mode' ? 'prompt' = false);
"
```

### 11.4 「混合內容 / Mixed Content」

**原因**：瀏覽器 HTTPS 頁面呼叫 HTTP API。
**修法**：套 `dify-nginx-proxy`，所有路徑都從同源出去。

### 11.5 plugin-daemon 一直 CrashLoopBackOff

常見原因 & 對應 env 修法：
- `ServerKey required` → 設 `SERVER_KEY`（不是 `PLUGIN_DAEMON_KEY`）
- `DBHost required` → 設 `DB_HOST`（不是 `DB_HOSTNAME`）
- `plugin remote installing host is empty` → 設 `PLUGIN_REMOTE_INSTALLING_HOST=0.0.0.0`
- `plugin working path is empty` → 設 `PLUGIN_WORKING_PATH=/app/storage/plugins`
- bind 不到 `dify-plugin-daemon:5002` → 改成 `0.0.0.0`，k8s service DNS 沒辦法 bind

---

## 12. 容量 / 擴展規劃

- **dify-api**：可以水平擴（多 replica），純 stateless
- **dify-worker**：可以水平擴，從 broker 搶任務
- **dify-plugin-daemon**：stateless，但要做 master election（單機 OK，多節點要小心）
- **dify-db / redis / broker**：單機夠用就好，要 HA 的話換成 managed 服務

預估資源（單節點 OrbStack Mac）：
- dify-api: 1 vCPU, 1GB RAM
- dify-worker: 0.5 vCPU, 512MB
- dify-plugin-daemon: 0.5 vCPU, 512MB
- dify-db: 0.5 vCPU, 1GB RAM（隨資料量成長）
- dify-redis: 0.2 vCPU, 256MB
- dify-broker: 0.2 vCPU, 256MB
- dify-web: 0.2 vCPU, 256MB
- dify-nginx-proxy: 0.1 vCPU, 64MB