---
title: "在 8GB RAM Mac 上使用 K8s 部署 Immich 私有相簿"
date: 2026-05-27 12:00:00 +0800
categories: [Kubernetes, HomeLab]
tags: [immich, k8s, orbstack, self-hosted, photos]
---

在將 Jellyfin、Nextcloud 與 WordPress 成功遷移至 Kubernetes 後，我面臨了最大的挑戰：部署目前最強大的自託管相簿方案 —— **Immich**。

這篇文章記錄了如何在資源極度受限的 8GB RAM Mac (OrbStack) 上，成功運行這個由多個微服務組成的龐然大物。

## 1. 架構挑戰與解決方案

Immich 是一個分散式系統，包含 Server、Machine Learning (AI)、Postgres (Vector) 與 Redis。要在 8GB RAM 的環境下運行，我們必須精打細算。

### 資源優化策略
*   **AI 限制**：Machine Learning 模組在進行人臉辨識時非常耗費資源。在 K8s 的 Deployment 中，我們強制設定了 `resources.limits.memory: "1Gi"`，防止 AI 榨乾 Mac 的記憶體導致死機。
*   **儲存分離**：放棄 K8s 原生的 PV/PVC，改用 `hostPath` 直接掛載 `/Users/mlee/immich/upload`。這不僅節省效能，未來若要遷移至 N100 等專用伺服器，只需拷貝資料夾即可。
*   **版本控制**：針對 2026 年 Immich 的資料庫底層更新，我們精確鎖定了 `ghcr.io/immich-app/postgres:14-vectorchord0.4.3` 映像檔，確保資料庫初始化成功。

## 2. 部署過程中的「坑」

在部署過程中，遇到了幾個值得記錄的技術問題：

1.  **啟動失敗 (CrashLoopBackOff)**：
    初期因為映像檔標籤使用 `latest` 導致拉取失敗。改用明確的穩定版本 `v1.105.1` 後才成功。
2.  **502 Bad Gateway 與 Port 變更**：
    容器成功啟動後，外部 Cloudflare Tunnel 卻報錯 502。經查閱日誌發現，Immich 2.x 版本將預設的內部通訊 Port 從 `3001` 改為了 **`2283`**。修改 K8s Service 與 Cloudflare 設定後即順利連通。
3.  **微服務衝突**：
    新版的 Immich 將 Server 與 Microservices 合併為同一映像檔。如果不加參數啟動，它可能會進入微服務模式而非網頁伺服器模式，導致無法提供 HTTP 服務。

## 3. 現狀與體驗

目前 `photo.3pm.lol` 已穩定上線。在區域網路下，從手機備份照片的速度極快。雖然初次進行 AI 掃描與影片轉碼時，Mac 會出現明顯的卡頓（這是預期內的「技術債」處理），但一旦舊照片處理完畢，日常使用將非常順暢。

最棒的是，Immich 內建的 **Hash 去重功能**，完美解決了多台舊手機中重複照片的問題，為未來的「數位資產大一統」奠定了基礎。
