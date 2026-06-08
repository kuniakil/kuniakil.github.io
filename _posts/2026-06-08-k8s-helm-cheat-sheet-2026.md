---
layout: post
title: "k8s helm cheat sheet 2026"
date: 2026-06-08 00:00:00 +0800
categories: [General]
tags: []
---

# 🛠️ Kubernetes (kubectl) vs Helm 指令對照表

本對照表旨在幫助您理解在管理 K8s 服務時，**手動 YAML 模式 (`kubectl`)** 與 **套件管理模式 (`helm`)** 的常用指令對應關係。

---

## 📊 核心操作對照

| 🚀 目的 / 情境 | 📄 Kubectl 模式 (手動 YAML) | 📦 Helm 模式 (套件管理) | 💡 重點說明 |
| :--- | :--- | :--- | :--- |
| **1. 尋找與下載** | 上網找別人的 YAML 檔下載到本機 | `helm repo add <名稱> <網址>`<br>`helm repo update` | Helm 像 App Store，需要先新增「商店源（Repository）」。 |
| **2. 新增與安裝** | `kubectl apply -f <檔案>.yaml` | `helm install <Release名> <Chart名>` | Helm 安裝時必須自訂一個「實例名稱（Release）」。 |
| **3. 查看已裝服務** | `kubectl get deployments -n <namespace>` | `helm list -n <namespace>` | Helm 列出的是「軟體包實例」，而 `kubectl` 列出的是「底層 K8s 元件」。 |
| **4. 升級與更新** | 修改 YAML 檔後：<br>`kubectl apply -f <檔案>.yaml` | 修改 `values.yaml` 後：<br>`helm upgrade <Release名> <Chart名> -f values.yaml` | Helm 升級時只會更動有修改的變數，並自動進行滾動更新。 |
| **5. 快速修改參數** | 直接用編輯器修改 YAML 檔案 | `helm upgrade <Release名> <Chart名> --set <欄位>=<值> --reuse-values` | Helm 支援在命令列直接用 `--set` 修改單一變數（例如改 Image Tag）。 |
| **6. 故障回滾** | 打開舊 YAML 修改回舊設定：<br>`kubectl apply -f <檔案>.yaml` | `helm rollback <Release名> <版本號>` | Helm 內部有歷史紀錄，可以一鍵無痛倒回（Rollback）歷史版本。 |
| **7. 徹底刪除服務** | `kubectl delete -f <檔案>.yaml` | `helm uninstall <Release名>` | Helm 卸載會自動清空當初安裝的**所有**相關元件，不留垃圾。 |

---

## 🛠️ 排查與日常維運（兩者通用）

無論服務是用 `kubectl` 還是 `helm` 安裝的，一旦服務跑起來了，**日常排查與監控一律使用 `kubectl`（或在 `k9s` 中直接操作）**：

* **查看日誌**：
  ```bash
  kubectl logs -n <namespace> <pod名稱> --tail=100 -f
  ```
* **優雅重啟服務**：
  ```bash
  kubectl rollout restart deployment/<deployment名稱> -n <namespace>
  ```
* **手動強制刪除 Pod（觸發自我修復）**：
  ```bash
  kubectl delete pod <pod名稱> -n <namespace>
  ```

---

## 💡 黃金法則與心法

> **「從哪裡開始，就從哪裡結束。」**
> 
> * **Helm 安裝的服務**（OrbStack 標示 `managed by helm`）：
>   * ❌ **不要**使用 `kubectl delete` 去刪除它的 Deployment 或 Service。
>   * 🟢 **務必**使用 `helm uninstall <Release名稱>` 來卸載它。
> 
> * **Kubectl 安裝的服務**（手動 apply YAML）：
>   * 🟢 直接使用 `kubectl apply` 更新，`kubectl delete` 刪除。
