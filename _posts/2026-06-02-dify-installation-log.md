---
title: "Dify 安裝紀錄 (Install Log)"
date: 2026-06-02 09:00:00 +0800
categories:
  - Dify
  - Operations
tags:
  - dify
  - install
  - k8s
  - homelab
---

> 跟 `ARCHITECTURE.md` 互補：
> - **ARCHITECTURE.md** = 怎麼運作（元件、互動、資料流）
> - **本檔** = 裝到哪了（已完成、待辦、決策依據）
>
> 適用情境：交接、新機器重建、半年後回來看「當初為什麼這樣裝」。

---

## 🎯 TL;DR

✅ Dify 核心已可在 https://dify.3pm.lol 使用
✅ MiniMax provider 已通，聊天測試成功
⚠️ 還沒建任何 production app（測試用 chatbot 1 個）
⚠️ 知識庫、Agent、Workflow 全部 0 經驗

---

## 🛣️ 目標 (Goals)

1. **本地優先** — LLM App 平台自己架在 OrbStack Mac 上，文件/對話/API key 不出 home lab
2. **可移植** — 整包搬到 N100 伺服器時改 IP/host 即可重 deploy
3. **可串接** — 之後跟 n8n 串，組自動化 pipeline
4. **單一入口** — 所有路徑走同一個 Cloudflare Tunnel，跟其他服務一致

---

## 📅 里程碑 (Milestones)

### Day 1 (2026-06-01) — 基本部署

| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| 1.1 | 寫 `dify/dify-bundle.yaml` 初版 | ✅ | db / redis / broker / api / web / worker |
| 1.2 | 修正 image 名稱 `difyai/*` → `langgenius/*` | ✅ | commit `32cff14` |
| 1.3 | 加 nginx-proxy 解決 mixed-content | ✅ | ConfigMap 在 dify 命名空間內 |
| 1.4 | 透過 SQL 直接建 admin 帳號 | ✅ | 繞過安裝精靈（後來有副作用，見 2.4） |
| 1.5 | Cloudflare Tunnel 設 `dify.3pm.lol` | ✅ | 對外入口確立 |

### Day 2 (2026-06-02) — 修 bug & 補元件

| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| 2.1 | 修「failed to request plugin daemon」每秒跳 | ✅ | 加 `dify-plugin-daemon` Deployment（commit `33390cc`） |
| 2.2 | 修「Vector store type is not configured」 | ✅ | `VECTOR_STORE=pgvector` + Postgres 換成 `pgvector/pgvector:0.8.2-pg15`（commit `6c3c438`） |
| 2.3 | 修 plugin-daemon 啟動 env 踩坑（3 次 crash） | ✅ | `SERVER_KEY` / `DB_HOST` / `PLUGIN_DAEMON_TCP_HOST=0.0.0.0` 等 |
| 2.4 | 補 tenant RSA 私鑰（`PrivkeyNotFoundError`） | ✅ | 手動生成 keypair + 寫入 `~/dify-data/api-storage/privkeys/...`（順便修 `/app/api/storage` 沒掛 hostPath）|
| 2.5 | `/app/api/storage` 改 hostPath 持久化 | ✅ | commit `318923f`，未來重啟不丟私鑰 |
| 2.6 | 升級 Dify 1.14 後 conversation schema 驗證失敗 | ✅ | 用 `jsonb_set` 補 3 個必填欄位（`annotation_reply` / `more_like_this` / `agent_mode.prompt`）|
| 2.7 | MiniMax provider 安裝 + 填 API key | ✅ | plugin 從 marketplace 裝 |
| 2.8 | 建測試 chatbot「dify talk」+ 第一次成功對話 | ✅ | 訊息已存 db |

### Day 2 (下午) — 整理 & 清理

| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| 3.1 | 寫 `dify/ARCHITECTURE.md` | ✅ | commit `d633796`，12 章節（架構 + 使用 + 疑難排解）|
| 3.2 | HANDOVER.md 加 dify 條目 | ✅ | 同上 commit |
| 3.3 | 刪死掉的 Ingress (`dify-api-ingress`) | ✅ | commit `b8c6486`，本來就沒 ingress controller 在跑 |
| 3.4 | 刪 Cloudflare Tunnel `dify-api.3pm.lol` | ✅ | DNS 紀錄自動連動清掉 |

---

## ✅ 目前運作中 (Currently Working)

- [x] 對外 `https://dify.3pm.lol` 正常（Cloudflare → nginx-proxy → 後端）
- [x] 登入 / Settings / Model Provider 頁面
- [x] MiniMax provider 已認證，模型清單可選
- [x] Chatbot app 可建立、可發布、可聊
- [x] 串流回應（SSE）正常
- [x] 訊息持久化（`dify-db`）
- [x] 建議追問（`suggested-questions`）正常
- [x] Plugin daemon 持續運行，可裝/卸 plugin
- [x] pgvector 0.8.2 可用（知識庫 RAG 預備好）

---

## 🟡 半完成 (Partial)

- [ ] **測試用 chatbot「dify talk」** — 跑了 1 次對話就沒再動，prompt / 設定都是預設值
- [ ] **API Tokens** — 還沒在 apps 開過 API token，之後串 n8n 需要
- [ ] **Redis 密碼** — 目前是明文 `dify123456`，暫時可接受，未來要換

---

## ⬜ 還沒做 (Pending)

### P0 — 馬上要做的

- [ ] **決定第一個真實 use case**，並建對應 app
  - 候選：
    - 個人助理（接 MiniMax 對話）
    - 知識庫問答（餵自己的筆記/文件進 RAG）
    - Agent 自動化（搭配工具呼叫）
- [ ] **建 API token**，準備給 n8n / 其他服務串接
- [ ] **正式的 SECRET_KEY** — 目前 `dify-secret-key-change-me-in-production` 是 placeholder

### P1 — 有了 use case 之後

- [ ] **知識庫 (Knowledge Base)**
  - 文件來源：本機 PDF / Notion / 網頁
  - 走 pgvector（已就緒）
  - embedding model 設定（MiniMax 是否有提供？要測）
- [ ] **Workflow / Agent app**
  - 多步驟工具呼叫
  - 接 web search / code interpreter 之類的 tool
- [ ] **多模型供應商備援**
  - 至少加一個第二家（OpenAI / Ollama 本地）避免 MiniMax 掛了就全停
  - 推薦：**Ollama**（本地、免費、私密）— Mac 上跑 `ollama run llama3`，Dify 透過 OpenAI 相容 endpoint 接

### P2 — 系統強化

- [ ] **備份策略**
  - `~/dify-data/db`（PostgreSQL）— `pg_dump` 排程
  - `~/dify-data/api-storage/privkeys/`（**最關鍵**，沒這份 tenant 解密全炸）
  - 還原演練至少做一次
- [ ] **Secrets 管理**
  - 全部明文 env 不好——換成 K8s Secret 或 sealed-secrets
  - 至少 SECRET_KEY / DB_PASSWORD / REDIS_PASSWORD / PLUGIN_DAEMON_KEY 換掉
- [ ] **資源限制**
  - 各 deployment 加 `resources.requests/limits`
  - 防止 OOM 把整個 node 拖爆
- [ ] **監控**
  - Prometheus exporter 或至少 uptime check
  - 目前只看 `kubectl get pods` 知道活著

### P3 — 之後搬到 N100 時

- [ ] **Dify 1.x → 檢查 release notes** — 每次升級可能 schema 又變，要重跑補欄位 script
- [ ] **多 replica** — api/worker 可水平擴
- [ ] **HTTPS 內部通訊** — 目前 api 跟 plugin-daemon 走 HTTP，K8s 內部還好
- [ ] **對接企業 SSO**（如果 N100 上多帳號）

---

## 🤔 決定紀錄 (Decisions Log)

### 為什麼選 MiniMax 作為第一個 provider？
- 已有 API key，不花額外成本
- 中英文都強，之後寫中文 prompt 不用切模型
- 缺點：商業依賴、連國外網路慢

### 為什麼選 pgvector 而不是 Qdrant / Milvus？
- 已經有 Postgres 在跑了，多一個 vector store 服務就多一個維護點
- pgvector 對中小規模（< 100 萬向量）效能夠用
- 之後量大了再換 Qdrant

### 為什麼 Dify API 跟 Worker 用同一個 image？
- Dify 官方就這樣設計，`MODE` env 切換
- 我們只是 follow，不用自己 build custom image

### 為什麼不裝 nginx ingress controller？
- 已經有 cloudflared + nginx-proxy（in-cluster），沒必要再多一層
- 少一個元件少一個故障點

### 為什麼不做 HA？
- 單機 Mac 跑 homelab，HA 沒意義
- 真的要 HA 等搬到 N100 叢集再說

---

## 📊 資源使用（截至 2026-06-02 下午）

```
dify-api          1 vCPU, 1GB RAM
dify-worker       0.5 vCPU, 512MB
dify-plugin-daemon 0.5 vCPU, 512MB
dify-db           0.5 vCPU, 1GB RAM
dify-redis        0.2 vCPU, 256MB
dify-broker       0.2 vCPU, 256MB
dify-web          0.2 vCPU, 256MB
dify-nginx-proxy  0.1 vCPU, 64MB
─────────────────────────────────
總計 (理論上限)   ~3.2 vCPU, ~3.8GB RAM
```

實際用量要 `kubectl top pods -n dify` 才知道，沒設 limit 的話 K8s 不會主動量測。

---

## 🔗 相關檔案

- Manifest: `dify/dify-bundle.yaml`
- 架構說明: `dify/ARCHITECTURE.md`
- 本檔: `dify/INSTALL_LOG.md`
- 專案交接: `HANDOVER.md`
- Mobile kubeconfig: `mobile-kubeconfig.yaml`（連 `k8s.3pm.lol`，跟 Dify 入口不同）