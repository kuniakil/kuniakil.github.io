---
title: "Cloudflare Worker VPN 設定指南"
date: 2026-04-20 00:49:26 +0800
categories:
  - 網路
tags:
  - Cloudflare
  - VPN
  - 網路
  - 部署
---

基於 cmliu 專案，實現全球極速 CDN 轉送

        
## 第一階段：Cloudflare 核心設定

        
            步驟 1. 建立數據庫 (KV)
            前往 **Storage & databases** > **Workers KV**。

            點擊 **Create Instance**，名稱填入 `CFO`。
        
        
            步驟 2. 建立運算服務 (Worker)
            前往 **Workers & Pages** > **Create** > **Worker**。

            名稱自訂，點擊 **Deploy**。隨後點擊 **Edit Code** (或 Start with Hello World)，刪除原本代碼，貼入 `cmliu` 專案的 `_worker.js`。
        
        
            步驟 3. 綁定身分與路徑 (關鍵)
            回到 Worker 頁面，進入 **Settings** > **Variables and Secrets**：
            

                - **變數 1：**新增 `ADMIN`，值設為你的後台登入密碼。

                - **變數 2 (KV 綁定)：**在下方點擊 Add binding。變數名填 `KV` (大寫)，空間選擇剛建的 `CFO`。

            

            完成後點擊 **Save and deploy**。
        
        
            步驟 4. 綁定自定義域名
            在 **Settings** > **Domains & Routes** 點擊 **Add Custom Domain**。

            輸入你的網址：`你的網域名稱`。
        
        
## 第二階段：獲取連線節點

        
            後台管理網址：https://你的網域名稱/admin
        
        進入後台後，請尋找 **「Clash 訂閱」** 或 **「V2Ray 訂閱」** 連結並複製。建議使用「Clash 格式」以獲得最佳的自動優選體驗。

        
## 第三階段：客戶端軟體下載 (Mac/Android)

        
### 1. MacBook (M1/M2/M3 系列)

        推薦使用 **Clash Verge Rev**，支援 Apple Silicon 原生架構。

        
            [前往 GitHub 下載](https://github.com/clash-verge-rev/clash-verge-rev/releases)
        
        **權限修復：**若提示檔案損毀，請在終端機輸入：

        sudo xattr -r -d com.apple.quarantine "/Applications/Clash Verge.app"
        
### 2. Android 手機

        推薦使用 **v2rayNG**，穩定且支援多種混淆協議。

        
            [前往 GitHub 下載](https://github.com/2dust/v2rayNG/releases)
        
        
## 第四階段：優化與故障排除

        

            - **連線超時：**請檢查 `ADMIN` 與 `KV` 是否正確儲存並執行了 `Save and deploy`。

            - **速度提速：**在後台 `/admin` 頁面更換「優選 IP」位址（推薦：`cf.090227.xyz`），然後更新軟體訂閱。

            - **安全建議：**請務必使用 HTTPS 訪問後台，避免密碼明文傳輸。

        

        
            技術支援：由 AI 根據 2026 年最新操作實作彙整 | 你的網域名稱 專屬手冊