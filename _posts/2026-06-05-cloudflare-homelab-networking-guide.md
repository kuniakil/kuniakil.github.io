---
layout: post
title: "Cloudflare Tunnel 與 Homelab 本地網路優化配置指南"
date: 2026-06-05 21:45:00 +0800
categories: [Network, Homelab]
tags: [cloudflare, vpn, warp, routing, split-tunnels]
---

這是一份針對 `3pm.lol` 網域及本地 `Jelly-Lab` 環境的網路規劃手冊，旨在解決開 WARP 後服務中斷、影音串流繞遠路，以及外部連線路由等 Homelab 常見問題。

---

## 🧭 導覽目錄
1. [Mac 啟動 WARP 導致網站中斷與解決方法（Split Tunnels）](#1-mac-啟動-warp-導致網站中斷與解決方法split-tunnels)
2. [影音串流（Jellyfin）本地免繞路優化](#2-影音串流jellyfin本地免繞路優化)
3. [SSH 本地直連與外部 WARP 私有網路連線](#3-ssh-本地直連與外部-warp-私有網路連線)
4. [萬用字元網域（*.3pm.lol）與外部雲端主機分流規則](#4-萬用字元網域3pmlol與外部雲端主機分流規則)

---

## 1. Mac 啟動 WARP 導致網站中斷與解決方法（Split Tunnels）

### 🚨 症狀與原因
- **症狀**：Mac 本機開啟 WARP VPN 後，外網的使用者突然打不開你架設在 K8s 上的網站服務（如 WordPress、n8n 等）。
- **原因**：**非對稱路由衝突（Asymmetric Routing）**。當 Mac 開啟 WARP 後，WARP 接管了所有網路流量。當外部流量透過 `cloudflared` 進來，K8s 容器要回覆時，封包被 WARP 強行攔截並送往外網 VPN 通道，導致連線中斷。

### ⚙️ 解決步驟（在 Cloudflare Zero Trust 設定排除）
必須將 K8s 內部網段及本地局域網排除在 WARP 的接管之外：

1. 登入 [Cloudflare Zero Trust 後台](https://one.dash.cloudflare.com/)。
2. 點選左側選單最下方的 **`Settings`（設定）** ──> **`WARP Client`（WARP 客戶端）**。
3. 在 **`Device settings`（設備設定）** 區塊中，找到 **`Default`** 設定檔，點選右側的 `...` ──> **`Configure`（配置）**。
4. 下拉找到 **`Split Tunnels`（分離通道）** 區塊，確認模式為 **`Exclude IPs and domains`**，點選 **`Manage`**。
5. 點選 **`Add Route`** 新增以下本地網段以進行排除：
   - `10.42.0.0/16`（Kubernetes 預設 Pod 容器網段）
   - `10.43.0.0/16`（Kubernetes 預設 Service 網段）
   - `192.168.31.0/24`（你家裡的實體 Wi-Fi 區域網路網段）
6. 儲存設定。此時 Mac 上的 WARP 會自動同步排除規則，網站即可正常對外服務。

---

## 2. 影音串流（Jellyfin）本地免繞路優化

### 🚨 症狀
使用 `jelly.3pm.lol` 在家裡看影片時，大流量會先繞到 Cloudflare 節點再回來，導致速度變慢、佔用外網頻寬，且容易被 Cloudflare 限制流量。

### 🛠️ 推薦的兩種解決方案

#### 方案 A. 直接使用本地 IP + Port（最簡單、速度最快）
- **在家裡時**：直接連線 `http://192.168.31.123:8096`。封包完全不走外網，Wi-Fi 直連，速度極限（1Gbps+）。
- **在外面時**：使用 `https://jelly.3pm.lol` 走 Cloudflare 傳送門。
- *註：這是最省硬體資源的做法，缺點是內外網需要切換書籤。*

#### 方案 B. 雙向 DNS + 本地反向代理 Caddy（最優雅、網址相同且無憑證警告）
如果你希望不論內外網都使用 `https://jelly.3pm.lol`：
1. **設定雙向 DNS**：在本地的 Pi-hole / AdGuard Home / 路由器中，設定將 `jelly.3pm.lol` 的 IP 直接解析為 Mac 本地 IP `192.168.31.123`。
2. **本地 Caddy 配置**：在 Mac 上運行一個 Caddy，因為 Let's Encrypt 無法為私有 IP 發行憑證，我們利用 **DNS-01 驗證法** 透過 Cloudflare API 寫入臨時 DNS 來向 Let's Encrypt 證明網域所有權。Caddyfile 設定範例：
   ```caddy
   jelly.3pm.lol {
       tls {
           dns cloudflare <YOUR_CLOUDFLARE_API_TOKEN>
       }
       reverse_proxy 127.0.0.1:8096
   }
   ```

---

## 3. SSH 本地直連與外部 WARP 私有網路連線

### 🔒 為什麼 SSH 不需要 Caddy 等 SSL 憑證？
網頁（HTTPS）需要 SSL 憑證是因為瀏覽器有嚴格的安全信任機制。而 **SSH 本身就自帶強大的金鑰加密協定**，它不需要向證書機構申請憑證，只要網址或 IP 對了，連線就保證是加密安全的，因此不需要 Caddy 轉接。

### 🔀 連線情境與路由
當你在 Cloudflare Tunnel 中設定了私有網路（CIDR，例如 `192.168.31.0/24`）：

- **在家時（連 Wi-Fi）**：
  - 手機**關閉 WARP**。
  - 直接 SSH 連線 `192.168.31.123`。流量直接走 Wi-Fi，最快。
- **在外時（連行動網路）**：
  - 手機**開啟 WARP**（加入 Teams 設備清單後）。
  - 在 SSH App 中輸入 `192.168.31.123`。Cloudflare 會辨識出此私有 IP，將流量引導回 Mac 本地，實現如同在內網一般的安全連線。

---

## 4. 萬用字元網域（*.3pm.lol）與外部雲端主機分流規則

### ❓ 萬用字元會不會覆蓋其他雲端主機？
不會。如果你將 `*.3pm.lol` 都指向本地 K8s 上的 Tunnel，但你另外有 `vpn.3pm.lol` 和 `mail.3pm.lol` 在不同的雲端主機上。

### ⚖️ DNS 優先級鐵律
DNS 解析遵循：**「精準匹配（Exact Match） ＞ 萬用字元（Wildcard）」**。
- 當使用者連線 `vpn.3pm.lol`：Cloudflare 發現你有**明確指定**的 A 紀錄，因此流量直接引導至雲端主機。
- 當使用者連線 `n8n.3pm.lol`：Cloudflare 發現沒有專門的紀錄，於是 **fallback（降級套用）** 萬用字元 `*.3pm.lol`，將流量引導至你的本地 K8s。
- **安全做法**：確保 `vpn` 與 `mail` 的 DNS 紀錄在 Cloudflare DNS 頁面中有確實寫出來即可。
