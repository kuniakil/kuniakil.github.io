---
layout: post
title: "jelly lab guide 2026"
date: 2026-06-10 00:00:00 +0800
categories: [General]
tags: []
---

# Jelly-Lab: 從 Docker Compose 到 Kubernetes 的優雅遷移

date: 2026-05-26 16:00:00 +0800
categories: [Kubernetes, HomeLab]
tags: [k8s, orbstack, cloudflare, zero-trust, jellyfin, nextcloud]

## 1. 核心架構 (Infrastructure)

本次遷移的核心目標是在有限的資源下，建立一個現代化、易於管理的微型資料中心。

### 基礎設施
捨棄耗費資源的 Docker Desktop + k3d 組合，改用 **OrbStack** 的單節點 Kubernetes 叢集。記憶體佔用大幅下降，僅約 **2.2GB** 即可流暢跑起全套基礎服務。

*   **Node Name**: `orbstack`
*   **Storage Strategy**: `hostPath`（直接掛載 Mac 本機路徑，確保資料持久化且無需複雜的 PV/PVC 設定）
*   **Version Control**: 專案設定皆以 `mac-new-config` 分支存放於 Git。

### 網路與安全 (Network)
拋棄舊版「每個服務開一個 Tunnel」的笨方法，整合 **Cloudflare Zero Trust**，實現「一個隧道管全家」。

*   **L7 (Public)**: 透過 Public Hostname (HTTP) 存取 Jellyfin, Nextcloud, WordPress 等網頁服務。
*   **L4 (Private)**: 透過 **WARP + CIDR (192.168.31.123)** 直接連線 SSH。徹底解決了原生 SSH 客戶端（如 Termius）無法透過 L7 隧道連線的問題，實現真正的 Zero Trust 遠端存取。

---

## 2. 服務矩陣 (Service Matrix)

| 服務 | 命名空間 (Namespace) | 存取網址 | 儲存方式 (hostPath) |
| :--- | :--- | :--- | :--- |
| **Jellyfin** | `jellyfin` | `https://jelly.3pm.lol` | `~/jellyfin` & `~/k8s-media` |
| **qBittorrent** | `jellyfin` | `http://localhost:8080` / `https://qb.3pm.lol` | `~/qbittorrent/config` & `~/k8s-media` |
| **Prowlarr** | `jellyfin` | `http://localhost:9696` / `https://prowlarr.3pm.lol` | `~/prowlarr/config` |
| **FlareSolverr** | `jellyfin` | Internal (`http://flaresolverr-service:8191`) | Ephemeral (Memory cache) |
| **Radarr** | `jellyfin` | `http://localhost:7878` / `https://radarr.3pm.lol` | `~/radarr/config` & `~/k8s-media` |
| **Sonarr** | `jellyfin` | `http://localhost:8989` / `https://sonarr.3pm.lol` | `~/sonarr/config` & `~/k8s-media` |
| **Bazarr** | `jellyfin` | `http://localhost:6767` / `https://bazarr.3pm.lol` | `~/bazarr/config` & `~/k8s-media` |
| **Nextcloud** | `nextcloud` | `https://nextcloud.3pm.lol` | `~/nextcloud/nextcloud-data` |
| **WordPress** | `web-apps` | `https://wp.3pm.lol` | `~/WDC` |
| **SSH Gateway** | `gateway` | `192.168.31.123`（需 WARP） | Ephemeral (cloudflared) |

*(註：Nextcloud 與 WordPress 皆已在 K8s 內部署了專屬的 MariaDB Pod，並透過內部 Service 互相溝通。)*

---

## 3. 遷移成功的關鍵知識

### 聲明式管理 (Declarative Management)
拋棄 `docker compose up`，改擁抱 `kubectl apply -f .`。Kubernetes 的 Rolling Update 機制確保了服務更新時的「零停機時間」，它會先確保新 Pod 健康運作後，再優雅地關閉舊 Pod。

### Zero Trust SSH 的突破
最大挑戰在於手機 SSH 的連線。Cloudflare 的 Public Hostname (L7) 無法處理原生的 TCP/SSH 封包。解決方案：
1. 在 Tunnel 中設定 Private Network (CIDR: `192.168.31.123/32`)
2. 在 WARP 的 Split Tunnels 中設定 **Include Mode**，確保只有指向該 IP 的流量會走加密隧道
3. 這樣既保證了本機上網速度不被拖慢，又實現了安全的手機遠端 SSH

### 8GB RAM 存活指南
在資源受限的機器上跑 K8s：
1. 選擇 OrbStack 而非厚重的 VM
2. 使用 `hostPath` 節省 Storage Class 的開銷
3. 關閉不必要的 K8s 組件（如 Metrics Server）
4. 必要時使用 `resources.limits` 限制吃 RAM 怪獸（如 PHP-FPM）

### qBittorrent 與 libtorrent 2.0 的 SSD 與記憶體最佳化（針對 8GB Mac + 外接 SSD）
qBittorrent v5.0+ 搭配 libtorrent v2.0+ 中，軟體層磁碟快取已被移除，改由系統的 `mmap` 機制接管。為防止在 8GB Mac 的有限資源下因吃滿 Pod 限額（`1Gi`）而被 K8s 判定為 OOMKilled，同時要降低外接 USB 3.0 SSD 的磨損：

1. **Disk IO type**：由 `Default` 改為 `Simple pread/pwrite`，停用 mmap 映射，將記憶體使用量穩定控制在數百 MB 以內
2. **Disk IO read/write mode**：保持在 `Enable OS cache`，讓系統在記憶體中緩衝數據，避免頻繁寫入硬碟造成 SSD 損耗與系統 I/O 阻塞

---

> 本專案設定與部署過程由 **Gemini CLI** (Auto-Edit Mode) 協助完成。