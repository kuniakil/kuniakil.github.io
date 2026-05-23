---
title: "Docker vs Kubernetes 指令對照表"
date: 2026-04-10 10:00:00 +0800
categories:
  - 技術
tags:
  - Kubernetes
  - Docker
  - DevOps
  - 學習
---

這份對照表幫助你從單機 Docker 操作轉換到叢集 Kubernetes 維運。

<!-- more -->

## 查看狀態 (Observability)

| 功能 | Docker 指令 | Kubernetes 指令 |
|------|-----------|----------------|
| 查看運行中的程式 | `docker ps` | `kubectl get pods` |
| 查看所有程式 (含停止) | `docker ps -a` | `kubectl get pods -A` (-A 是全空間) |
| 即時監控狀態 | (無直接對應) | `kubectl get pods -w` (-w 是 Watch) |
| 查看資源佔用 (RAM/CPU) | `docker stats` | `kubectl top pods` |

## 操作與控制 (Lifecycle)

| 功能 | Docker 指令 | Kubernetes 指令 |
|------|-----------|----------------|
| 啟動服務 | `docker compose up -d` | `kubectl apply -f .` |
| 停止並移除服務 | `docker compose down` | `kubectl delete -f .` |
| 進入容器內部 | `docker exec -it ID bash` | `kubectl exec -it <pod> -n <ns> -- bash` |
| 檢視日誌 | `docker logs <id>` | `kubectl logs <pod> -n <ns>` |
| 重新啟動服務 | `docker restart <id>` | `kubectl rollout restart deploy/<name> -n <ns>` |

## 資源管理 (Resources)

| 功能 | Docker 指令 | Kubernetes 指令 |
|------|-----------|----------------|
| 查看磁碟使用 | `docker system df` | `kubectl get pvc -A` |
| 清理未使用資源 | `docker system prune` | `kubectl delete pod --field-selector=status.phase=Succeeded` |
| 查看網路連線 | `docker network ls` | `kubectl get svc -A` |

## 圖形化工具 (GUI)

| 功能 | Docker | Kubernetes |
|------|--------|------------|
| 視覺化介面 | Docker Desktop Dashboard | [k9s](https://k9scli.io/) |

> 提示：k9s 是一個終端機 UI，讓你能用鍵盤快速管理 K8s 資源，適合喜歡在終端機操作的人。

## 快速參考

```bash
# Docker
docker ps
docker-compose up -d
docker exec -it container_name bash

# Kubernetes
kubectl get pods
kubectl apply -f deployment.yaml
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh
```

> 來源參考：[kuniakil/my-k8s](https://github.com/kuniakil/my-k8s)