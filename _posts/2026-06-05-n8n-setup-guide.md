---
layout: post
title: "n8n 本地化 RAG 系統安裝與建置手冊"
date: 2026-06-05 20:35:00 +0800
categories: [Automation, Kubernetes]
tags: [n8n, k8s, docker, rag, setup]
---

本手冊彙整了本系統從零開始建置、容器打包、Kubernetes 部署、背景服務啟動以及問題排查的完整實戰流程。

---

## 🛠️ 步驟 1：建置自訂 n8n Docker 映像檔

由於官方映像檔缺少機器學習推論庫，且 isolated-vm 需要特定的全域套件，我們建立自訂 Dockerfile。

### 1. Dockerfile 設計
在專案根目錄下建立 `n8n/Dockerfile`：
```dockerfile
FROM node:22.16-bullseye-slim

# 安裝基本工具及編譯環境（isolated-vm 需要）
RUN apt-get update && apt-get install -y \
    python3 make g++ curl sqlite3 bash \
    && rm -rf /var/lib/apt/lists/*

# 全域安裝指定版本 n8n 以及機器學習套件
RUN npm install -g n8n@2.22.6 @xenova/transformers --unsafe-perm

# 設定 HuggingFace 模型快取資料夾
ENV HF_HOME=/home/node/.n8n/.cache/huggingface
RUN mkdir -p $HF_HOME && chown -R 1000:1000 /home/node

USER 1000
WORKDIR /home/node
ENTRYPOINT ["n8n"]
CMD ["start"]
```

### 2. 映像檔編譯與推送
```bash
docker build -t ghcr.io/kuniakil/n8n:2.22.6-custom ./n8n
docker push ghcr.io/kuniakil/n8n:2.22.6-custom
```

---

## ☸️ 步驟 2：Kubernetes 資源配置

建立 `n8n-bundle.yaml`。為避免機器學習推論與向量比對導致 OOM，請配置充足的記憶體。

### 1. 關鍵環境變數設定
```yaml
env:
  - name: NODE_FUNCTION_ALLOW_BUILTIN
    value: "crypto,child_process,http" # 放行 http 以便 n8n 呼叫外部向量服務
  - name: NODE_FUNCTION_ALLOW_EXTERNAL
    value: "*"
  - name: N8N_BLOCK_EXTERNAL_EXECUTION
    value: "false"
  - name: HF_HOME
    value: "/home/node/.n8n/.cache/huggingface"
  - name: N8N_USER_FOLDER
    value: "/home/node" # 修正 n8n 自動拼接 .n8n 導致空白 DB 的 bug
  - name: N8N_RUNNERS_HEARTBEAT_INTERVAL
    value: "600" # 增加 Task Runner 容許心跳時間，防止超載時斷線
```

### 2. 資源限額與儲存掛載
- **資源限額**：`requests.memory: "1Gi"`, `limits.memory: "6Gi"` (避免計算向量時被 K8s 砍掉)。
- **持久化**：使用 `hostPath` 掛載 `/Users/mlee/n8n-data` 至容器的 `/home/node/.n8n`。

---

## 🚀 步驟 3：部署背景向量伺服器

向量伺服器負責將 query 向量化與計算 Cosine Similarity。

1. **腳本配置**：將 `embed-server.js` 放置於 `/Users/mlee/n8n-data/.cache/embed-server.js`。
2. **啟動腳本**：建立 `startup-server.sh` 於同資料夾下，透過 `nohup` 將伺服器綁定在容器背景運行：
   ```bash
   nohup node embed-server.js >> embed-server.log 2>&1 &
   ```
3. **在 n8n 中啟動**：
   在 n8n 中新增一個工作流，使用 `Execute Command Plus` 節點執行：
   ```bash
   bash /home/node/.n8n/.cache/startup-server.sh
   ```

---

## 🗃️ 步驟 4：離線資料庫寫入工具 (`update-chatbot.js`)

為了避免每次更新 Code Node 都需要登入 n8n 網頁，我們編寫了 [update-chatbot.js](file:///Users/mlee/kubernetes/n8n/update-chatbot.js)。

在每次修改完本地的 `n8n-rag-query.js` 後，於主機端執行：
```bash
node n8n/update-chatbot.js
kubectl rollout restart deployment/n8n -n n8n
```
腳本會使用 Python 自動將程式碼安全寫入 SQLite 的 `workflow_entity` 和 `workflow_history` 表中，並在重啟 pod 後立即生效。

---

## 🚨 常見排障指引 (Troubleshooting)

### 1. `SQLITE_IOERR: disk I/O error`
- **原因**：掛載主機目錄（hostPath）時，SQLite 的 WAL 與 SHM 暫存檔可能發生鎖定衝突或損壞。
- **解法**：
  ```bash
  rm -f /Users/mlee/n8n-data/database.sqlite-shm
  rm -f /Users/mlee/n8n-data/database.sqlite-wal
  kubectl rollout restart deployment/n8n -n n8n
  ```

### 2. `Unexpected module status 5. Cannot require() ES Module`
- **原因**：在 n8n 沙箱中直接 require ESM 套件（如 `@xenova/transformers`）會拋出此錯誤。
- **解法**：不直接在 n8n 載入機器學習套件，改用異步 `http` 向背景運行的 `embed-server.js` 發送 POST `/rag` 請求。

### 3. `listen EADDRINUSE: address already in use 127.0.0.1:18789`
- **原因**：舊的 `embed-server` 進程未被釋放，佔用了端口。
- **解法**：進入 pod 殺死舊進程：
  ```bash
  kubectl exec -n n8n deployment/n8n -- bash -c "kill -9 34" # 根據實際 PID 調整
  ```
