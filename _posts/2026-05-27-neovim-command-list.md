---
title: "LazyVim 常用快捷鍵與指令速查表"
date: 2026-05-27 12:30:00 +0800
categories:
  - Neovim
tags:
  - Neovim
  - LazyVim
  - 快捷鍵
---

# 🚀 LazyVim 常用快捷鍵與指令速查表

> 💡 **提示**：`<Leader>` 鍵在 LazyVim 中預設是 **`Space`（空白鍵）**。

---

## 📂 檔案與目錄瀏覽 (Neo-tree)

| 快捷鍵 / 指令 | 功能說明 |
| :--- | :--- |
| `<Leader> + e` | 打開 / 關閉左側檔案樹選單 (Toggle Explorer) |
| `Ctrl + w + w` | 在左側檔案樹與右側文件之間**來回切換** |
| `Ctrl + h` | 游標直接跳到**左邊**選單 |
| `Ctrl + l` | 游標直接跳到**右邊**文件 |
| `h` / `l` | (在選單中) 折疊目錄 / 展開目錄 |
| `Backspace` | (在選單中) 回到上一層目錄 |
| `Enter` | (在選單中) 開啟選中的檔案 |

---

## 🔍 模糊搜尋與尋找 (Telescope)

| 快捷鍵 | 功能說明 |
| :--- | :--- |
| `<Leader> + f + f` | 尋找專案內檔案 (Find Files) |
| `<Leader> + /` | 在整個專案內搜尋文字 (Grep 關鍵字) |
| `<Leader> + ,` | 切換最近開啟過的檔案 (Switch Buffer) |
| `<Leader> + f + r` | 開啟最近編輯的檔案紀錄 (Recent Files) |

---

## 📄 分頁與緩衝區管理 (Buffers)

| 快捷鍵 | 功能說明 |
| :--- | :--- |
| `[ + b` | 跳到左邊的檔案分頁 (Previous Buffer) |
| `] + b` | 跳到右邊的檔案分頁 (Next Buffer) |
| `<Leader> + b + d` | **關閉目前檔案，但不退出編輯器** (Delete Buffer) |
| `<Leader> + b + D` | 強制關閉目前檔案（不儲存修改） |
| `<Leader> + b + o` | 關閉其他所有分頁，只保留當前檔案 |

---

## 🪟 視窗分割與管理 (Splits)

| 快捷鍵 | 功能說明 |
| :--- | :--- |
| `<Leader> + -` | 水平分割視窗 (Split window horizontally) |
| `<Leader> + \|` | 垂直分割視窗 (Split window vertically) |
| `Ctrl + hjkl` | 在上、下、左、右分割視窗間直接切換 |
| `Ctrl + 方向鍵` | 調整目前分割視窗的大小 |

---

## 🛠️ 編輯器系統指令

| 快捷鍵 / 指令 | 功能說明 |
| :--- | :--- |
| `<Leader> + q` | 退出 Neovim（若有未存檔會提示） |
| `:w` | 儲存檔案 |
| `:wa` | 儲存所有已修改的檔案 |
| `<Leader> + l` | 打開 Lazy 外掛管理器（升級/檢查外掛） |
| `<Leader> + m` | 打開 Mason 管理器（安裝 LSP/Linter/Formatter） |

---

## 📝 基礎移動技巧補充
* `Ctrl + ^` (或 `Ctrl + 6`)：在當前檔案與上一個檔案之間「極速切換」。
* 在檔案樹中按 `a` 可以直接新增檔案或資料夾；按 `d` 可以刪除。