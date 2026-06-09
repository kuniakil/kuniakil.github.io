---
layout: post
title: "Cloudflare WARP SSH 故障排查"
date: 2026-06-09 00:00:00 +0800
categories: [Concepts]
tags: [infrastructure, protocol]
---

# Cloudflare WARP SSH 故障排查

手機在 4G/5G 行動網路下開啟 Cloudflare WARP，無法 SSH 連線至 Mac 私有 IP（`192.168.31.123`）的完整排查與修復紀錄。

## 問題背景

| 情境 | 結果 |
|------|------|
| 家中 Wi-Fi，關 WARP | ✅ SSH 成功 (`192.168.31.123:22`) |
| 家中 Wi-Fi，開 WARP | ✅ SSH 成功 |
| 4G/5G，開 WARP | ❌ 連線逾時 |

## 排查過程

### 步驟 1：K8s 容器 → Mac 網路可達
```bash
kubectl run net-test --rm -i --image=alpine -- nc -w 3 -zv 192.168.31.123 22
# 輸出：192.168.31.123:22 open
```
→ Mac SSH 正常監聽，K8s VM 網路到 Mac 可達，排除防火牆。

### 步驟 2：Cloudflare Tunnel 路由正確
```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/teamnet/routes"
```
→ 兩條路由存在：`192.168.31.123/32` + `10.42.81.123/32`，`warp-routing: enabled`。

### 步驟 3：Device Settings Profiles — 發現元兇
```bash
curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/devices/policies"
```

發現三個策略，**手機優先匹配 `mobilephone` 而非 `Default`**：

| 策略 | 適用裝置 | 模式 | 包含/排除 |
|------|---------|------|----------|
| Macbook | Mac | Exclude | 排除 `192.168.0.0/16` |
| mobilephone | iOS/Android | **Exclude** | **排除 `192.168.0.0/16`** |
| Default | 其餘 | Include | 包含 `192.168.31.123/32` |

**根本原因**：`mobilephone` 的 Exclude 模式把 `192.168.0.0/16` 全部排除，導致手機把 SSH 流量直接送電信商，私有 IP 無法路由。

## 解決方案

將 `mobilephone` 改為 **Include Mode**，只納入必要網段：

```bash
curl -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/devices/policy/<mobilephone_policy_id>/include" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[
    {"address": "192.168.31.123/32", "description": "Mac Host SSH"},
    {"address": "10.42.81.123/32", "description": "K8s Node/Pod Network"}
  ]'
```

### 效果
- 發往 `192.168.31.123` 和 `10.42.81.123` 的流量 → WARP 隧道 → Cloudflare Tunnel → Mac
- 其餘流量（一般網頁）→ 直接走 4G/5G，不佔 Tunnel 頻寬

## 設計原則

> **「從哪裡開始，就從哪裡結束。」** 網路流量亦然——設備類型不同，Split Tunnel 策略就必須分開。

1. **伺服器端（Mac）**：Exclude Mode，排除本機 LAN，防止非對稱路由
2. **行動客戶端**：Include Mode，只納指定的私有 IP，其餘流量直連

## 相關概念

- cloudflare-tunnel-homelab-optimization — 同主題基礎概念：WARP 排除清單、SSH 路由 Overview
- homelab-networking-hairpinning — Hairpinning 三難題與 Cloudflare Tunnel 取捨
- jelly-lab-context — K8s 叢集環境背景
- cloudflare-warp-ssh-troubleshooting — 本頁面（實戰 Troubleshooting case）