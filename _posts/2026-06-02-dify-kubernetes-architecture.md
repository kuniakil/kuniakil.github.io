---
title: "Dify on Kubernetes — 架構、運作與操作手冊"
date: 2026-06-02 10:00:00 +0800
categories:
  - Dify
  - Architecture
tags:
  - dify
  - k8s
  - architecture
  - homelab
---

> 範圍：只涵蓋本 repo 的 `dify/` 部署（dify-bundle.yaml + nginx-proxy configmap + 此文件）。
> 對外入口：`https://dify.3pm.lol`（Cloudflare Tunnel → dify-nginx-proxy）。
> 完整 manifest：`dify/dify-bundle.yaml`。

---

## 1. 為什麼自己架 Dify

Dify 是開源 LLM App 平台（聊天機器人、RAG 知識庫、Agent workflow 都用它編）。
雲端版有免費額度，但自架的好處：
- 資料不出 home lab（文件、對話紀錄、API key 都在自己 Mac 上）
- 客製化（plugin、模型供應商、儲存路徑）
- 跟 n8n 串接方便（之後做 workflow）

---

## 2. 元件總覽

部署了 8 個 Pod，全部在 `dify` namespace：

| 元件 | 角色 | 技術 | 備註 |
|------|------|------|------|
| **dify-db** | 主資料庫 | PostgreSQL 15 + pgvector | 存 app、conversation、message、tenant key、文件區塊 embedding |
| **dify-redis** | 快取 + pub/sub | Redis 7 | SSE 串流通道、session、LLM response cache、Celery broker |
| **dify-broker** | 訊息佇列 | RabbitMQ | 給 worker 排非同步任務（建議問題、文件索引、webhook） |
| **dify-api** | 主要 API 服務 | Python / Flask + gunicorn | 處理所有 HTTP 請求、跟 LLM 對接 |
| **dify-worker** | 背景任務 worker | 跟 api 同 image，跑 `MODE=worker` | 從 broker 拉任務執行（長任務、批次） |
| **dify-web** | 前端 | Next.js (Node) | UI，build 完用 nginx 服務靜態檔 |
| **dify-nginx-proxy** | 反向代理 | nginx | 把 `/console/api/ /api/ /v1/ /` 路由到正確後端 |
| **dify-plugin-daemon** | Plugin runtime | **Go**（其他都是 Python） | 安裝/隔離/執行 plugin，呼叫外部 LLM API |

> 📌 **特別注意**：`dify-api` 和 `dify-worker` 共用 `langgenius/dify-api:latest` 同一個 image，
> 只是 entrypoint 跑不同：`MODE=api` 起 Flask，`MODE=worker` 起 Celery worker。
> 好處是 deploy/升級一次到位，schema 完全一致。

---

## 3. 網路拓樸

```
   你的瀏覽器
       │ HTTPS (dify.3pm.lol)
       ▼
   Cloudflare Tunnel (gateway namespace)
       │ HTTP
       ▼
┌────────────────────────────┐
│  dify-nginx-proxy :80      │  ← 唯一對外的 K8s service (LoadBalancer)
└────────────────────────────┘
       │
   ┌───┴────┬──────────┬─────────────┐
   ▼        ▼          ▼             ▼
 /         /api/  /console/api/    /v1/
   │        │          │             │
   ▼        ▼          └─────┐       │
dify-web   dify-api ◄────────┘       │
   │           │                    │
   │           ├──► dify-db ─► pgvector (vector search)
   │           ├──► dify-redis (cache + SSE pub/sub)
   │           ├──► dify-broker ─► dify-worker
   │           └──► dify-plugin-daemon ─► MiniMax API
   │
   └─ 直接 build 好的靜態檔（不需要再跟 api 對話時）
```

---

## 4. 一次 chat 訊息的完整路徑

你打一句「你好」：

1. **瀏覽器** POST `https://dify.3pm.lol/console/api/apps/{id}/chat-messages`
2. **Cloudflare** 透過 tunnel 轉到 K8s → **dify-nginx-proxy** port 80
3. **nginx-proxy** 看到 `/console/api/` → 轉給 **dify-api:8080**（內部是 5001）
4. **dify-api**：
   - 從 cookie 認出你是 admin，查 `dify-db` 取 user/conversation/app config
   - 拿 conversation 的 `override_model_configs` 決定用哪個模型（MiniMax-m3）
   - 組 prompt → 呼叫 **dify-plugin-daemon** `POST /dispatch/llm/invoke`
5. **dify-plugin-daemon**：
   - 載入 MiniMax plugin（隔離環境）
   - 用你的 API key 打 MiniMax API
   - 串流 token 回傳給 dify-api
6. **dify-api**：
   - 邊收 token 邊 SSE 推回瀏覽器（透過 nginx-proxy）
   - 完整回應存進 `dify-db.messages.answer`
   - 順便 enqueue 一個「生成建議追問」任務到 **dify-broker**
7. **dify-worker**：
   - 從 broker 拉到任務
   - 再呼叫 plugin-daemon 一次生成建議問題
   - 結果寫回 db
8. 瀏覽器接著 GET `suggested-questions` → dify-api 從 db 撈出來顯示

---

## 5. 三個「為什麼」

- **為什麼要有 nginx-proxy？**
  Dify web 從瀏覽器發 `/console/api/*` 跟 `/api/*`，
  沒這層代理會撞 CORS / mixed-content。我們的 dify-web 服務是內部 ClusterIP，
  瀏覽器不會直接打到——所有 API 請求都透過 nginx-proxy 同源轉發。

- **為什麼 api 跟 worker 用同個 image？**
  同 codebase，只是 `MODE` 不同。這樣 deploy/升級一次到位，schema 完全一致。

- **為什麼 plugin-daemon 是 Go 不是 Python？**
  Plugin 是「裝進來跑使用者程式碼」的安全風險。
  Dify 用 Go 開 child process + seccomp 沙箱隔離 plugin，
  避免一個爛 plugin 把整個 API 容器拖下水。
  Python 端的 API 只負責 IPC。

---

## 6. 資料流向一覽

```
              ┌─ pgvector: vector similarity search
              │
dify-db ◄─────┤  tables: apps, conversations, messages,
              │          datasets, embeddings, tenants, api_tokens
              │  files:  RSA private keys (/app/api/storage/privkeys/)
              │
dify-redis ◄──┤  pub/sub: SSE stream fan-out
              │  cache:   tenant_privkey, model credentials
              │  queue:   Celery broker(worker alternative)
              │
dify-broker ◄─┤  queue:   workflow runs, async tasks
              │           (suggested-questions, document indexing)
              │
dify-plugin-daemon ◄─ storage: plugin files, signatures
              │  cluster: master election (用 Redis)
              │
              └─ outbound: MiniMax / OpenAI / Anthropic APIs
```

---

## 7. Storage 路徑一覽（hostPath）

全部在 Mac 本機的 `~/` 下，未來遷移直接 tar 帶走：

| 用法 | hostPath | 對應容器路徑 |
|------|----------|-------------|
| Postgres 資料 | `/Users/mlee/dify-db` | `/var/lib/postgresql/data` |
| Redis 資料 | `/Users/mlee/dify-redis` | `/data` |
| Dify API runtime（log、cache） | `/Users/mlee/dify-api` | `/home/dify` |
| Dify API storage（**RSA private key 在這**） | `/Users/mlee/dify-api-storage` | `/app/api/storage` |
| Dify worker runtime | `/Users/mlee/dify-worker` | `/home/dify` |
| Plugin daemon 檔案 | `/Users/mlee/dify-plugin-daemon` | `/app/storage` |

> ⚠️ `/Users/mlee/dify-api-storage/privkeys/<tenant_id>/private.pem` 是解密的私鑰，
> 沒這檔案 = tenant 任何 API 操作都 500。**備份時這個目錄是關鍵**。

---

## 8. 環境變數關鍵設定

`dify-api` 必設（沒設會 runtime 炸）：

- `VECTOR_STORE=pgvector` — 沒設的話 `/console/api/datasets/retrieval-setting` 直接 500
- `PLUGIN_DAEMON_URL=http://dify-plugin-daemon:5002`
- `PLUGIN_DAEMON_KEY=dify-plugin-daemon-key` — 跟 daemon 的 `SERVER_KEY` 對齊
- `SECRET_KEY=...` — 改自己的，否則 token 不安全
- `DB_HOST/PORT/USERNAME/PASSWORD/DATABASE` — 指向 `dify-db`
- `REDIS_HOST/PORT/PASSWORD` — 指向 `dify-redis`
- `CONSOLE_WEB_URL=https://dify.3pm.lol`
- `APP_WEB_URL=https://dify.3pm.lol`

`dify-plugin-daemon` 必設（每個都是踩過坑的）：

- `DB_HOST` (**不是** `DB_HOSTNAME`，會 silently 拒絕)
- `SERVER_KEY` (**不是** `PLUGIN_DAEMON_KEY`)
- `PLUGIN_DAEMON_TCP_HOST=0.0.0.0`
- `PLUGIN_DAEMON_TCP_PORT=5003`
- `PLUGIN_REMOTE_INSTALLING_HOST=0.0.0.0`
- `PLUGIN_REMOTE_INSTALLING_PORT=5003`
- `PLUGIN_WORKING_PATH=/app/storage/plugins`
- `PLUGIN_PACKAGE_PATH=/app/storage/packages`
- `PLUGIN_MEDIA_PATH=/app/storage/media`
- `DIFY_INNER_API_URL=http://dify-api:8080`
- `DIFY_INNER_API_KEY` / `DIFY_INNER_API_KEY_FOR_PLUGIN` — 跟 api 那邊對齊

---

## 9. 第一次使用流程

### 9.1 安裝模型供應商

1. 右上 **Settings → Model Provider**
2. 找 provider → 點 **Install**（plugin 模式）
3. 安裝完後同一頁填 API key
4. MiniMax 走 OpenAI 相容協議，plugin 會自動讀

### 9.2 建第一個 Chatbot

1. 頂部 **Studio** → 右上 **Create from Blank**
2. 選 **Chatbot** → 命名 → **Create**
3. 上方 **Orchestrate** 頁面 → 找 **Inference Model** 下拉 → 選 MiniMax 模型
4. 點 **Publish** 發布
5. 切回右側 **Debug / Preview** 就能打字聊了
6. 想正式對外：右上 **API Access** 看 endpoint，或 Cloudflare tunnel 開個子網域

### 9.3 建知識庫（RAG）

1. 頂部 **Knowledge** → **Create Knowledge**
2. 選資料來源（檔案 / Notion / 網頁爬蟲）
3. Embedding model 會用 tenant default（`tenant_default_models` 表格存）
4. 索引建好後在 Chatbot 的 context 區掛上 → 就有 RAG

---

## 10. 日常運維

### 10.1 怎麼看 log

```bash
# API 服務
kubectl logs -n dify -l app=dify-api --tail=100 -f

# Worker（看背景任務）
kubectl logs -n dify -l app=dify-worker --tail=100 -f

# Plugin daemon（看 plugin 載入 / LLM 呼叫）
kubectl logs -n dify -l app=dify-plugin-daemon --tail=100 -f

# 看所有 pod 狀態
kubectl get pods -n dify
```

### 10.2 怎麼重啟 / 更新

```bash
# 套用整包
kubectl apply -f dify/dify-bundle.yaml

# 只想重啟某個服務
kubectl rollout restart deployment/dify-api -n dify
kubectl rollout restart deployment/dify-worker -n dify
kubectl rollout restart deployment/dify-plugin-daemon -n dify
```

### 10.3 怎麼看 DB 內容

```bash
DB_POD=$(kubectl get pod -n dify -l app=dify-db -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n dify $DB_POD -- psql -U dify -d dify

# 常用查詢
\dt                                          # 列出所有表
SELECT * FROM apps;                          # 列出所有 app
SELECT id, query, answer FROM messages 
  ORDER BY created_at DESC LIMIT 5;          # 最近的對話
SELECT * FROM tenant_default_models;         # 預設模型設定
```

### 10.4 怎麼看 redis / rabbitmq 內容

```bash
REDIS_POD=$(kubectl get pod -n dify -l app=dify-redis -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n dify $REDIS_POD -- redis-cli
> KEYS tenant_privkey:*        # 看私鑰快取
> FLUSHDB                       # 清快取（解 schema 變更的 stale 問題）

BROKER_POD=$(kubectl get pod -n dify -l app=dify-broker -o jsonpath='{.items[0].metadata.name}')
# RabbitMQ 管理介面在 :15672，預設 guest/guest（容器內部網路限定）
```

### 10.5 升級 Dify 版本

1. 備份 `/Users/mlee/dify-db` 和 `/Users/mlee/dify-api-storage`（私鑰！）
2. 改 `dify-bundle.yaml` 裡的 image tag（`langgenius/dify-api:latest` → `:1.x.y`）
3. `kubectl apply -f dify/dify-bundle.yaml`
4. 看 `kubectl get pods -n dify` 全綠
5. **第一次升級前先看 release notes**——Dify 1.14 加了 `annotation_reply`、`more_like_this`、`agent_mode.prompt` 三個 schema 必填欄位，舊 conversation 沒這些會 500（見第 11 節）

---

## 11. 踩過的坑（疑難排解）

### 11.1 「failed to request plugin daemon」每秒跳

**原因**：`dify-plugin-daemon` 沒部署。
**修法**：套 `dify-bundle.yaml` 裡的 plugin-daemon section，api/worker 加 `PLUGIN_DAEMON_URL`。
**為什麼 `:latest` 失敗**：該 image 沒 `:latest` tag，要用 `:main-local`。

### 11.2 「Vector store type is not configured」

**原因**：`VECTOR_STORE` env 沒設，或 Postgres 沒裝 pgvector extension。
**修法**：
- api/worker 加 `VECTOR_STORE=pgvector`
- Postgres image 改 `pgvector/pgvector:0.8.2-pg15`（不是 `postgres:15-alpine`）

### 11.3 「InternalServerError」+ 右上角瘋狂轉圈

**原因 1**：tenant 沒 RSA 私鑰（手動建 admin 帳號繞過安裝精靈時會這樣）。
**修法**：
```bash
API_POD=$(kubectl get pod -n dify -l app=dify-api -o jsonpath='{.items[0].metadata.name}')
DB_POD=$(kubectl get pod -n dify -l app=dify-db -o jsonpath='{.items[0].metadata.name}')
TENANT_ID="<你的 tenant uuid>"

# 1) 生成 keypair
kubectl exec -n dify $API_POD -- python <<EOF
from Crypto.PublicKey import RSA
import os
priv = RSA.generate(2048); pub = priv.publickey()
target = f'/app/api/storage/privkeys/$TENANT_ID'
os.makedirs(target, exist_ok=True)
with open(f'{target}/private.pem','wb') as f: f.write(priv.export_key())
with open('/tmp/new_pub.pem','w') as f: f.write(pub.export_key().decode())
EOF

# 2) 寫回 DB
kubectl cp dify/$API_POD:/tmp/new_pub.pem /tmp/new_pub.pem
kubectl cp /tmp/new_pub.pem dify/$DB_POD:/tmp/new_pub.pem
kubectl exec -n dify $DB_POD -- psql -U dify -d dify -c \
  "UPDATE tenants SET encrypt_public_key = pg_read_file('/tmp/new_pub.pem') WHERE id = '$TENANT_ID';"

# 3) 清 redis 負快取
kubectl exec -n dify dify-redis-774df44f56-ps8gg -- redis-cli FLUSHDB
```

**原因 2**：`/app/api/storage` 沒掛 hostPath，pod 重啟私鑰就丟。
**修法**：bundle 已修，永久化到 `/Users/mlee/dify-api-storage`。

**原因 3**（升級 Dify 1.14 後）：conversation 的 `override_model_configs` 缺三個 schema 必填欄位。
**修法**：
```bash
DB_POD=$(kubectl get pod -n dify -l app=dify-db -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n dify $DB_POD -- psql -U dify -d dify -c "
UPDATE conversations SET override_model_configs = jsonb_set(
  jsonb_set(
    jsonb_set(
      override_model_configs::jsonb,
      '{annotation_reply}', '{\"enabled\": false}'::jsonb, true),
    '{more_like_this}',   '{\"enabled\": false}'::jsonb, true),
  '{agent_mode,prompt}', '\"\"'::jsonb, true)
::text
WHERE override_model_configs IS NOT NULL
  AND (override_model_configs::jsonb ? 'annotation_reply' = false
    OR override_model_configs::jsonb ? 'more_like_this' = false
    OR override_model_configs::jsonb->'agent_mode' ? 'prompt' = false);
"
```

### 11.4 「混合內容 / Mixed Content」

**原因**：瀏覽器 HTTPS 頁面呼叫 HTTP API。
**修法**：套 `dify-nginx-proxy`，所有路徑都從同源出去。

### 11.5 plugin-daemon 一直 CrashLoopBackOff

常見原因 & 對應 env 修法：
- `ServerKey required` → 設 `SERVER_KEY`（不是 `PLUGIN_DAEMON_KEY`）
- `DBHost required` → 設 `DB_HOST`（不是 `DB_HOSTNAME`）
- `plugin remote installing host is empty` → 設 `PLUGIN_REMOTE_INSTALLING_HOST=0.0.0.0`
- `plugin working path is empty` → 設 `PLUGIN_WORKING_PATH=/app/storage/plugins`
- bind 不到 `dify-plugin-daemon:5002` → 改成 `0.0.0.0`，k8s service DNS 沒辦法 bind

---

## 12. 容量 / 擴展規劃

- **dify-api**：可以水平擴（多 replica），純 stateless
- **dify-worker**：可以水平擴，從 broker 搶任務
- **dify-plugin-daemon**：stateless，但要做 master election（單機 OK，多節點要小心）
- **dify-db / redis / broker**：單機夠用就好，要 HA 的話換成 managed 服務

預估資源（單節點 OrbStack Mac）：
- dify-api: 1 vCPU, 1GB RAM
- dify-worker: 0.5 vCPU, 512MB
- dify-plugin-daemon: 0.5 vCPU, 512MB
- dify-db: 0.5 vCPU, 1GB RAM（隨資料量成長）
- dify-redis: 0.2 vCPU, 256MB
- dify-broker: 0.2 vCPU, 256MB
- dify-web: 0.2 vCPU, 256MB
- dify-nginx-proxy: 0.1 vCPU, 64MB