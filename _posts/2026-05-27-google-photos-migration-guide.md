---
title: "逃離 Google 相簿：使用 Immich 進行無痛搬家與智慧去重"
date: 2026-05-27 12:30:00 +0800
categories: [Workflow, Self-hosted]
tags: [immich, google-photos, deduplication, backup]
---

自建 Immich 相簿後，最終的目標是將散落各地的回憶 —— 包括舊硬碟、多台舊手機，以及龐大的 Google Photos 雲端庫 —— 全部統整到一個乾淨的私有空間。

這篇文章記錄了如何利用 Immich 強大的 Hash 比對功能與開源工具，實現無痛搬家與完美的照片去重。

## 1. 為什麼選擇 Immich？(去重的魔法)

在整理老舊照片時，最大的噩夢就是「重複」。我們可能在不同的手機、不同的備份硬碟裡存了同一張照片，且檔名各不相同。

如果使用寫程式的 AI 助理（如 Claude 或一般腳本）來處理，往往效果不彰，因為它們不懂得多媒體檔案的特徵。而 Immich 的核心優勢在於：**它比對的是檔案的 Hash 值**。只要影像內容一致，不管檔名怎麼改，Immich 都會判定為重複，並只儲存一份實體檔案。

這意味著，我們可以無腦地將所有舊裝置的照片「全盤倒入」Immich，它會自動幫我們過濾、整理。

## 2. 第一階段：硬碟與多台舊手機匯入

### 舊手機策略
對於那些 8GB/12GB RAM 的退役旗艦機：
1. 分別安裝 Immich App 並登入同一帳號。
2. 啟動背景備份。
3. **注意事項**：為了避免伺服器（特別是像 8GB Mac 這種低配主機）因為同時進行大量人臉辨識與轉碼而過熱降頻，建議**一台跑完再跑下一台**。

### 舊硬碟匯入 (CLI 工具)
對於存放在硬碟裡的幾十 GB 老照片，網頁上傳容易崩潰。推薦使用 Immich 官方的命令列工具：
1. 安裝 CLI：`npm i -g @immich/cli`
2. 執行上傳：
   ```bash
   immich upload --key [API_KEY] --server https://photo.3pm.lol /您的/硬碟/照片資料夾
   ```
此工具會飛快地掃描目錄，遇到重複檔案自動跳過，極大節省了網路傳輸與伺服器處理的時間。

## 3. 第二階段：Google Photos 搬家 (Google Takeout)

Google 雖然不允許第三方軟體即時同步，但我們可以透過社群神器 `immich-go` 來處理 Google 的匯出檔案。

### 操作步驟：
1. **申請匯出**：前往 [Google Takeout](https://takeout.google.com/)，僅勾選「Google 相簿」並申請匯出。您會收到多個 `.zip` 壓縮檔。
2. **理解痛點**：Google 匯出的檔案會將照片與其 EXIF 資訊（如地理位置）拆分成 `.json` 檔案。如果直接上傳，照片會失去時間與地點。
3. **使用 immich-go**：這是一款專為此痛點開發的開源工具（[GitHub 連結](https://github.com/simulot/immich-go)）。
   * 它會自動解壓縮、配對 JSON 資訊。
   * 更重要的是，它同樣具備 **Hash 去重** 能力。如果 Google 上的照片已經在您的手機備份過了，它絕對不會重複上傳。
4. **執行指令**：
   ```bash
   immich-go -server https://photo.3pm.lol -key [API_KEY] upload [Takeout資料夾或壓縮檔]
   ```

## 4. 結語：數位資產的大一統

完成上述三個階段後，所有的照片都會在 Immich 裡匯流。它會補足 Google 壓縮過的畫質（如果您硬碟裡有原圖），過濾掉重複的檔案，並利用 AI 為您的人臉與物件進行分類。

在這個漫長的初次掃描過程結束後，您將獲得一個史無前例乾淨、且完全屬於您自己的家庭相簿，並且終於可以放心地清空 Google 雲端，停止支付每月的訂閱費用了！
