---
title: "Docker Compose 到 K8s 遷移必踩的兩個「大坑」：啟動指令與網路暴露"
date: 2026-05-29 09:30:00 +0800
categories:
  - Kubernetes
  - Migration
tags:
  - k8s
  - docker
  - troubleshooting
  - entrypoint
  - loadbalancer
  - orbstack
---

將服務從 Docker Compose 遷移到 Kubernetes 時，我們經常會想著「直接把參數翻譯過去就好」。但在實際遷移 AI Agent (如 Hermes) 的過程中，我們踩到了兩個非常經典的架構差異陷阱。

這份筆記記錄了這兩個核心差異，幫助未來的我們（或新手）避開這些令人抓狂的 `CrashLoopBackOff` 和 `Connection refused`。

---

## 坑一：啟動指令被無情覆蓋 (Entrypoint vs Command)

### 🚨 症狀
Pod 陷入 `CrashLoopBackOff`，日誌顯示類似錯誤：
> `executable file not found in $PATH`

### 🔍 原因分析
這源於 Docker 和 K8s 針對映像檔啟動參數的命名定義不一致，甚至是**完全衝突**的。

在許多 Docker 映像檔中，開發者會寫一個預設的 `Entrypoint` 腳本（用來準備環境），然後再把我們傳入的指令（Command）附加在後面執行。

*   **在 Docker Compose 裡**：
    我們寫的 `command: gateway run`，會乖乖地被附加在 `Entrypoint` 腳本之後。
*   **在 Kubernetes 裡**：
    如果我們在 YAML 的 container 區塊寫了 `command: ["gateway", "run"]`，**K8s 的 `command` 其實等同於 Docker 的 `entrypoint`**。
    這意味著，K8s 會把映像檔裡原本那個重要的啟動腳本**整組刪掉**，直接去找一個叫 `gateway` 的執行檔，自然就會引發找不到檔案的錯誤。

### ✅ 解決方案
在 Kubernetes 的 YAML 中：
*   **不要用** `command` 來翻譯 Docker 的 `command`。
*   **要用** `args`。

**錯誤的 K8s 寫法 (會覆蓋腳本)：**
```yaml
containers:
  - name: my-agent
    image: my-agent:latest
    command: ["gateway", "run"] # ❌ 這是錯的！
```

**正確的 K8s 寫法 (正確附加參數)：**
```yaml
containers:
  - name: my-agent
    image: my-agent:latest
    args: ["gateway", "run"] # ✅ 這樣才會保留原有的 Entrypoint 腳本
```

---

## 坑二：明明開了 Port 卻連不上 (ClusterIP vs LoadBalancer)

### 🚨 症狀
K8s 裡的 Pod 和 Service 都顯示正常運作，但在 Mac 本機終端機執行 `ssh -p 2222 hermes@localhost` 時卻得到：
> `Connection refused`

### 🔍 原因分析
這是 Docker 網路模型與 K8s 網路模型的根本差異。

*   **在 Docker Compose 裡**：
    寫 `ports: - "2222:22"` 時，Docker 會自動在您的 Mac 主機 (`localhost`) 上打洞，把外面的 2222 埠直接牽線到容器的 22 埠。
*   **在 Kubernetes 裡**：
    當我們建立一個 Service 且沒有特別指定 `type` 時，它預設是 **`ClusterIP`**。
    `ClusterIP` 是在 K8s 的「虛擬內網」中流通的。這意味著：只有叢集裡的其他 Pod（例如 Cloudflare 網關）能看到它。您站在叢集外面的 Mac (`localhost`) 去敲門，K8s 根本不會理您。

### ✅ 解決方案 (特別針對 OrbStack 環境)
要讓 Mac 本機能直接存取 K8s 裡面的服務，我們必須明確改變 Service 的對外暴露類型。

在 OrbStack 這類優化過的本地 K8s 環境中，最佳解是將 Service 類型設為 **`LoadBalancer`**。OrbStack 偵測到這個類型後，就會自動幫您在 Mac 的 `localhost` 綁定對應的通訊埠。

**修正後的 Service 定義：**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: hermes-agent
  namespace: hermes
spec:
  type: LoadBalancer # 👈 關鍵：加上這行，OrbStack 才會在 localhost 開門
  selector:
    app: hermes-agent
  ports:
    - port: 2222
      targetPort: 22
```

## 💡 總結心法

1. **翻譯指令時**：Docker 的 `command` = K8s 的 `args`。
2. **需要本機直接連線時**：K8s 的 Service 不能只用預設，必須加上 `type: LoadBalancer` (或 `NodePort`)。