---
title: "Kubernetes 生命週期與災難復原指南 (OrbStack 版)"
date: 2026-05-26 16:30:00 +0800
categories: [Kubernetes, Operations]
tags: [k8s, orbstack, lifecycle, scaling, recovery]
---

這份指南總結了在 8GB RAM Mac 上使用 OrbStack 運行 Kubernetes 時，如何優雅地管理服務的生命週期，並在必要時進行快速的災難復原。

## 生命週期管理三級距

我們將服務的開關與移除分為三個嚴重等級，請根據您的需求選擇適合的操作。

### 🟢 Level 1: 縮放 (Scale) - 暫停服務
只是叫住戶搬走，房子（設定檔）還在。最適合在 8GB RAM 機器上**臨時釋放記憶體**。

*   **關閉 (Scale down to 0)**：
    ```bash
    kubectl scale deployment/[服務名] --replicas=0 -n [命名空間]
    # 範例: kubectl scale deployment jellyfin --replicas=0 -n jellyfin
    ```
*   **開啟 (Scale up to 1)**：
    ```bash
    kubectl scale deployment/[服務名] --replicas=1 -n [命名空間]
    ```

### 🟠 Level 2: 停止 (Stop) - 叢集休眠
整台伺服器斷電。適合要「幹正事」不想讓後台跑東西，或是關機睡覺時。

*   **操作**：點擊 Mac 選單列的 OrbStack 圖示，選擇 **"Quit OrbStack"**。
*   **優點**：下次打開 OrbStack 時，所有設定好的 K8s 服務（只要副本數大於 0）會**自動恢復運作**，無需重新下指令。

### 🔴 Level 3: 刪除 (Delete) - 大掃除
地基剷平。適合要徹底重做實驗、移除不再使用的服務，或是釋放所有空間時。

*   **刪除指定服務**（透過 YAML 檔）：
    ```bash
    kubectl delete -f [資料夾或檔案]
    ```
*   **刪除整個命名空間**（一口氣清空該類別下的所有資源）：
    ```bash
    kubectl delete ns [命名空間]
    ```
> ⚠️ **注意**：執行 Level 3 後，K8s 裡的設定紀錄會完全消失。但由於我們使用 `hostPath`，您硬碟裡的實體資料夾檔案仍會安全保留。

---

## 🚨 災難復原腳本 (真正的一鍵回歸)

如果您不小心執行了 Level 3 的 Delete 操作，或是換了一台新電腦，不用擔心！這就是 **IaC (基礎設施即代碼)** 的魔力。只要依序執行以下指令，環境就會自動重建：

### 1. 確認基礎設施就緒
只要 OrbStack 的 Kubernetes 狀態為綠燈，代表底層的虛擬節點已經打好了。

### 2. 全自動部署 (Apply)
請進入您的專案根目錄 (`~/kubernetes`)，並依序套用 YAML 設定檔：

```bash
# 啟動 Cloudflare 網關
kubectl apply -f gateway/tunnel-deployment.yaml

# 啟動應用服務
kubectl apply -f jellyfin/
kubectl apply -f nextcloud/nc-bundle.yaml
kubectl apply -f wordpress/wp-bundle.yaml
```

### 3. 驗證服務
等待 Pods 狀態變為 `Running` 後，即可直接造訪綁定在 Cloudflare Tunnel 上的網頁：
*   `https://jelly.3pm.lol`
*   `https://nextcloud.3pm.lol`
*   `https://wp.3pm.lol`

**💡 為什麼復原變得這麼簡單？**
因為我們捨棄了笨重且與特定環境綁定的 PV/PVC，改用 `hostPath` 直接掛載 Mac 的絕對路徑，並將外部連線全權交由 Cloudflare 統一管理。資料夾裡的這些 YAML 檔案，已經包含了「從行政區劃分到家具擺設」的所有絕對真理。
