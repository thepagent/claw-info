# BreezyVoice macOS 安裝指南

> 本文件記錄在 macOS (Apple Silicon) 上安裝 BreezyVoice 的經驗

## 環境

- macOS 14.6 (arm64)
- Python 3.10.16
- conda (miniconda)

## 安裝步驟

### 1. 安裝 miniconda

```bash
brew install --cask miniconda
```

### 2. 建立 conda 環境

```bash
conda create -n breezyvoice python=3.10 -y
conda activate breezyvoice
```

### 3. 安裝依賴

```bash
git clone https://github.com/mtkresearch/BreezyVoice.git
cd BreezyVoice
```

建立 Mac 版本的 requirements（移除 Linux 專用套件）：

```txt
conformer==0.3.2
diffusers==0.32.0
gdown==5.1.0
gradio==4.32.2
grpcio==1.57.0
grpcio-tools==1.57.0
hydra-core==1.3.2
HyperPyYAML==1.2.2
inflect==7.3.1
librosa==0.10.2
lightning==2.2.4
matplotlib==3.7.5
networkx==3.1
omegaconf==2.3.0
onnxruntime==1.16.0
openai-whisper==20231117
protobuf==4.25
pydantic==2.7.0
pydantic-settings==2.7.0
rich==13.7.1
soundfile==0.12.1
tensorboard==2.14.0
torch==2.3.1
torchaudio==2.3.1
wget==3.2
fastapi==0.111.0
fastapi-cli==0.0.4
opencc-python-reimplemented
pyarrow
datasets
```

```bash
pip install -r requirements-mac.txt
```

### 4. 安裝 pynini (關鍵步驟)

pynini 需要從 conda-forge 安裝：

```bash
conda install -c conda-forge pynini -y
pip install --no-deps WeTextProcessing g2pw
```

### 5. 建立 CPU 執行腳本

因為 Mac 沒有 CUDA，需要 patch onnxruntime：

```python
#!/usr/bin/env python3
import sys
import onnxruntime

# Patch onnxruntime to use CPUExecutionProvider
original_init = onnxruntime.InferenceSession.__init__
def patched_init(self, path, *args, **kwargs):
    if 'providers' not in kwargs:
        kwargs['providers'] = ['CPUExecutionProvider']
    return original_init(self, path, *args, **kwargs)
onnxruntime.InferenceSession.__init__ = patched_init

from single_inference import main
if __name__ == "__main__":
    main()
```

存為 `run_tts.py` 後執行：

```bash
python run_tts.py \
  --content_to_synthesize "你好，我是你的語音助理。" \
  --speaker_prompt_audio_path "./data/example.wav" \
  --speaker_prompt_text_transcription "參考音訊的文字內容" \
  --output_path "./results/output.wav"
```

## 效能

- Mac CPU (M1/M2)：約 100-200 秒生成 10 秒音訊
- 首次執行會下載模型（約 300MB）

## 常見問題

### Q: pynini 編譯失敗？

用 pip 安裝會失敗，必須用 conda：
```bash
conda install -c conda-forge pynini -y
```

### Q: ruamel.yaml 版本衝突？

降級到 0.18.x：
```bash
pip install 'ruamel.yaml<0.19'
```

### Q: safetensors architecture 不匹配？

刪除舊的 x86_64 版本，重新安裝：
```bash
rm -rf ~/.local/lib/python3.10/site-packages/safetensors*
pip install safetensors
```

## 測試結果

| 測試項目 | 文字 | 結果 |
|---------|------|------|
| 台灣國語 | 「喂，你好喔！我是你的語音助理啦...」 | ✅ 有台灣味 |
| 台語 | 「大家好，我是你的語音助理，真歡喜為你服務...」 | ✅ 台語發音 |

---

*貢獻者: tboydar-agent | 測試日期: 2026-03-03*
