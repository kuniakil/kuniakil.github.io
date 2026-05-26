---
title: "Jelly-Lab: 從 Docker Compose 到 Kubernetes 的優雅遷移"
date: 2026-05-26 16:00:00 +0800
categories: [Kubernetes, HomeLab]
tags: [k8s, orbstack, cloudflare, zero-trust, jellyfin, nextcloud]
---

這是一份關於將 HomeLab 服務從傳統 Docker Compose 遷移至 Kubernetes (OrbStack) 的完整技術紀錄。特別針對 **8GB RAM 的 Mac** 進行了極致的資源最佳化。

## 1. 核心架構 (Infrastructure)

本次遷移的核心目標是在有限的資源下，建立一個現代化、易於管理的微型資料中心。

### 基礎設施
我們捨棄了耗費資源的 Docker Desktop + k3d 組合，改用 **OrbStack** 的單節點 Kubernetes 叢集。這讓記憶體佔用大幅下降，僅約 **2.2GB** 即可流暢跑起全套基礎服務。

*   **Node Name**: `orbstack`
*   **Storage Strategy**: `hostPath` (直接掛載 Mac 本機路徑，確保資料持久化且無需複雜的 PV/PVC 設定)
*   **Version Control**: 專案設定皆以 `mac-new-config` 分支存放於 Git。

### 網路與安全 (Network)
拋棄了舊版「每個服務開一個 Tunnel」的笨方法，我們整合了 **Cloudflare Zero Trust**，實現「一個隧道管全家」。

*   **L7 (Public)**: 透過 Public Hostname (HTTP) 存取 Jellyfin, Nextcloud, WordPress 等網頁服務。
*   **L4 (Private)**: 透過 **WARP + CIDR (192.168.31.123)** 直接連線 SSH。這徹底解決了原生 SSH 客戶端 (如 Termius) 無法透過 L7 隧道連線的問題，實現了真正的 Zero Trust 遠端存取。

---

## 2. 服務矩陣 (Service Matrix)

目前部署的四大核心模組及其對應關係：

| 服務 | 命名空間 (Namespace) | 存取網址 | 儲存方式 (hostPath) |
| :--- | :--- | :--- | :--- |
| **Jellyfin** | `jellyfin` | `https://jelly.3pm.lol` | `~/jellyfin` & `~/k8s-media` |
| **Nextcloud** | `nextcloud` | `https://nextcloud.3pm.lol` | `~/nextcloud/nextcloud-data` |
| **WordPress** | `web-apps` | `https://wp.3pm.lol` | `~/WDC` |
| **SSH Gateway** | `gateway` | `192.168.31.123` (需 WARP) | Ephemeral (cloudflared) |

*(註：Nextcloud 與 WordPress 皆已在 K8s 內部署了專屬的 MariaDB Pod，並透過內部 Service 互相溝通。)*

---

## 3. 遷移成功的關鍵知識

### 聲明式管理 (Declarative Management)
拋棄 `docker compose up`，改擁抱 `kubectl apply -f .`。Kubernetes 的 Rolling Update 機制確保了服務更新時的「零停機時間」，它會先確保新 Pod 健康運作後，再優雅地關閉舊 Pod。

### Zero Trust SSH 的突破
最大的挑戰在於手機 SSH 的連線。我們發現 Cloudflare 的 Public Hostname (L7) 無法處理原生的 TCP/SSH 封包。解決方案是：
1. 在 Tunnel 中設定 Private Network (CIDR: `192.168.31.123/32`)。
2. 在 WARP 的 Split Tunnels 中設定 **Include Mode**，確保只有指向該 IP 的流量會走加密隧道。
3. 這樣既保證了本機上網速度不被拖慢，又實現了安全的手機遠端 SSH。

### 8GB RAM 存活指南
在資源受限的機器上跑 K8s：
1. 選擇 OrbStack 而非厚重的 VM。
2. 使用 `hostPath` 節省 Storage Class 的開銷。
3. 關閉不必要的 K8s 組件 (如 Metrics Server)。
4. 必要時使用 `resources.limits` 來限制吃 RAM 怪獸 (如 PHP-FPM)。

> 本專案設定與部署過程由 **Gemini CLI** (Auto-Edit Mode) 協助完成。
