---
title: "Kubernetes 學習架構：Jellyfin 實作版"
date: 2026-04-11 10:00:00 +0800
categories:
  - 技術
tags:
  - Kubernetes
  - k3d
  - Jellyfin
  - 學習
---

在 Mac 上使用 k3d 學習 Kubernetes 時，Jellyfin 是一个很好的實驗項目。本文說明整體架構設計。

<!-- more -->

## 架構層級圖

```
你的實體電腦
    ↓ 運行
MacBook (8GB RAM)
    ↓ 運行
Docker Desktop (隔離層)
    ↓ 啟動
K3d Cluster (Single Node) - 我們的實驗室
    ↓ 部署
Jellyfin Pod - 服務
```

## 為什麼這樣設計？

- **隔離性：** k3d 像是在 Docker 裡開一個小房間。你在裡面怎麼玩 K8s，都不會碰到外面其他的 Docker 容器。
- **資源節省：** k3d 只佔用約 512MB ~ 1GB RAM，比標準 K8s 輕量很多。
- **掛載挑戰：** 外接硬碟掛載到 K8s 需要經過三層映射，這正是學習「持久化存儲 (PV/PVC)」的最佳實戰！

## 熱掛載實驗路徑

```
外接 HDD (/Volumes/MyDisk)
    → Docker VM
    → k3d Node
    → Jellyfin Pod
```

## 存儲策略

| 類型 | 說明 | 安全性 |
|------|------|--------|
| Media (媒體檔案) | 外接 HDD ~/k8s-media 映射到 /mnt/media | 獨立於叢集，安全 |
| Configs (設定檔) | Dynamic PVCs 管理，儲存在 Docker volumes | 刪除叢集後消失 |

## 環境參數

- **叢集類型：** k3d (K3s in Docker)
- **叢集名稱：** `jelly-lab`
- **節點：** 1 Server node (All-in-one)
- **網路入口：** Mac Port `8096` 映射到 K8s `30096` (NodePort) via loadbalancer

## 常見指令

```bash
# 啟動叢集
k3d cluster start jelly-lab

# 應用所有設定
kubectl apply -f .

# 查看資源使用
kubectl top pods -A
```

> 來源參考：[kuniakil/my-k8s](https://github.com/kuniakil/my-k8s)