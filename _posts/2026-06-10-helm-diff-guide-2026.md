---
layout: post
title: "helm diff guide 2026"
date: 2026-06-10 00:00:00 +0800
categories: [General]
tags: []
---

# 📦 Helm Diff 插件使用指南

`helm-diff` 是一個 Helm 外掛（Plugin），能讓您在執行 `helm upgrade` 或 `helm rollback` 之前，先**預覽 Kubernetes 資源的變更細節**。這在維運生產環境中是一道至關重要的安全防線。

---

## 💡 為什麼需要 Helm Diff？
在沒有安裝 `helm-diff` 之前，執行 `helm upgrade` 就像是閉著眼睛更新，您無法得知：
* 這個更新會不會刪除某個重要的 PVC（持久化儲存）？
* 參數的縮排是不是寫錯了，導致某個環境變數沒有帶入？
* 有哪些 Service Port 被修改了？

安裝 `helm-diff` 後，它會比對「目前運行中的 Release 狀態」與「您本地的新 template/values」，以**紅綠色對照**的方式呈現變更，確認無誤後再執行升級。

---

## 🛠️ 核心指令

### 1. 升級前比對變更（最常用 🌟）
當您修改了 `values.yaml` 或更新了 Chart 版本，在準備部署前，執行此指令：
```bash
helm diff upgrade <Release名稱> <Chart名稱/路徑> -f values.yaml -n <命名空間>
```
* **實際範例**：
  ```bash
  helm diff upgrade caddy-ingress caddy/caddy-ingress-controller -f caddy-ingress/values.yaml -n gateway
  ```

### 2. 比對兩個歷史版本（Revisions）之間的差異
當服務出現問題，想知道「第 5 版」和最新的「第 8 版」之間到底改了什麼：
```bash
helm diff revision <Release名稱> <版本號A> <版本號B> -n <命名空間>
```
* **實際範例**：
  ```bash
  helm diff revision cert-manager 2 3 -n cert-manager
  ```

### 3. 回滾（Rollback）前比對差異
在決定將服務一鍵倒回到舊版本（例如退回第 2 版）之前，先看看會發生什麼變化：
```bash
helm diff rollback <Release名稱> <目標版本號> -n <命名空間>
```
* **實際範例**：
  ```bash
  helm diff rollback cert-manager 2 -n cert-manager
  ```

---

## 🎨 解讀比對結果（顏色標示）

在終端機中，`helm-diff` 會輸出色彩斑斕的差異對照，其代表意義如下：

| 顏色 / 符號 | 代表意義 | 說明 |
| :--- | :--- | :--- |
| **+ 綠色** | **新增（Added）** | 新增的 Kubernetes 物件，或是現有物件中新加入的屬性/欄位。 |
| **- 紅色** | **刪除（Removed）** | 被移除的 Kubernetes 物件，或是現有物件中刪除的屬性/欄位。**（需特別注意，防止誤刪）** |
| **~ 黃色** | **修改（Modified）** | 現有欄位的值被修改（例如 `replicas: 1` 變更為 `replicas: 2`）。 |

---

## 🚀 實戰演練流程

當您要對您的 Kubernetes 服務進行調整時，建議養成以下 **三步驟黃金工作流**：

1. **修改設定**：編輯本地的 `values.yaml` 檔案。
2. **進行 Diff 預覽**：
   ```bash
   helm diff upgrade caddy-ingress caddy/caddy-ingress-controller -f caddy-ingress/values.yaml -n gateway
   ```
   *仔細檢查紅綠色輸出，確保變更完全符合預期。*
3. **正式套用**（確認無誤後才敲這條指令）：
   ```bash
   helm upgrade caddy-ingress caddy/caddy-ingress-controller -f caddy-ingress/values.yaml -n gateway
   ```