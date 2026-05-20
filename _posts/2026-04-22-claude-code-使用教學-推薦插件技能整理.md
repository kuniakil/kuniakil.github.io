---
title: "Claude Code 使用教學 & 推薦插件技能整理"
date: 2026-04-22 11:52:23 +0800
categories:
tags:
---

📚 整理自 X (Twitter) 上最熱門的 Claude Code 使用教學貼文，涵蓋：系統化學習路線、創始人使用技巧、以及社群推薦的必裝 Plugins、Skills 與 MCP Servers。

🎯 適合想從入門到進階的開發者，建議先收藏、反覆觀看。

## 📖 推薦學習資源

### ① DeRonin_ — 週末精通 Claude 指南 ❤️ 2285

[🔗 檢視原始推文](https://x.com/i/status/2045893227115344152)

一個週末精通 Claude 的路線圖，套件含 13 個官方學習資源連結：

  - **週六**：Claude 101 → 提示詞教學 → CLAUDE.md → Skills

  - **週日**：Claude Code → MCP → Routines → 構建第一個自動化

涵蓋 Claude 101、Claude Code 101、互動式提示詞教學、Skills 教學、MCP 接入、Anthropic Academy 免費課程等。

👉 這個指南涵蓋所有官方資源，全部免費，強烈建議跟著走一遍。

### ② Claude Code 創始人 Boris Cherny 30分鐘分享 ❤️ 2003

[🔗 檢視原始推文](https://x.com/i/status/2046264877703102753)

Claude Code 創始人親自分享使用技巧和工作流，號稱「看完勝過100個 YouTube 教學」。

📺 [影片直連](https://t.co/HU0fLO6XkP)

### ③ Claude Code 創始人的開發流程 ❤️ 155

[🔗 檢視原始推文](https://x.com/i/status/2046489912887980407)

來自創始人 Boris Cherny 的親身實踐：

  - 1️⃣ 先規劃，與 Claude 來回討論直到完美，才開始寫 code

  - 2️⃣ 創建 `CLAUDE.md` 檔案，讓 Claude 每次會話都了解你的專案、規則和風格

  - 3️⃣ 給 Claude 一種驗證自己工作的方式（後端：測試；UI：截圖）

  - 4️⃣ 在 `settings.json` 設定專案級權限規則，而非完全跳過許可

  - 5️⃣ 只有在這之後，才切換到自動接受模式

💡 關鍵心法：把 Claude 當作需要清晰指令、反饋循環和護欄的初級開發者，而不是神奇的黑盒子。

### ④ claude-code-best-practice 系統化指南 ⭐ 社區推薦

[🔗 檢視原始推文](https://x.com/i/status/2044352531338588245)

口號：「實踐造就完美 Claude」。86+ 實戰技巧，涵蓋：

  - Agents、Commands、Skills、Hooks、MCP Server、Subagents

  - 每個模組都有可直接使用的模板

  - 不是翻譯官方文檔，而是社區真實踩坑後的經驗總結

🔗 [GitHub 開源位址](https://github.com/shanraisshan/claude-code-best-practice)

### ⑤ 27分鐘深入學習影片 ❤️ 111

[🔗 檢視原始推文](https://x.com/i/status/2046402417609351381)

由 Claude Code 創始人 Boris Cherny 親自深入講解各個方面，適合想從源頭學透的人。

📺 [影片直連](https://t.co/627uMeThiP)

## 🧩 推薦安裝的 Plugins / Skills / MCP Servers

### 🔧 Skills

  
    
      名稱
      功能
      安裝指令
    
  
  
    
      **Superpowers**
      結構化思考，寫程式前先規劃再動手
      `npx skills add superpowers`
    
    
      **make-interfaces-feel-better**
      UI 優化：hover state、spacing、tabular numbers、字體一致性
      `npx skills add jakubkrehel/make-interfaces-feel-better`
    
    
      **Antigravity Awesome Skills**
      1200+ 現成技能合集，最大規模的社群技能庫之一
      社群技能市場取得
    
    
      **Awesome Claude Code**
      社群技能、hooks、斜槓命令大全
      社群資源
    
  

### 🔌 MCP Servers

  
    
      名稱
      功能
      連結
    
  
  
    
      **claude-context** (zilliztech)
      將整個程式碼庫作為即時上下文，解決大型專案 Agent 不了解的痛點
      [GitHub](https://github.com/zilliztech/claude-context)
    
    
      **n8n-MCP**
      連接 400+ n8n 整合，擴展工作流自動化能力
      —
    
    
      **WordPress Playground MCP**
      官方 WordPress MCP server，支援 PHP 執行和網站管理
      `npx @wp-playground/mcp`
    
    
      **RoundtableSpace MCP Auto-Install**
      自動發現並安裝最適合你技術棧的 MCP servers
      [GitHub](https://github.com/RoundtableSpace/mcp-auto-install)
    
  

### 🚀 全端工具推薦

  
    
      名稱
      功能
    
  
  
    
      **Claude Mem**
      跨 session 持久化記憶，不用每次重新教 Claude 你的程式碼庫
    
    
      **LightRAG**
      Graph + vector RAG，讓 Claude 理解大型程式碼結構
    
    
      **UI UX Pro Max**
      50+ 樣式、161 配色、99 UX 規範，防止 Claude 生成醜 UI
    
    
      **VoiceMode MCP**
      透過 Whisper + Kokoro 實現自然語音對話
    
    
      **Claude Marketplaces**
      Claude Code 擴展超市，可按安裝量 / GitHub star 排序熱門擴展
    
  

## 🔗 實用連結總整理

  - 📘 [Claude Code 官方文檔](https://docs.anthropic.com/en/docs/claude-code)

  - 📘 [Claude Code 完整文檔](https://docs.anthropic.com/en/docs/claude-code/overview)

  - 📙 [claude-code-best-practice](https://github.com/NousResearch/claude-code-best-practice) — 86+ 實戰技巧開源專案

  - 📙 [Awesome Claude Code](https://github.com/successful-devs/awesome-claude-code) — 社群聖經

  - 📙 [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) — 1000+ Agent 技能精選

  - 📙 [Claude Marketplaces](https://claude.market) — 擴展超市

  - 📙 [Claude Code Ultimate Guide](https://github.com/successful-devs/claude-code-ultimate-guide) — 23K+ 行文檔、219 模板

  - 📙 [claude-context](https://github.com/zilliztech/claude-context) — 程式碼庫即時上下文

  - 📙 [Claude Code GitHub](https://github.com/anthropics/claude-code)

  - 🎓 [Anthropic Academy](https://console.anthropic.com/academy) — 13 門官方免費課程

### 💡 建議學習順序

推薦按照以下順序學習，吸收效果最佳：

  - 先看 **Boris Cherny 30分鐘分享** 了解整體概念

  - 跟著 **DeRonin 週末指南** 的路線圖實作一遍

  - 建立自己的 `CLAUDE.md` 並學習使用 **Superpowers** 結構化思考

  - 根據需求安裝對應的 **MCP Server**（如 claude-context）

  - 探索 **Claude Marketplaces** 發現更多擴展

整理自 X (Twitter) · 資料時間：2026年4月