---
title: "Kubernetes 生命週期管理指南"
date: 2026-04-12 10:00:00 +0800
categories:
  - 技術
tags:
  - Kubernetes
  - k3d
  - DevOps
  - 學習
---

在 Mac 上使用 k3d 學習 Kubernetes 時，管理叢集的生命周期非常重要。本文介紹三種不同級別的資源管理策略。

<!-- more -->

## 三種生命週期管理層級

### Level 1: 縮放 (Scale) - 暫停服務

只是叫住戶搬走，房子還在。最適合平常省記憶體用。

**關閉：**
```bash
kubectl scale deployment/jellyfin --replicas=0 -n jellyfin
```

**開啟：**
```bash
kubectl scale deployment/jellyfin --replicas=1 -n jellyfin
```

### Level 2: 停止 (Stop) - 叢集休眠

整棟大樓斷電鎖門。適合要關掉 Docker 睡覺時。

**關閉：**
```bash
k3d cluster stop jelly-lab
```

**開啟：**
```bash
k3d cluster start jelly-lab
```

### Level 3: 刪除 (Delete) - 大樓拆除

地基剷平。適合要徹底重做實驗或搬家時。

**執行：**
```bash
k3d cluster delete jelly-lab
```

> ⚠️ 注意：Config 資料會消失，但 Media 還在。

## Level 3 災難復原腳本

如果您不小心執行了 Delete，請依序執行這兩行指令，環境就會自動重建：

**第一步：重建大樓與隧道**
```bash
k3d cluster create jelly-lab -v "~/k8s-media:/mnt/media@server:0" -p "8096:30096@loadbalancer"
```

**第二步：全自動部署**
請進入儲存那 6 個 YAML 檔案的資料夾執行：
```bash
kubectl apply -f .
```

## 存儲策略說明

| 類型 | 位置 | 持久性 |
|------|------|--------|
| Media (媒體檔案) | 外接 HDD ~/k8s-media | 安全（獨立於叢集） |
| Configs (設定檔) | k3d Docker volumes | 刪除叢集後消失 |

> 來源參考：[kuniakil/my-k8s](https://github.com/kuniakil/my-k8s)