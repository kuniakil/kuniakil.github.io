---
title: "Kubernetes 系統組件復原手冊"
date: 2026-05-28 11:00:00 +0800
categories:
  - Kubernetes
  - Operations
tags:
  - k8s
  - orbstack
  - recovery
  - troubleshooting
---

這份備份資料夾包含了您的 OrbStack Kubernetes 叢集中最核心的「系統級服務」設定。如果您在實驗過程中（例如在 `k9s` 中）不小心刪除了 `kube-system` 命名空間下的資源，請依照此手冊快速恢復。

## 📁 備份內容說明
- **`coredns.yaml`**：負責整個叢集的域名解析（如果刪掉，Pod 之間會連不上，網址也會打不開）。
- **`local-path-provisioner.yaml`**：負責自動化管理儲存空間的掛載。
- **`metrics-server.yaml`**：負責收集 CPU 與記憶體數據（如果刪掉，手機 App 和 `k9s` 會看不到使用率）。

---

## 🛠️ 復原步驟

如果您發現某個系統服務不見了（在 `k9s` 看到它消失，或是在 `:deploy` 視圖找不到）：

1. **打開終端機** 並進入專案根目錄。
2. **執行以下對應的指令**：

### 恢復 DNS (導航系統)
```bash
kubectl apply -f kube-system-backups/coredns.yaml
```

### 恢復 Metrics (心跳數據)
```bash
kubectl apply -f kube-system-backups/metrics-server.yaml
```

### 恢復儲存管理器
```bash
kubectl apply -f kube-system-backups/local-path-provisioner.yaml
```

---

## 💡 為什麼要有這份備份？
雖然這些是「系統預裝」的服務，但在 Kubernetes 中，它們同樣是以「Deployment」的形式存在的。這意味著如果您有這份 YAML 設定檔，您就擁有對它們的 100% 控制權與復原權。

這份備份已經包含了我們針對 OrbStack 環境所做的所有特殊修補（例如 `metrics-server` 的跳過證書檢查參數）。

**有了這份文件，您的 Jelly-Lab 就是不死之身！** 🛡️🚀