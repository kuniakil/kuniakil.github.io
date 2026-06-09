---
layout: post
title: "ssh warp troubleshooting 2026"
date: 2026-06-09 00:00:00 +0800
categories: [General]
tags: []
---

# 🔍 Cloudflare WARP 手機行動網路 SSH 連線故障排查與解決紀錄

本文件紀錄了手機在 **4G/5G 行動網路** 下開啟 Cloudflare WARP，卻無法透過私有 IP (`192.168.31.123`) SSH 連線至 Mac 本機的故障排查過程與解決方案。

---

## 🚨 問題現象
* **在家中（區域網路 Wi-Fi）**：手機可以順利透過 `192.168.31.123:22` SSH 連線到 Mac（開啟或關閉 WARP 皆可）。
* **在室外（行動網路 4G/5G）**：手機開啟 Cloudflare WARP，嘗試 SSH 連線 `192.168.31.123` 時，**連線逾時失敗**。

---

## 🛠️ 排查步驟

### 步驟 1：驗證 Mac 本機與 K8s 容器網路是否相通
我們在 K8s 叢集內啟動了一個臨時的 Alpine 容器，並對 Mac 本機 IP 執行 TCP 埠掃描：
```bash
kubectl run net-test --rm -i --image=alpine -- nc -w 3 -zv 192.168.31.123 22
```
* **結果**：輸出 `192.168.31.123:22 open`。
* **結論**：代表 Mac 本機的 SSH 服務正常監聽所有網路卡，且 OrbStack 的虛擬機器網路（`cloudflared` 運行的環境）是可以正常連接到 Mac 本機的。排除了 Mac 本機防火牆阻擋的可能性。

### 步驟 2：驗證 Cloudflare Tunnel 的私有網路路由
使用 Cloudflare API 查詢目前 Tunnel 註冊的 CIDR 路由：
```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/teamnet/routes"
```
* **結果**：確認有兩條路由指向您的 K8s 隧道 `fc5a3dd5-29c5-45ac-b2fa-61c60ae4dbd1`：
  1. `192.168.31.123/32`
  2. `10.42.81.123/32`
  且 Tunnel 設定中的 `warp-routing` 欄位為 `enabled: true`。
* **結論**：Cloudflare 雲端到本地 Tunnel 的路由是完全正確的。

### 步驟 3：驗證 WARP 設備設定檔（Device Settings Profiles）
這是發現問題的關鍵。我們使用 API 查詢了 Cloudflare 帳戶中的所有設備策略：
```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/devices/policies"
```
發現帳戶中存在三個設定檔，且規則如下：
1. **`Macbook` 策略** (套用於 Mac)：
   * 模式：**Exclude Mode（排除模式）**。
   * 排除名單包含：`192.168.0.0/16`。
   * *說明：這是正確的，避免了 Mac 本機的非對稱路由衝突。*
2. **`mobilephone` 策略** (套用於 Android/iOS 手機)：
   * 模式：**Exclude Mode（排除模式）**。
   * 排除名單同樣包含：`192.168.0.0/16`。
3. **`Default` 策略** (預設降級策略)：
   * 模式：**Include Mode（包含模式）**。
   * 包含名單包含：`192.168.31.123/32`。

---

## 🎯 根本原因（踩坑點）
由於手機是 iOS/Android 系統，它會**優先匹配**到自訂的 `mobilephone` 策略，而不是 `Default` 策略。

而 `mobilephone` 策略當時被設為 **Exclude Mode**，且排除了 `192.168.0.0/16`：
1. 手機在 4G/5G 嘗試發送封包到 `192.168.31.123`。
2. 手機的 WARP App 發現 `192.168.31.123` 屬於 `192.168.0.0/16`，因此觸發排除規則，**繞過 WARP 隧道**。
3. 封包被直接送往手機的 4G/5G 電信商網路。
4. 電信商網路無法路由私有 IP，導致連線直接**斷開/逾時**。

---

## 💡 解決方案
為了讓手機的 WARP 能接管 `192.168.31.123` 的流量，我們將手機設定檔改為 **Include Mode**。

我們使用 API 對 `mobilephone` 設定檔（ID: `57b027a1-5ef7-4257-9274-510a7cba9b27`）的 `/include` 端點發送更新：
```bash
curl -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/devices/policy/57b027a1-5ef7-4257-9274-510a7cba9b27/include" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[
    {"address": "192.168.31.123/32", "description": "Mac Host SSH"},
    {"address": "10.42.81.123/32", "description": "K8s Node/Pod Network"}
  ]'
```

### 🎯 調整後的效果
* 手機的 WARP 成功切換為 **Include 模式**。
* 現在，只有發往 `192.168.31.123` 和 `10.42.81.123` 的流量會被吸入 WARP 隧道並經由 Cloudflare Tunnel 安全送回 Mac。
* 其他所有一般網頁瀏覽流量都直接走 4G/5G，保持原速且不佔用 Tunnel 頻寬。

---

## 🧠 學習總結與心法
在 Zero Trust 網路設計中：
1. **伺服器端（如 Mac 主機）**：通常需要 **Exclude 模式**，排除本地局域網（如 `192.168.31.0/24`），防止流量回覆時走錯網卡（非對稱路由）。
2. **行動客戶端（如手機、筆電在外網）**：如果只想存取 Homelab，最優雅的做法是 **Include 模式**，只將 Homelab 的特定私有 IP 納入隧道，其餘流量直連網際網路。
3. **區分設備設定檔（Device Profiles）**：絕對不能讓「伺服器」與「手機」套用同一個 Split Tunnel 設定檔，必須在 Zero Trust 中依據作業系統或裝置名稱進行分流配置。