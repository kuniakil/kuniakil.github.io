---
title: "Kronos 研究報告"
date: 2026-05-27 14:00:00 +0800
categories:
  - AI
  - 金融科技
tags:
  - Kronos
  - K-line
  - 時間序列
  - 基礎模型
---

## 1. 專案概述

**Kronos** 是第一個專為金融 K 线（K-line / 蜡烛图）設計的開源基礎模型（Foundation Model），由来自 45 個全球交易所、超過 120 億筆 K 线資料預訓練而成。該專案已接受 AAAI 2026。

### 核心解決的問題

現有的時間序列基礎模型（TSFM）在處理金融資料時存在以下缺陷：
- 金融資料噪音極高
- 價格波動具有獨特的規律
- 通用模型難以捕捉市場特定的語言

Kronos 提出一個兩階段框架來解決這些問題。

---

## 2. 系統架構

Kronos 的核心架構分為**兩大模組**：

### 2.1 Tokenizer（KronosTokenizer）

負責將連續的 OHLCV（開盤價、最高價、最低價、收盤價、成交量）資料離散化為 tokens。

#### 層級式量化（Hierarchical Quantization）

Tokenizer 採用 **Binary Spherical Quantizer (BSQ)** 將多維價格序列編碼為二級階層 token：

| 層級 | 名稱 | 位元數 | 說明 |
|------|------|--------|------|
| S1（粗粒度） | Coarse token | 8 bits | 編碼價格的主要變動方向 |
| S2（細粒度） | Fine token | 8 bits | 編碼價格的細微波動 |
| 總計 | 複合 token | 16 bits | 2¹⁶ = 65,536 種可能的市場狀態 |

**量化流程**：
1. 輸入 `x ∈ ℝ^(batch, seq_len, d_in)` 經過 `Linear → Embedding` 映射到隱空間
2. 經過數層 Transformer Encoder 提取特徵
3. 透過 `BSQuantizer` 將連續向量量化為 ±1 的二值編碼
4. 分成前半（S1）和後半（S2）兩部分
5. 各經過 Transformer Decoder 重建原始維度輸出

**BSQuantizer 核心機制**：
- 將每個 K 线 embedding 量化為一個長度為 `s1_bits + s2_bits` 的二值向量
- 使用可微分_entropy 損失（基於 Binary Spherical Quantization）來平衡：
  - **Commit loss**：確保量化前後不會偏離太遠
  - **Entropy penalty**：避免 codebook 使用不均勻，促進離散化多樣性

#### 編碼 / 解碼

```python
# 編碼：將 OHLCV 資料轉為 token indices
z_indices = tokenizer.encode(x)  # → [batch, seq_len]

# 解碼：將 token indices 還原為價格重建
x_reconstructed = tokenizer.decode(z_indices)  # → [batch, seq_len, d_in]
```

### 2.2 Transformer 主模型（Kronos）

一個 decoder-only 的 Transformer，輸入為 tokenizer 輸出的 hierarchical tokens，進行 next-token prediction 預訓練。

#### 模型配置

| 模型 | 參數量 | 層數 | 隱藏維度 | 注意力頭數 | 上下文長度 |
|------|--------|------|----------|------------|-----------|
| Kronos-mini | 4.1M | - | - | - | 2048 |
| Kronos-small | 24.7M | - | - | - | 512 |
| Kronos-base | 102.3M | - | - | - | 512 |
| Kronos-large | 499.2M | - | - | - | 512 |

#### 關鍵模組

**1. HierarchicalEmbedding**
- 將 S1 token 與 S2 token 分別透過 `nn.Embedding` 映射後拼接
- 再透過一個 `Linear(d_model*2, d_model)` 融合兩者

**2. TemporalEmbedding**
- 對時間戳（minute, hour, weekday, day, month）各自做 FixedEmbedding（正弦/餘弦位置編碼）或可學習 Embedding
- 全部加總後與 token embedding 融合

**3. TransformerBlock（× n_layers）**
- 使用 RMSNorm（而非 LayerNorm）
- Rotary Positional Embedding（RoPE）用於旋轉式位置編碼
- 含 Dropout 的 FeedForward Network（SwiGLU 激活）

**4. DependencyAwareLayer**
- 創新設計：在解碼 S2 token 時，condition on 對應的 S1 embedding
- 使用 Cross-Attention 機制，讓 S2 的預測受到 S1 的約束

**5. DualHead**
- `proj_s1`：輸出 S1 的 vocabulary logits
- `proj_s2`：在 DependencyAwareLayer 之後，輸出 S2 的 vocabulary logits

#### 前向傳播與損失

```
Loss = (CE(s1_logits, s1_targets) + CE(s2_logits, s2_targets)) / 2
```

### 2.3 自迴歸推理（Auto-regressive Inference）

推理時使用 teacher forcing 或 sampling 策略，逐步預測未來的 S1+S2 tokens：

```python
for i in range(pred_len):
    # 根據當前 context 預測下一個 S1
    s1_logits, context = model.decode_s1(tokens)
    sample_s1 = sample_from_logits(s1_logits)  # nucleus/top-k sampling

    # 以 S1 為條件預測 S2
    s2_logits = model.decode_s2(context, sample_s1)
    sample_s2 = sample_from_logits(s2_logits)

    # 將新 token 加入滑動窗口
    tokens = roll_and_append(tokens, sample_s1, sample_s2)
```

---

## 3. 核心類別：KronosPredictor

提供一個高層次的預測介面，封裝了所有繁瑣的細節。

```python
predictor = KronosPredictor(model, tokenizer, max_context=512)

# 單序列預測
pred_df = predictor.predict(df, x_timestamp, y_timestamp, pred_len=120)

# 批量預測（多序列並行）
pred_dfs = predictor.predict_batch(df_list, x_timestamp_list, y_timestamp_list, pred_len=120)
```

**內部流程**：
1. 檢查 `df` 是否包含 `['open', 'high', 'low', 'close']`（可選 `volume`, `amount`）
2. 計算時間特徵（minute, hour, weekday, day, month）
3. Z-score 正規化 + clipping（預防極端值）
4. 呼叫 `auto_regressive_inference` 執行自迴歸生成
5. 反正規化輸出預測結果

---

## 4. 使用方式

### 4.1 安裝

```bash
pip install -r requirements.txt
```

依賴：torch, einops, huggingface_hub, matplotlib, pandas, tqdm, safetensors

### 4.2 基本預測流程

```python
from model import Kronos, KronosTokenizer, KronosPredictor

# 1. 載入預訓練模型
tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
model = Kronos.from_pretrained("NeoQuasar/Kronos-small")

# 2. 初始化 Predictor
predictor = KronosPredictor(model, tokenizer, max_context=512)

# 3. 準備資料
df = pd.read_csv("your_kline_data.csv")
lookback = 400
pred_len = 120

x_df = df.loc[:lookback-1, ['open', 'high', 'low', 'close', 'volume', 'amount']]
x_timestamp = df.loc[:lookback-1, 'timestamps']
y_timestamp = df.loc[lookback:lookback+pred_len-1, 'timestamps']

# 4. 預測
pred_df = predictor.predict(
    df=x_df,
    x_timestamp=x_timestamp,
    y_timestamp=y_timestamp,
    pred_len=pred_len,
    T=1.0,        # 溫度參數
    top_p=0.9,    # nucleus sampling 閾值
    sample_count=1
)
```

### 4.3 批量預測

```python
pred_dfs = predictor.predict_batch(
    df_list=[df1, df2, df3],
    x_timestamp_list=[ts1, ts2, ts3],
    y_timestamp_list=[yts1, yts2, yts3],
    pred_len=120,
    sample_count=5,  # 多路徑採樣後平均
    verbose=True
)
```

---

## 5. 微調（Fine-tuning）流程

Kronos 支援針對自定義資料集的微調，分為兩個階段：

### Stage 1：微調 Tokenizer

```bash
torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_tokenizer.py
```

### Stage 2：微調 Predictor

```bash
torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_predictor.py
```

微調資料使用 Qlib 框架處理，支援 A 股市場資料的自動化前處理與 backtest 整合。

---

## 6. 實驗結果

根據論文 arXiv:2508.02739：

| 任務 | 指標 | 改進幅度 |
|------|------|----------|
| 價格預測 | RankIC | +93% vs 最佳 TSFM |
| 價格預測 | RankIC | +87% vs 非預訓練最佳 baseline |
| 波動率預測 | MAE | -9% |
| 合成資料生成 | Fidelity | +22% |

模型展現**零樣本（Zero-shot）能力**，可在不經任務特定微調的情況下執行多樣化的金融任務。

---

## 7. 目錄結構

```
Kronos/
├── README.md
├── requirements.txt
├── model/
│   ├── __init__.py
│   ├── kronos.py          # KronosTokenizer, Kronos, KronosPredictor, auto_regressive_inference
│   └── module.py          # TransformerBlock, BSQuantizer, RMSNorm, RoPE, HierarchicalEmbedding...
├── examples/
│   ├── prediction_example.py
│   ├── prediction_wo_vol_example.py
│   ├── prediction_batch_example.py
│   └── run_backtest_kronos.py
├── finetune/
│   ├── config.py
│   ├── train_tokenizer.py
│   ├── train_predictor.py
│   ├── qlib_data_preprocess.py
│   ├── dataset.py
│   └── utils/
├── webui/
│   └── app.py             # Gradio Web UI
└── tests/
```

---

## 8. 技術棧

- **Python**（主要語言）
- **PyTorch**（深度學習框架）
- **Hugging Face Transformers**（模型管理與 Hub 整合）
- **Qlib**（金融資料處理與回測，微調階段使用）
- **Einops**（張量操作）
- **Gradio**（可選 Web UI）

---

## 9. 主要創新點總結

1. **第一個金融 K 线基礎模型**：首個專為 K 线設計的 decoder-only 基礎模型
2. **階層式量化 tokenizer**：將 OHLCV 編碼為 S1/S2 兩層離散 tokens，保留價格動態與交易活動模式
3. **Dependency-Aware Layer**：S2 預測以 S1 為條件，模擬市場粗細粒度的依賴關係
4. **超大規模預訓練**：45 個交易所、120 億筆 K 线，覆蓋全球多市場
5. **零樣本能力**：無需任務特定微調即可執行預測、 volatility 估計、資料生成等多種任務