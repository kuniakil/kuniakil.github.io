# 文章編輯指南

## Repo 資訊

- **Repo URL**: https://github.com/kuniakil/kuniakil.github.io
- **Branch**: `main`
- **靜態檔案目錄**: `assets/img/`

---

## 新增文章

### 1. 建立文章檔案

在 `_posts/` 目錄建立 `.md` 檔案，檔名格式：

```
YYYY-MM-DD-標題.md
```

例如：`2026-05-20-新文章.md`

### 2. 檔案格式

```markdown
---
title: "文章標題"
date: 2026-05-20 10:00:00 +0800
categories:
tags:
---

文章內容，使用 Markdown 格式。
```

### 3. 圖片放置

若文章有圖片，先下載到 `assets/img/`，然後在文章中引用：

```markdown
![圖片說明](/assets/img/圖片檔名.png)
```

---

## 提交與發布

### 在 Mac 本機（已有 PAT）

```bash
cd /Users/mlee/3pm.lol/kuniakil.github.io

git add .

git commit -m "你的修改說明"

git push
```

### 在 Docker 容器或 VPS

容器內需要設定 PAT 環境變數：

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxx"

git remote set-url origin https://${GITHUB_TOKEN}@github.com/kuniakil/kuniakil.github.io.git

git add .

git commit -m "你的修改說明"

git push
```

### PAT 權限需求

- `repo` - Full repository access (含 push 權限)

---

## 注意事項

1. **圖片對應**：每篇文章的圖片需確認對應正確
   - 5G 文章用 `5g-01.jpeg` ~ `5g-04.jpeg`
   - VPN 文章用 `vpn-01.jpeg` ~ `vpn-07.png`

2. **Build 失敗**：若 GitHub Actions 失敗，檢查：
   - Markdown 語法是否正確
   - front matter 格式是否正確
   - 圖片路徑是否存在

3. **URL 格式**：Jekyll 會自動將 `2026-05-20-標題.md` 轉換為 `/posts/標題/` 的 URL

---

## 文章範本

```markdown
---
title: "你的文章標題"
date: $(date '+%Y-%m-%d %H:%M:%S') +0800
categories:
tags:
---

## 第一段標題

內容...

## 第二段標題

內容...
```

---

## 疑難排解

### GitHub Actions 失敗
- 檢查 `_posts/` 下的 Markdown 語法
- 確認 front matter 的 `title`、`date` 格式正確

### 圖片顯示不出來
- 確認 `assets/img/` 目錄有該圖片
- 確認文章中的路徑正確（如 `/assets/img/xxx.jpeg`）

### 認證失敗
- Mac 本機：確認已設定 GitHub credential
- Docker/VPS：需要設定 `GITHUB_TOKEN` 環境變數