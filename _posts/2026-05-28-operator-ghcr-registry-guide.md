---
title: "GHCR (GitHub Container Registry) 操作風險說明"
date: 2026-05-28 10:00:00 +0800
categories:
  - DevOps
  - Docker
tags:
  - GHCR
  - Container Registry
  - Docker
  - GitHub Actions
---

## 背景

2026-05-28 在升級 v2026.5.26 時，誤刪了 GHCR 的無標籤 versions，導致所有舊版 image manifests 全部斷裂，必須從頭重建。

## GHCR 資料模型

```
┌──────────────────────────────────────────────────────┐
│ 有 tag 的 version (例: "v2026.5.26")                  │
│ 類型: Manifest list / index                          │
│ 內容: 指向其他 version 的 digest 清單                 │
│   manifests: [                                        │
│     { digest: sha256:BBBB, platform: linux/amd64 },   │
│     { digest: sha256:CCCC, platform: linux/arm64 }    │
│   ]                                                   │
└──────────────────────────────────────────────────────┘
         ▲                               ▲
         │ (引用)                        │ (引用)
         │                               │
┌─────────────────────┐       ┌─────────────────────┐
│ 無 tag 的 version   │       │ 無 tag 的 version   │
│ digest: sha256:BBBB │       │ digest: sha256:CCCC │
│ (amd64 manifest)    │       │ (arm64 manifest)    │
└─────────────────────┘       └─────────────────────┘
         ▲                               ▲
         │ (引用)                        │ (引用)
    layer blobs (無 tag)            layer blobs (無 tag)
```

**對應關係：**
- **Tag → Manifest list version (有 tag)**
- **Manifest list → Platform manifests (無 tag)**
- **Platform manifests → Image layers (無 tag)**

## 錯誤假設

```
❌ 誤以為：無 tag = 失敗/殘留版本可以刪除
✅ 實際上：無 tag = 實際 image data (manifest + layers)
           有 tag = 只是指標 (manifest list)
```

## 安全刪除原則

1. **嚴格區分「有 tag」和「無 tag」的版本**
2. **只刪「有 tag 且已知是失敗 build」的 version**
3. **絕對不刪「無 tag」的版本**（除非明確知道該 layer 沒被任何 manifest 引用）
4. 刪除前先 `docker manifest inspect <tag>` 確認該 tag 解析沒問題，再確認要刪的 version 是否被其他 tags 依賴

## 如何查版本對應

```bash
# 查看 tag 指向的完整結構（manifest list → platform manifests → layers）
docker manifest inspect ghcr.io/<owner>/<repo>:<tag> --verbose

# 快速看某個 tag 的所有 digest
docker manifest inspect ghcr.io/<owner>/<repo>:<tag>
```

## 實際對應範例（v2026.5.26）

從 `docker manifest inspect --verbose ghcr.io/kuniakil/openclaw:2026.5.26` 的輸出：

```
ghcr.io/kuniakil/openclaw:2026.5.26
    │
    ├── [manifest list / index]
    │   "digest": "sha256:941ece724fee..."  ← 這也是個 "無 tag 的 version"
    │
    ├── [amd64 image manifest, 無 tag]
    │   "digest": "sha256:d505b98a5c26..."     ← amd64 的實際 image
    │   layers: [sha256:84a2afebaf4d..., sha256:24c453db3621..., ...]
    │
    ├── [arm64 image manifest, 無 tag]
    │   "digest": "sha256:c6300995dc77..."     ← arm64 的實際 image
    │   layers: [sha256:eb04ef52de3a..., sha256:43a62db3740c..., ...]
    │
    ├── [attestation manifest (SBOM+SLSA), 無 tag]
    │   "digest": "sha256:b14dd2c5557b..."     ← amd64 attestation
    │
    └── [attestation manifest (SBOM+SLSA), 無 tag]
        "digest": "sha256:bf217d402979..."     ← arm64 attestation
```

衍生 tag 的對應關係：
```
2026.5.26         → manifest list → amd64 manifest + arm64 manifest
2026.5.26-amd64  → amd64 manifest（直接）
2026.5.26-arm64  → arm64 manifest（直接）
2026.5.26-slim   → 同 2026.5.26-amd64（都是 amd64）
```

**重要發現：**
- `sha256:4f4fb700ef54...` (size 32) 這個空白 layer 同時出現在 amd64 和 arm64 的 manifest 中
- 如果砍了某個 "無 tag" version，會影響所有引用它的 tags
- 但 attestation (SBOM/provenance) 是獨立的，刪了不影響 image 本身

## 完整清理壞 build 的流程

假設 `v2026.5.19` 這個 build 是錯的，要完整刪乾淨：

**Step 1：** 找出 v2026.5.19 所有相關 tag
```bash
docker manifest inspect ghcr.io/kuniakil/openclaw:2026.5.19
docker manifest inspect ghcr.io/kuniakil/openclaw:2026.5.19-amd64
docker manifest inspect ghcr.io/kuniakil/openclaw:2026.5.19-arm64
docker manifest inspect ghcr.io/kuniakil/openclaw:2026.5.19-slim
```
每個都會告訴你它的 digest。

**Step 2：** 收集所有要刪的 digest
```
v2026.5.19         → digest: ??? (manifest list)
v2026.5.19-amd64   → digest: sha256:AAAA (amd64 manifest)
v2026.5.19-arm64   → digest: sha256:BBBB (arm64 manifest)
v2026.5.19-slim    → 可能等於 AAAA (與 amd64 共用)
+ 每個 attestation 的 digest
```

**Step 3：** 從 GHCR UI 或 API 刪除
- 每一個 "有 tag" 的 version 可以個別刪除（只是刪指標，很安全）
- "無 tag" 的 version（AAAA、BBBB 等）要確認不再被任何其他 tag 引用再刪
- 建議：只刪有 tag 的 version，讓無 tag 的 image data 保留；未來確認沒人用再砍

**Step 4：** 驗證
```bash
docker manifest inspect ghcr.io/kuniakil/openclaw:v2026.5.19
# 預期：manifest unknown
```

## 刪除行為

| 刪除類型 | 影響 |
|---------|------|
| 刪「有 tag」的 version | 該 tag 失效；其他 tags 和 images 不受影響 |
| 刪「無 tag」的 version | 所有引用該 digest 的 manifests 全部斷裂；所有相關 tags 變成 `manifest unknown` |

## 事故記錄

- 日期：2026-05-28
- 影響：v2026.5.19, v2026.5.12, v2026.5.7, v2026.5.6, v2026.5.5, v2026.5.2 全部失效
- 修復：重新 trigger 全部版本的 Docker build
- 教訓：沒有 git 那樣的回溯機制，GHCR 刪了就是刪了

## 重建狀態（截至 2026-05-29）

| Version | Status | Notes |
|---------|--------|-------|
| v2026.5.26 | ✅ Ready | Run 26586942243, all manifests OK |
| v2026.5.19 | ❌ Deleted | 需重建 |
| v2026.5.12 | ❌ Deleted | 需重建 |
| v2026.5.7 | ❌ Deleted | 需重建 |
| v2026.5.6 | ❌ Deleted | 需重建 |
| v2026.5.5 | ❌ Deleted | 需重建 |
| v2026.5.2 | ❌ Deleted | 需重建 |
| v2026.4.27 | ❌ Deleted | 需重建 |
| v2026.4.24 | ❌ Deleted | 需重建 |
| v2026.4.22 | ❌ No branch | 無法重建（無 my-config-v2026.4.22） |