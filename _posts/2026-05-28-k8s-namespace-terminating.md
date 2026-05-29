---
title: "解決 Kubernetes Namespace 卡在 Terminating 狀態的終極指南"
date: 2026-05-28 10:00:00 +0800
categories:
  - Kubernetes
  - Troubleshooting
tags:
  - k8s
  - namespace
  - terminating
  - k9s
  - force-delete
---

在操作 Kubernetes 時，我們經常會使用 `kubectl delete namespace <name>` 來一鍵清空某個專案的所有資源。但有時候，您會發現 Namespace 標記為 `Terminating`，然後就這樣卡了 10 分鐘甚至幾個小時都不會消失。

這篇指南將解釋為什麼會發生這種情況，以及如何快速「拔管」解決它。

## 為什麼會卡在 Terminating？

當您下達刪除 Namespace 的指令時，K8s 其實是在做資源回收：它會依序去刪除該 Namespace 底下的所有東西（Pod -> ReplicaSet -> Deployment -> Service -> Volume）。

如果發生以下狀況，整個回收流程就會卡住：
1. **Pod 拒絕死亡**：某個 Pod 可能正在執行繁重的 I/O 操作、拉取巨大的 Image 卡住，或是無法卸載掛載的 Volume（如 `hostPath` 或 NFS）。K8s 預設會給 Pod 30 秒的優雅關閉時間（Grace Period），如果 Pod 一直不回應，K8s 就會傻傻地等。
2. **Finalizers (終結者) 未清除**：某些資源（如被外部 LoadBalancer 綁定的 Service）需要完成特定的清理動作後，才會移除其身上的 `finalizers` 標籤。如果清理動作失敗，標籤不掉，資源就刪不掉。

Namespace 必須等到裡面**完全空無一物**時才會真正消失。只要有一個卡住的 Pod，Namespace 就會永遠卡在 `Terminating`。

## 解決方案一：精準拔管 (使用 CLI)

如果您習慣使用命令列，可以使用強制刪除指令來清理卡住的 Pod。

### 1. 找出卡住的元兇
首先，查看該 Namespace 下還有什麼東西殘留：
```bash
kubectl get all -n <your-namespace>
```
您通常會看到一個或多個狀態為 `Terminating` 的 Pod。

### 2. 強制刪除 (Force Delete)
對那個卡住的 Pod 執行強制拔管，設定 `grace-period=0` 代表不給它任何交代後事的時間，立刻斬殺：
```bash
kubectl delete pod <pod-name> -n <your-namespace> --force --grace-period=0
```

### 3. 清理剩餘物件
如果 Pod 被強制刪除了，但 Namespace 還在，請手動清理殘留的 Deployment 或 Service：
```bash
kubectl delete deploy,svc,rs --all -n <your-namespace>
```
當最後一個殘骸被清除，K8s 發現房間空了，Namespace 就會瞬間消失。

---

## 解決方案二：圖形化快刀 (使用 k9s)

如果您使用 `k9s` 這個終端機神器，解決這個問題會優雅很多，不需要打一長串指令。

1. **進入出問題的 Namespace**：按下 `:`，輸入 `pod` 進入 Pod 列表。確保您正在查看那個卡住的 Namespace（按 `0` 查看全部，或用 `:ns` 切換）。
2. **鎖定目標**：用方向鍵選中那個狀態一直顯示 `Terminating` 的 Pod。
3. **溫柔刪除 (無效時)**：通常我們按 `Ctrl + d` 來刪除資源，這等於一般的 `kubectl delete`。如果它卡住了，這個按鍵沒用。
4. **強制拔管 (Force Delete)**：按下 **`Shift + f`** (大寫 F)。`k9s` 會跳出一個紅色的警告視窗，詢問您是否要 Force Delete。按下 Enter 確認。

Pod 瞬間消失後，您再按 `:ns` 查看，那個卡住的 Namespace 應該就已經灰飛煙滅了。

## 結語

理解 K8s 的「優雅關閉」與「強制刪除」的差異，是掌握 K8s 資源管理的必經之路。遇到 `Terminating` 卡死不用慌，這只是某個小組件在做最後的掙扎，給它一刀 `force` 就能解決 99% 的問題。