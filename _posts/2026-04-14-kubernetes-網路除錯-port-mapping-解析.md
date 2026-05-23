---
title: "Kubernetes 網路除錯：Port Mapping 解析"
date: 2026-04-14 10:00:00 +0800
categories:
  - 技術
tags:
  - Kubernetes
  - 網路
  - DevOps
  - 除錯
---

為什麼 8096 與 30096 讓你混亂？本文解析 Kubernetes 中的兩種連線方式。

<!-- more -->

## 方式 A：kubectl port-forward (臨時隧道)

這是一個**臨時的捷徑**。它直接把你的 Mac 埠號連到 K8s 內部的 Service。

```
Mac 瀏覽器 8096 ──(隧道)──> Service 8096
```

**網址：** http://localhost:8096

> ※ 缺點：Pod 重啟時隧道會斷，需要重開指令。

## 方式 B：NodePort (正式大門)

這是在 YAML 裡設定的正式門牌 30096。但在你的 Mac 上，這道門被 Docker 的牆擋住了。

```
Mac 瀏覽器 30096 ──(牆)──X── K8s 節點 30096
```

> ※ 原因：我們建立 k3d 時沒加上 "-p" 指令，所以 Docker 沒在 Mac 上開這個 30096 埠。

## 結論

因為我們目前的「隧道」是連往 8096 的，所以請統一使用 **localhost:8096**。

如果您剛才斷線了，請重新執行：
```bash
kubectl port-forward svc/jellyfin-service 8096:8096 -n jellyfin
```

## Port Mapping 快速參考

| 類型 | 用途 | 持久性 |
|------|------|--------|
| port-forward | 開發調試用 | 臨時，斷開需重連 |
| NodePort | 正式暴露服務 | 需在 k3d 建立時設定 |
| LoadBalancer | 雲端環境 | 雲端平台自動設定 |

> 來源參考：[kuniakil/my-k8s](https://github.com/kuniakil/my-k8s)