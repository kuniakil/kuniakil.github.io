---
layout: post
title: "dify jina concurrency limit postmortem"
date: 2026-06-12 00:00:00 +0800
categories: [Concepts]
tags: []
---
# 📝 Dify 知識庫 Jina AI 併發限制修復紀錄 (Postmortem)

> **背景**：為了釋放本機 Mac 的記憶體（RAM），我們停用了本機運行的 Ollama 向量服務（`nomic-embed-text`），改用雲端免費的 **Jina AI Embedding API**。然而在同步大文件時，遭遇了嚴格的併發限制問題，此文件記錄了問題排查與徹底解決的歷程。

---

## 🚨 問題現象 (Symptoms)

在執行 `sync_to_dify.js` 同步文件至 Dify 知識庫時，部分段落較多（文件較大）的 Markdown 檔案（如 `caddy-ingress-migration.md` 等）會隨機向量化失敗，Dify 後台資料庫顯示以下錯誤：
```
[models] Rate Limit Error, Concurrency limit exceeded: 2/2 concurrent requests. Wait for pending requests to complete before sending new ones.
```

---

## 🔍 原因分析 (Root Cause)

1. **Jina AI 免費額度限制**：Jina AI 免費 Key 限制最大併發（同時處理的請求數）為 `2`。
2. **Dify 內建多線程併發**：
   * Dify 內建的 High Quality 向量化任務在拆分文件（Chunking）後，會將多個段落同時交給一個線程池進行向量化。
   * 查看 Dify 核心源碼 `/app/api/core/indexing_runner.py` 第 605 行，發現其硬編碼（Hardcoded）了 `max_workers = 10`：
     ```python
     max_workers = 10
     if dataset.indexing_technique == IndexTechniqueType.HIGH_QUALITY:
         with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
     ```
   * 這意味著，即使外部腳本是一個檔案一個檔案上傳，**Dify 內部仍會同時啟動 10 個線程並行向 Jina AI 發送請求**，這會瞬間打破 Jina AI 的 2 併發限制，導致長文件高機率向量化失敗。

---

## 🛠️ 解決方案 (Resolution Plan)

我們採用了 **「解鎖環境變數控制」+「K8s 運行時熱插拔掛載」** 的方案，徹底解決了此問題：

### 1. 修改 Dify 核心向量化線程池
我們將 Dify 的 `indexing_runner.py` 拷貝至本地，並將硬編碼的 `max_workers` 改為讀取環境變數 `INDEXING_MAX_WORKERS`：

```python
# 引入 os 模組
import os

# 修改線程數為環境變數控制，默認值為 10
max_workers = int(os.environ.get('INDEXING_MAX_WORKERS', 10))
```

### 2. 在 K8s 部署中掛載此 Patch 並限制併發數
修改 [dify/dify-bundle.yaml](file:///Users/mlee/kubernetes/dify/dify-bundle.yaml)，為 `dify-api` 和 `dify-worker` 兩個 Deployment 加入以下更改：
*   **環境變數限制**：設定 `INDEXING_MAX_WORKERS` 為 `"1"`。
*   **動態掛載 Patch**：利用 K8s `hostPath` Volume 指向本地 [dify/indexing_runner.py](file:///Users/mlee/kubernetes/dify/indexing_runner.py)，並使用 `subPath` 單檔掛載覆蓋容器內的 `/app/api/core/indexing_runner.py`：

```yaml
# 容器 volumeMounts 設置
volumeMounts:
- name: indexing-runner-patch
  mountPath: /app/api/core/indexing_runner.py
  subPath: indexing_runner.py

# 卷定義 (指向 Mac 本地專案目錄下的 patched 檔案)
volumes:
- name: indexing-runner-patch
  hostPath:
    path: /Users/mlee/kubernetes/dify
    type: Directory
```

### 3. 優化 n8n 同步腳本的狀態檢測
修改 [n8n/sync_to_dify.js](file:///Users/mlee/kubernetes/n8n/sync_to_dify.js)，將先前盲目的「固定延遲 8 秒」升級為 **「主動狀態輪詢（Polling）」**。
*   每次上傳文件後，腳本會每隔 3 秒查詢該文件的 `indexing_status`。
*   必須等到該文件在 Dify 後台完全轉為 `completed`（或 `error`）後，才繼續處理下一個檔案。
*   **雙重保障**：藉由「外部檔案序列化」+「內部段落單線程化（max_workers=1）」，完全保證對 Jina AI 的併發請求數維持在 `1`，徹底告別併發 Rate Limit。

---

## 📈 修復驗證 (Verification Results)

重新套用 K8s 設定後，再次執行同步，51 份 Wiki 文件（包括長文件）**全部以 `Completed` 狀態成功向量化導入 Dify 知識庫**，完美解決！

> [!TIP]
> *   **Ollama 資源釋放**：本機的 Ollama 服務已順利 `scale --replicas=0` 關閉，節省了 Mac 大約 4GB 以上的 RAM。
> *   **手動/自動觸發**：我們在 n8n 的自動同步工作流中加入了 `Manual-Trigger` 節點，現在可隨時在 n8n 控制台點擊「手動同步」，且即使 n8n 關閉，亦可在終端機運行 `node n8n/sync_to_dify.js` 完成同步。
