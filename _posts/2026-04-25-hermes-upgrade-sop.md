---
title: "Hermes-Agent 升級 SOP：從閱讀到完成的完整流程"
date: 2026-04-25 10:00:00 +0800
categories:
  - AI
tags:
  - Hermes
  - Docker
  - Git
  - Workflow
---

## 升級指令範本

下次需要升級時，請直接複製以下文字貼給 AI：

> 「請讀取 `UPGRADE_STRATEGY.md`。現在 `hermes-agent` 已發布新版本 **[在此填入新版本號，例如 v2026.5.1]**。
>
> 請依照 SOP 執行以下動作：
> 1. 從目前的 `my-config-v2026.4.23` 分支切出新分支（命名格式：`my-config-版本號`）。
> 2. 將我目前的 **8 個自定義 Commit** Rebase 到新版本上。
> 3. **特別注意：** 務必保留我優化過的 `Dockerfile`（含記憶體限制）以及 `.github/workflows/ghcr-publish.yml`（含 Multi-arch 分流建構與 Manifest 合併功能）。
> 4. 更新 `docker-compose.yml` 中的映像檔標籤至新版本。
> 5. 完成後推送到 GitHub 遠端 `kuniakil`。」

---

## 目前自定義功能清單

- **Docker 優化**：`NODE_OPTIONS` 記憶體限制、`npm install` 參數優化。
- **CI/CD 神器**：GitHub Actions Matrix 分流建構 + Digest 合併 (解決 OOM)。
- **環境適配**：時區設定 (`Asia/Taipei`)、互動模式 (`tty: true`)、私有 GHCR 路徑。