---
title: "Git 實戰筆記：自定義維護與 Docker-Compose 更新"
date: 2026-04-25 00:24:44 +0800
categories:
  - AI
tags:
  - Git
  - Docker
  - GitHub
  - CI/CD
---

這份筆記記錄了在維護 `hermes-agent` 自定義分支時的操作流程與背後的 Git 核心原理。

        
## 一、 核心任務：更新 Docker-Compose

        將本地測試用的 Image 改為 GitHub 倉庫自動構建的 Image，實現 CI/CD 自動化流程。

        
`# 修改前 (docker-compose.yml)
image: hermes:local
# 修改後 (指向 GitHub Container Registry)
image: ghcr.io/kuniakil/hermes-agent:v2026.4.16
```

        
## 二、 為什麼修改後一定要 Git Commit？

        
            **核心觀念：** Commit 是為了留下「確切的記錄」。

            即使檔案已經被 Git 追蹤，修改內容若不提交，就不會進入版本歷史，也無法同步到遠端倉庫（GitHub）。這能確保未來回推（Rollback）或搬移（Cherry-pick）時，設定是完整且可追溯的。
        
        
## 三、 Git 的三層架構：為什麼需要 git add？

        Git 設計了「暫存區」機制，讓開發者在提交前有最後一次挑選檔案的機會。

        

            - **工作目錄 (Working Directory)：** 你正在編輯檔案的地方（檔案變色/顯示 M）。

            - **暫存區 (Staging Area)：** 準備提交的套件裹箱。執行 git add` 就是把東西放進去。

            - **儲存庫 (Repository)：** 正式的歷史記錄。執行 `git commit` 就是把箱子封條。

        

        
## 四、 VS Code (IDE) 與 終端機 (CLI) 的對應

        
            
                
                    動作
                    終端機 (CLI) 指令
                    VS Code 操作
                
            
            
                
                    **狀態檢視**
                    `git status`
                    檢視左側 Source Control 面板的變色檔案
                
                
                    **放入暫存區**
                    `git add .` 或 `git add [檔名]`
                    點擊檔案旁邊的 **「+」** 號
                
                
                    **提交記錄**
                    `git commit -m "訊息內容"`
                    在 Message 框輸入文字，按 **「Commit」** 按鈕
                
                
                    **同步到雲端**
                    `git push`
                    按 **「Sync Changes」** 或 **「Push」**
                
            
        
        
## 五、 實戰操作流程總結

        
            
### 本次更新的完整步驟：

            

                - **修改檔案：** 編輯 `docker-compose.yml` 更改 Image 路徑。

                - **加入暫存：** 執行 `git add docker-compose.yml` (告訴 Git 這次要記錄這個變動)。

                - **提交紀錄：** 執行 `git commit -m "chore: update docker-compose to use GHCR image v2026.4.16"`。

                - **推送雲端：** 執行 `git push kuniakil my-config-v2026.4.16`。

            

        
        
## 六、 進階心得：如何處理 10K+ 的 Commit 雜訊？

        當你 Fork 活躍的大型專案時，VS Code 常顯示落後 Main 分支數千個 Commit。處理原則如下：

        

            - **無視背景音：** 10K+ 的數字是「別人的進度」，只要你的「地基」 (Release Tag) 沒變，就不會影響你的功能。

            - **鎖定基準：** 永遠以 `v2026.4.16` 這種 Tag 作為比較基準。

            - **搬家策略：** 出新版本時，開新分支並用 `git cherry-pick` 或 `git rebase` 將你的 Custom Config 搬過去即可。

        

        
            © 2026 Git Learning Notes - Personal Reference For WordPress