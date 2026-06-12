---
layout: post
title: "caddy vs traefik tls postmortem"
date: 2026-06-12 00:00:00 +0800
categories: [Concepts]
tags: []
---
# Caddy vs Traefik TLS & 重啟故障事後分析 (Post-mortem)

本文記錄了 2026-06-12 由於 Mac 系統升級重啟後，Caddy Ingress Controller 導致外網訪問報 `502 Bad Gateway` 的故障原因分析，以及為何切換至 **Traefik + cert-manager (DNS-01)** 架構能徹底解決此問題。

---

## 🚨 故障現象與排查過程

### 1. 操作背景
在 Mac 系統升級前，執行了以下標準的安全關機步驟：
1. 將非關鍵應用 Pod (如 Jellyfin) 全部縮容至 0 (`scale to 0`)，保護資料庫與資料寫入安全。
2. 關閉 OrbStack (K3s 本身與內建容器)。
3. 執行 Mac 系統升級並重啟。

### 2. 重啟後的異常
Mac 系統開機並啟動 OrbStack 後，即使將應用 Pod 重新擴容至 1，外網訪問 `jelly.3pm.lol` 依然回報 **502 Bad Gateway**。
* 嘗試 `rollout restart` 重啟 `cloudflared` ➡️ **無效**。
* 嘗試 `rollout restart` 重啟 `caddy-ingress-controller` ➡️ **無效**。

---

## 🔍 核心故障原因剖析

故障的本質並非 Caddy 軟體本身的 Bug，而是 **Caddy 預設的自動憑證申請機制 (ACME) 在 Cloudflare Tunnel (無公網 IP) 的環境下，與 Kubernetes Pod 的無狀態 (Stateless) 特性產生了衝突**。

### 1. Pod 無狀態與憑證遺失
在 Kubernetes 中，Pod 是無狀態的。當 K3s / OrbStack 重啟時，原本運行 Caddy Ingress Controller 的 Pod 被銷毀並重新建立。這導致原先儲存在 Pod 記憶體或臨時掛載路徑中的 TLS 憑證快取徹底遺失。

### 2. ACME HTTP-01 驗證死胡同
重啟後的 Caddy 發現本地缺乏憑證，便會「熱心」地自動發起 Let's Encrypt 的憑證申請流程：
1. Caddy 預設會採用 **HTTP-01** 挑戰驗證。
2. Let's Encrypt 驗證伺服器需要通過 `http://<your-domain>/.well-known/acme-challenge/...` 連線進來驗證所有權。
3. **然而，在 Cloudflare Tunnel 架構下**，您的 K8s 叢集完全隱藏在內網中，沒有暴露任何公網 IP 或路由器埠。所有外部流量都必須經過 `cloudflared` 才能進來。
4. Let's Encrypt 驗證伺服器無法連入 Caddy，導致 Caddy 的憑證申請卡死在無限重試與失敗的循環中。

### 3. TLS Handshake 失敗導致 502
因為憑證一直申請失敗，Caddy 的 HTTPS (443) 服務無法正常啟動，或者僅能提供無效的自簽憑證。
當前方的 `cloudflared` 容器嘗試通過 HTTPS 連線到 Caddy 時，發生 **TLS Handshake 握手失敗**，`cloudflared` 因而直接向您的瀏覽器返回 `502 Bad Gateway`。

---

## 🛡️ 為什麼 Traefik + cert-manager (DNS-01) 架構更加穩健？

在妥協換裝 Traefik 後，我們改變了 TLS 憑證的架構，將「憑證申請」與「流量轉發」徹底解耦。

```
[Cloudflare Edge] 
       ↓ (加密)
[cloudflared (Tunnel)] 
       ↓ (內部 HTTPS / noTLSVerify: true)
[Traefik Ingress (ClusterIP)] ➡️ 讀取 ➡️ [Secret: wildcard-3pm-lol-tls]
       ↓ (轉發)                                      ↑ (自動更新)
[應用 Pod (如 Jellyfin)]                       [cert-manager (DNS-01)]
                                                     ↓ (透過 Token API)
                                              [Cloudflare DNS API]
```

### 1. 憑證申請：由 cert-manager 透過 DNS-01 驗證
我們使用 `cert-manager` 配合 **DNS-01 挑戰** 來自動維護憑證，這個機制完美避開了 Tunnel 的限制：
* **不需公網連入**：當憑證即將到期時，`cert-manager` 使用儲存在 `.secrets.env` 中的 `CLOUDFLARE_API_TOKEN`，主動呼叫 Cloudflare API，在您的網域下自動寫入一筆臨時的 TXT 解析紀錄（例如 `_acme-challenge.3pm.lol`）。
* Let's Encrypt 驗證伺服器只要向全球 DNS 查詢該 TXT 紀錄是否正確，即可完成驗證。
* 驗證通過後，`cert-manager` 下載新憑證並將其更新至 K8s Secret `wildcard-3pm-lol-tls` 中。整個過程完全是「叢集主動外連」，符合單向出站安全規則。

### 2. 流量轉發：由 Traefik 被動加載與熱載入
* **Traefik 不主動申請憑證**：Traefik 本身關閉了自動 ACME 申請，因此重啟時它不會試圖與 Let's Encrypt 通訊。它只負責監聽 K8s 內部的 `wildcard-3pm-lol-tls` Secret。
* **Hot-reload（熱載入）**：當 `cert-manager` 在背景自動續期並更新該 Secret 內容時，Traefik 會自動偵測到 Secret 的更新，並在**不需重啟 Pod** 的情況下直接熱載入新憑證，完全不會中斷服務。
* **ClusterIP 安全架構**：我們將 Traefik 的服務類型改為 `ClusterIP`，避免 K3s 為了分配 Host Port 而產生 `svclb-traefik` 卡在 Pending 的問題，讓叢集狀態保持純淨。

---

## 📝 總結與運維啟示

1. **操作順序無誤**：您原先的關機與重啟操作非常標準，無需改變。
2. **Tunnel 架構下的 Ingress 準則**：在以 Cloudflare Tunnel 為入口的內網 K8s 環境中，Ingress Controller 應保持「純粹的轉發器」角色，並將 TLS 憑證申請委託給使用 **DNS-01** 驗證機制的 `cert-manager`。
3. **避免 Ingress 自動 ACME**：使用 Caddy 或 Traefik 時，皆應停用其內建的 HTTP 憑證自動申請功能，防止重啟後因為連線被 Tunnel 阻擋而陷入 502 癱瘓。
