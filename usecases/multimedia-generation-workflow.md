---
last_validated: 2026-05-25
validated_by: claw-info-docs-contrib
---

# 多媒體生成整合工作流程（Image / Video / Music）

## TL;DR

- OpenClaw 的 `image_generate`、`video_generate`、`music_generate` 可以在同一個 agent workflow 中協調使用
- 適合內容創作、產品展示、社群媒體素材包等場景
- 善用 `image` 參數串接：圖片 → 影片 first_frame，音樂 → 影片 audioRef
- 使用 `instrumental: true` 生成背景音樂，避免歌詞干擾畫面
- 設定 `outputFormat` 與 `aspectRatio` 統一素材規格，減少後製成本

## 解決的問題 / 使用情境

### 情境 1：部落格自動配圖 + 背景音樂 + 宣傳短片

部落格作者撰寫文章後，agent 自動：
1. 根據文章主題生成封面圖片
2. 生成 30 秒輕音樂作為背景
3. 以封面圖為 first_frame 生成 15 秒宣傳短片
4. 將音樂作為 audioRef 嵌入影片

### 情境 2：產品多角度展示

電商上架新產品，agent 自動：
1. 從產品圖生成透明背景 PNG（`background: transparent`）
2. 生成 3 張不同風格的展示圖
3. 以展示圖為 reference_image 生成 360° 旋轉影片
4. 配上品牌主題音樂

### 情境 3：社群媒體素材包

行銷團隊需要 Instagram + TikTok 素材，agent 一次生成：
- 1:1 方形圖片（Instagram 貼文）
- 9:16 直式短影片（TikTok/Reels）
- 15 秒背景音樂（無版權疑慮）

## 核心概念

### 三種媒體工具的差異與適用場景

```
+----------------+----------------+----------------+----------------+
| 工具           | 輸出           | 最佳用途       | 耗時           |
+----------------+----------------+----------------+----------------+
| image_generate | 靜態圖片       | 封面、插圖、   | 數秒至數十秒   |
|                | (PNG/JPEG/WEBP)| 產品圖、素材   |                |
+----------------+----------------+----------------+----------------+
| video_generate | 影片檔案       | 動態展示、     | 數十秒至數分鐘 |
|                | (MP4/WebM)     | 宣傳片、教學   |                |
+----------------+----------------+----------------+----------------+
| music_generate | 音訊檔案       | 背景音樂、     | 數十秒         |
|                | (MP3/WAV)      | 主題曲、音效   |                |
+----------------+----------------+----------------+----------------+
```

### Provider Fallback 策略

OpenClaw 的媒體工具內建多 provider fallback：

```
使用者請求
    |
    v
image_generate ──→ 優先嘗試 provider A
    |                      |
    |                      v
    |              失敗？→ 自動 fallback 到 provider B
    |                      |
    v                      v
   成功                  成功
```

- **image_generate**：OpenAI (gpt-image-2/gpt-image-1.5) → Google (Imagen) → 其他
- **video_generate**：Qwen (Wan2.6) → Google (Veo) → 其他
- **music_generate**：Google (Lyria) → 其他

### 成本與品質權衡

| 策略 | 品質 | 成本 | 速度 | 適用場景 |
|------|------|------|------|----------|
| 高品質優先 | 最高 | 高 | 慢 | 品牌宣傳、產品發表 |
| 平衡模式 | 中上 | 中 | 中等 | 日常內容、部落格 |
| 快速迭代 | 中等 | 低 | 快 | 原型測試、草稿 |

## 操作指引

### 前置條件

1. **API Keys**：確保至少一個 media provider 已設定
   - OpenAI API key（圖片/影片）
   - Google AI API key（圖片/影片/音樂）
   - 其他 provider 依需求設定

2. **Workspace 空間**：媒體檔案會儲存在 OpenClaw 管理的 media 目錄，確保有足夠空間

3. **Timeout 設定**：影片生成較耗時，建議在 `video_generate` 中設定 `timeoutMs: 300000`（5 分鐘）

### 最小可行範例：單一 Agent 生成圖片 + 音樂 + 影片

```yaml
# 範例：為「夏日海灘」主題生成完整素材包

# 步驟 1：生成封面圖片
image_generate:
  prompt: "夏日海灘日落，棕櫚樹剪影，溫暖色調，適合部落格封面"
  aspectRatio: "16:9"
  outputFormat: "png"
  quality: "high"

# 步驟 2：生成背景音樂
music_generate:
  prompt: "輕快夏日海灘風格背景音樂，無人聲，放鬆氛圍"
  instrumental: true
  durationSeconds: 30
  format: "mp3"

# 步驟 3：生成宣傳短片（使用步驟 1 的圖片作為 first_frame）
video_generate:
  prompt: "夏日海灘動態場景，海浪輕輕拍打，棕櫚樹隨風搖曳"
  image: "{{ step1_output }}"  # 引用步驟 1 產出的圖片路徑
  imageRoles: ["first_frame"]
  audioRef: "{{ step2_output }}"  # 引用步驟 2 產出的音樂路徑
  aspectRatio: "16:9"
  durationSeconds: 15
  resolution: "1080P"
```

### 進階範例：Subagent 分工

對於複雜專案，使用多個 subagent 分工：

```
+---------------------+
|   主 Agent (導演)    |
|  - 拆解需求           |
|  - 分配任務           |
|  - 整合成果           |
+----------+----------+
           |
    +------+------+
    |             |
    v             v
+--------+   +--------+
| 視覺   |   | 音訊   |
| Agent  |   | Agent  |
| - 圖片 |   | - 音樂 |
| - 影片 |   | - 音效 |
+--------+   +--------+
    |
    v
+--------+
| 剪輯   |
| Agent  |
| - 合成 |
| - 輸出 |
+--------+
```

**視覺 Agent 任務**：
```yaml
image_generate:
  prompt: "產品展示圖，白色背景，專業攝影風格"
  background: "transparent"  # 需要透明背景時使用
  outputFormat: "png"
  count: 3  # 生成 3 張不同角度
```

**音訊 Agent 任務**：
```yaml
music_generate:
  prompt: "科技感電子音樂，適合產品展示"
  instrumental: true
  durationSeconds: 60
  format: "wav"  # 無損音質供後製
```

**剪輯 Agent 任務**：
```yaml
video_generate:
  prompt: "產品 360 度展示，流暢轉場"
  images: ["{{ visual_agent_output1 }}", "{{ visual_agent_output2 }}", "{{ visual_agent_output3 }}"]
  imageRoles: ["reference_image", "reference_image", "reference_image"]
  audioRef: "{{ audio_agent_output }}"
  aspectRatio: "16:9"
  durationSeconds: 30
```

## 最佳實務

### 如何選擇 Provider

| 需求 | 推薦 Provider | 原因 |
|------|--------------|------|
| 高品質圖片 | OpenAI gpt-image-2 | 細節最豐富 |
| 透明背景 | OpenAI gpt-image-1.5 | 專用 transparent 模式 |
| 快速圖片 | Google Imagen | 速度快、成本低 |
| 高品質影片 | Qwen Wan2.6 | 動作流暢、物理合理 |
| 長影片 | Google Veo | 支援較長 duration |
| 背景音樂 | Google Lyria | 樂器分離度好 |

### 錯誤處理策略

當某個媒體生成失敗時：

```yaml
# 策略 1：降級品質重試
image_generate:
  prompt: "相同主題"
  quality: "medium"  # 從 high 降為 medium

# 策略 2：更換 provider
image_generate:
  prompt: "相同主題"
  model: "google/imagen-3"  # 指定備援 provider

# 策略 3：使用靜態替代動態
# 若 video_generate 失敗，改為生成多張圖片製作 GIF
```

### 儲存與命名慣例

建議在 prompt 中或 workflow 中統一命名：

```
project-name/
├── images/
│   ├── cover_16x9.png
│   ├── product_01.png
│   └── product_02_transparent.png
├── audio/
│   ├── bgm_30s.mp3
│   └── theme_60s.wav
└── video/
    ├── promo_15s.mp4
    └── showcase_30s.mp4
```

## Troubleshooting

### Timeout 錯誤

**症狀**：`video_generate` 或 `music_generate` 回報 timeout
**解決**：
- 增加 `timeoutMs` 參數（預設可能僅 30 秒，建議設為 300000）
- 縮短 `durationSeconds`
- 降低 `resolution`（1080P → 720P）

### Provider 不支援特定格式

**症狀**：`outputFormat: "webp"` 被某些 provider 拒絕
**解決**：
- 查閱各 provider 支援的格式列表
- 使用 `png` 作為最通用格式
- 後製轉換（OpenClaw 會自動處理部分轉換）

### Quota Exceeded

**症狀**：API 回報 quota 用盡
**解決**：
- 啟用多 provider fallback（自動）
- 檢查各 provider 的配額狀態
- 考慮使用 `quality: "low"` 減少 token 消耗

### 音畫不同步

**症狀**：影片與背景音樂長度不匹配
**解決**：
- 確保 `music_generate` 的 `durationSeconds` ≥ `video_generate` 的 `durationSeconds`
- 或使用影片工具的 `audio: true` 讓 provider 自動生成匹配音訊

## 相關連結

- [image_generate 工具文件](../docs/tools/image_generate.md)
- [video_generate 工具文件](../docs/tools/video_generate.md)
- [music_generate 工具文件](../docs/tools/music_generate.md)
- [#602 - 多媒體生成工作流程（母 Issue）](https://github.com/thepagent/claw-info/issues/602)
- [STYLE_GUIDE.md - 文件寫作規約](./STYLE_GUIDE.md)

## 版本紀錄

| 日期 | 版本 | 說明 |
|------|------|------|
| 2026-05-25 | 1.0 | 初版，涵蓋 image/video/music 整合工作流程 |
