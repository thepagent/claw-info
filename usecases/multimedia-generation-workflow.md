---
last_validated: 2026-05-25
validated_by: tboydar-agent
---

# 多媒體生成整合工作流程

## TL;DR

- 單一 agent 可協調 `image_generate`、`video_generate`、`music_generate` 產出完整素材包
- 善用 provider fallback 與參數調校，平衡品質、成本與速度
- 透明背景圖片（`background: transparent`）是影片合成的前置利器
- Subagent 分工可並行處理視覺、音訊、剪輯，縮短總耗時
- 永遠為單一媒體生成失敗設計 fallback，避免整條 workflow 中斷

---

## 解決的問題 / 使用情境

| 情境 | 需求 | 產出 |
|------|------|------|
| 內容創作代理 | 部落格配圖 + 背景音樂 + 宣傳短片 | 圖片 + 音樂 + 影片 |
| 產品展示 | 從產品圖生成多角度展示 | 影片 + 配樂 |
| 社群媒體素材包 | Instagram / TikTok 一次性素材 | 圖片 + 短影片 + 背景音 |

**核心痛點：**
- 三種媒體工具參數各異，agent 難以一次寫對
- 個別生成失敗時，整條 workflow 容易中斷
- 成本與品質難以權衡（高品質圖片 vs 快速影片）
- 產出檔案缺乏命名慣例，後續整理困難

---

## 核心概念

### 三種媒體工具的差異與適用場景

```
+----------------+----------------+----------------+----------------+
| 工具           | 輸入           | 輸出           | 適用情境       |
+----------------+----------------+----------------+----------------+
| image_generate | 文字 prompt    | 靜態圖片       | 配圖、素材、   |
|                | + 參考圖(edit) | (png/webp/jpeg)| 影片 first_frame|
+----------------+----------------+----------------+----------------+
| video_generate | 文字 prompt    | 影片檔案       | 動態展示、     |
|                | + 參考圖/影片  | (mp4/...)      | 宣傳短片       |
+----------------+----------------+----------------+----------------+
| music_generate | 文字 prompt    | 音訊檔案       | 背景音樂、     |
|                | + lyrics       | (mp3/wav)      | 主題曲         |
+----------------+----------------+----------------+----------------+
```

**關鍵洞察：** `image_generate` 的產出可以作為 `video_generate` 的輸入（`first_frame` 或 `reference_image`），形成素材鏈。

### Provider Fallback 策略

OpenClaw 的媒體工具支援多 provider，當首選 provider 失敗或回應過慢時自動 fallback。建議策略：

```
首選 provider          fallback chain
+----------------+----------------+----------------+
| 圖片 (品質優先) | OpenAI         | Google         |
| 圖片 (成本優先) | Google         | OpenAI         |
| 影片 (品質優先) | Kling / Wan    | 其他可用       |
| 影片 (速度優先) | 支援快速生成   | 品質型         |
| 音樂            | 依歌詞/器樂   | 備用 provider  |
+----------------+----------------+----------------+
```

### 成本與品質權衡

| 工具 | 高品質參數 | 成本提示 | 快速參數 |
|------|-----------|---------|---------|
| image_generate | `quality: high`, `resolution: 2K` | 高 | `quality: low`, `size: 512x512` |
| video_generate | `resolution: 1080P`, `durationSeconds: 10` | 很高 | `resolution: 480P`, `durationSeconds: 5` |
| music_generate | `durationSeconds: 120`, 含 lyrics | 中 | `durationSeconds: 30`, `instrumental: true` |

---

## 操作指引

### 前置條件

1. **Provider 設定：** 至少設定一個圖片、一個影片、一個音樂 provider 的 API key
2. **儲存空間：** 媒體檔案較大，確認 OpenClaw 媒體目錄有足夠空間
3. **Timeout 意識：** 影片生成可能耗時數分鐘，調整 agent 的 patience 或拆分任務

### 最小可行範例：單一 Agent 生成圖片 + 音樂 + 影片

**目標：** 為「夏日海灘派對」生成一組社群媒體素材

```
Agent Prompt:
"為夏日海灘派對生成一組素材：
1. 一張主視覺圖：陽光沙灘、棕櫚樹、派對氛圍，1024x1024
2. 一段 5 秒宣傳影片：以主視覺圖為開場，展示海灘派對場景
3. 一段 30 秒背景音樂：輕快電子風格，無人聲"
```

**實際 tool calls（簡化）：**

```
Step 1: image_generate
  prompt: "陽光沙灘派對主視覺，棕櫚樹、彩色遮陽傘、清澈海水，明亮飽和色調"
  size: "1024x1024"
  outputFormat: "png"
  -> 產出: beach-party-cover.png

Step 2: video_generate
  prompt: "海灘派對宣傳短片，陽光沙灘、人們跳舞、彩色遮陽傘"
  image: "beach-party-cover.png"    (作為 first_frame)
  durationSeconds: 5
  aspectRatio: "1:1"
  resolution: "720P"
  -> 產出: beach-party-promo.mp4

Step 3: music_generate
  prompt: "輕快夏日電子音樂，海灘派對氛圍，節奏明快"
  instrumental: true
  durationSeconds: 30
  format: "mp3"
  -> 產出: beach-party-bgm.mp3
```

**素材鏈示意：**

```
[文字 prompt]
     |
     v
[image_generate] ---> beach-party-cover.png
     |                      |
     |                      v
     |            [video_generate: first_frame]
     |                      |
     |                      v
     |            beach-party-promo.mp4
     |
     +---> [music_generate]
                |
                v
          beach-party-bgm.mp3
```

### 進階範例：Subagent 分工

當素材需求複雜或數量龐大時，使用 subagent 並行處理：

```
[主 Agent: 素材總監]
     |
     +---> [Subagent: 視覺設計師]
     |           負責：所有圖片生成
     |           產出：cover.png, thumbnail.png, story-bg.png
     |
     +---> [Subagent: 音訊工程師]
     |           負責：背景音樂 + 音效
     |           產出：bgm.mp3, intro-jingle.mp3
     |
     +---> [Subagent: 影片剪輯師]
                 負責：接收視覺 + 音訊產出，組合影片
                 產出：final-promo.mp4, short-reel.mp4
```

**分工優勢：**
- 並行處理縮短總時間
- 每個 subagent 專注單一媒體類型，prompt 更精準
- 失敗隔離：視覺失敗不影響音訊進度

---

## 最佳實務

### 如何選擇 Provider

| 優先考量 | 圖片建議 | 影片建議 | 音樂建議 |
|---------|---------|---------|---------|
| **品質** | OpenAI (DALL-E 3 / GPT Image) | Kling / Wan2.6 | 依 provider 特性 |
| **成本** | Google Imagen | 較低階 provider | instrumental 模式較省 |
| **速度** | 低解析度 + low quality | 480P + 短 duration | 短 duration |
| **透明背景** | OpenAI gpt-image-1.5 (`background: transparent`) | - | - |

### 錯誤處理：單一媒體失敗的 Fallback

**策略 1：降級重試**
```
image_generate 失敗 (high quality)
  -> 重試 (medium quality)
      -> 重試 (low quality)
          -> 最終 fallback：使用預設占位圖或文字描述替代
```

**策略 2：替代方案**
```
video_generate 失敗
  -> 改用 image_generate 產出多張圖片
  -> 或使用現有影片素材庫
```

**策略 3：並行備援**
```
同時對兩個 provider 發送相同請求
  -> 採用先回應成功的結果
  -> 取消另一個（若支援）
```

### 儲存與命名慣例

建議命名格式：`{project}-{type}-{variant}.{ext}`

| 檔案類型 | 命名範例 |
|---------|---------|
| 主視覺圖 | `beachparty-cover-main.png` |
| 縮圖 | `beachparty-thumb-square.png` |
| 宣傳影片 | `beachparty-promo-5s.mp4` |
| 完整版影片 | `beachparty-promo-10s.mp4` |
| 背景音樂 | `beachparty-bgm-30s.mp3` |
| 主題曲 | `beachparty-theme-60s.mp3` |

---

## 技術細節參考

### image_generate 關鍵參數

| 參數 | 用途 | 範例 |
|------|------|------|
| `background: transparent` | 去背圖片（OpenAI gpt-image-1.5） | 產品圖、疊加素材 |
| `outputFormat: png` | 保留品質 + 支援透明 | 專業用途 |
| `outputFormat: webp` | 較小檔案 | 網頁使用 |
| `edit mode` | 以參考圖為基礎修改 | 風格統一 |

### video_generate 關鍵參數

| 參數 | 用途 | 範例 |
|------|------|------|
| `image` / `images` | 作為 first_frame / last_frame / reference_image | 品牌一致性 |
| `aspectRatio: "9:16"` | 短影片 / Reels / TikTok | 垂直影片 |
| `aspectRatio: "16:9"` | YouTube / 宣傳片 | 橫向影片 |
| `audio: true` | 生成內建音訊 | 快速預覽 |
| `audioRef` | 整合外部背景音樂 | 專業成品 |

### music_generate 關鍵參數

| 參數 | 用途 | 範例 |
|------|------|------|
| `instrumental: true` | 純背景音樂，無人聲 | 影片配樂 |
| `lyrics` | 主題曲、配音 | 品牌歌曲 |
| `durationSeconds` | 控制長度 | 注意各 provider 支援差異 |

---

## Troubleshooting

### 常見錯誤

| 症狀 | 可能原因 | 解決方案 |
|------|---------|---------|
| `timeout` | 影片/音樂生成時間過長 | 縮短 durationSeconds，或拆成 subagent |
| `provider 不支援格式` | 指定了該 provider 不支援的參數 | 查閱 provider 文件，調整參數或換 provider |
| `quota exceeded` | API 配額用盡 | 切換 fallback provider，或等待配額重置 |
| `image 作為 video 輸入失敗` | 圖片格式或尺寸不符 | 確保圖片為 png/jpeg，尺寸符合影片 model 要求 |
| `透明背景無效` | 非 OpenAI gpt-image-1.5 | 指定 `model: "openai/gpt-image-1.5"` |

### 診斷流程

```
生成失敗
    |
    +---> 檢查錯誤訊息
    |         |
    |         +---> timeout? -> 縮短參數 / 拆 subagent
    |         +---> quota? -> 換 provider
    |         +---> 格式? -> 調整 outputFormat / 查文件
    |
    +---> 檢查 provider 狀態
    |         +---> 嘗試其他 provider
    |
    +---> 最終 fallback
              +---> 使用預設素材
              +---> 標記人工介入
```

---

## 相關連結

- [image_generate 工具文件](../docs/tools/image_generate.md) *(若存在)*
- [video_generate 工具文件](../docs/tools/video_generate.md) *(若存在)*
- [music_generate 工具文件](../docs/tools/music_generate.md) *(若存在)*
- Issue [#602](https://github.com/thepagent/claw-info/issues/602) - 多媒體生成工作流程（母 issue）
- Issue [#656](https://github.com/thepagent/claw-info/issues/656) - 本文件對應 issue

---

## Changelog

| 日期 | 變更 |
|------|------|
| 2026-05-25 | 初版，涵蓋單一 agent 與 subagent 分工範例 |
