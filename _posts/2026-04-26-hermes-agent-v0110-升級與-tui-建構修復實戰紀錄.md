---
title: "Hermes-Agent v0.11.0 升級與 TUI 建構修復實戰紀錄"
date: 2026-04-26 09:21:00 +0800
categories:
tags:
---

在 2026 年 4 月 25 日，我們完成了 Hermes-Agent 從 `v2026.4.16` 至 `v2026.4.23` (核心版本 v0.11.0) 的深度升級。本次升級的重點在於全新 React/Ink TUI 的適配，以及解決 GitHub Actions 多架構建構中的各種「雷區」。

    
        
## 1. 核心挑戰：失蹤的 TUI 組件

        升級後，TUI 介面頻繁報錯：

        `Cannot find module ... @hermes/ink/dist/ink-bundle.js`

        調查發現，雖然官方重寫了 TUI，但其 Dockerfile 對於 **npm workspace** 的處理不夠強健，導致關鍵的渲染引擎檔案在建構時未能產出。

    
    
        
## 2. 修正五部曲：Dockerfile 的演進

        為了解決建構失敗與組件缺失，我們對 Dockerfile 進行了五次重大迭代：

        

            - 
                132352f76 **解決依賴複製**：修復 `npm install` 失敗，確保 `ui-tui/packages` 的本地依賴被正確複製。
            

            - 
                2f171065f **重構建構順序**：將 `COPY . .` 提前。這解決了建構產物被 `.dockerignore` 規則意外排除的「靜默失敗」問題。
            

            - 
                024d5ad4e **強制執行 esbuild**：不再依賴自動化工具，顯式進入目錄產出 `ink-bundle.js`，並加入路徑驗證邏輯。
            

            - 
                30bd7dec0 **對齊官方標準**：加入 `tini` 進程守護，並實作 `chmod -R a+rX` 全域權限修正，確保模組對所有使用者可讀。
            

            - 
                9254ac84b **修復指令路徑**：全域安裝 `typescript` 並改用 `npx tsc`，解決了最後的 `Exit 127` (指令找不到) 問題。
            

        

    
    
        
## 3. CI/CD 優化：Multi-arch 解決方案

        針對 GitHub Actions 免費版 7GB RAM 的限制，我們實作了以下優化：

        

            - **Matrix Build**：將 `amd64` 與 `arm64` 拆分到獨立 Job 執行，享受各自獨立的記憶體配額。

            - **Manifest Merge**：使用 `docker buildx imagetools` 合併多架構影像，徹底解決 OOM 崩潰。

            - **Layer Cache 優化**：透過指令拆分與檢查點，防止損壞的映像檔被推送到 GHCR。

        

    
    
        
## 4. 最終成果與待解決問題

        目前最新影像已成功部署。雖然 **Docker TUI 底層限制** 導致的 `Shift+Enter` 換行失效問題仍存在（已提交官方 Issue），但 Hermes 的核心功能與 UI 穩定度已達到最佳狀態。

        
            Build Status: SUCCESS
            Image Size: ~2.6GB
        

    
    
    紀錄於 2026-04-25 · 由 Gemini CLI 輔助修復