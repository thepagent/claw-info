# Amazon Bedrock 模型定價比較

```
source: https://aws.amazon.com/bedrock/pricing/
update: Feb 14, 2026
```

## 定價表 (US East, $/M tokens)

```
┌──────────────────────────────────────┬─────────────┬──────────────┬─────────────────────┐
│ Model                                │ Input $/M   │ Output $/M   │ Total (1M+1M)       │
├──────────────────────────────────────┼─────────────┼──────────────┼─────────────────────┤
│ openai.gpt-oss-safeguard-20b         │ $0.07       │ $0.20        │ $0.27               │
│ openai.gpt-oss-20b-1:0               │ $0.07       │ $0.31        │ $0.38               │
│ zai.glm-4.7-flash                    │ $0.07       │ $0.40        │ $0.47               │
│ openai.gpt-oss-safeguard-120b        │ $0.15       │ $0.60        │ $0.75               │
│ openai.gpt-oss-120b-1:0              │ $0.15       │ $0.62        │ $0.77               │
│ qwen.qwen3-next-80b-a3b              │ $0.15       │ $1.20        │ $1.35               │
│ minimax.minimax-m2                   │ $0.30       │ $1.20        │ $1.50               │
│ minimax.minimax-m2.1                 │ $0.30       │ $1.20        │ $1.50               │
│ qwen.qwen3-coder-next                │ $0.50       │ $1.20        │ $1.70               │
│ deepseek.v3.2                        │ $0.62       │ $1.85        │ $2.47               │
│ zai.glm-4.7                          │ $0.60       │ $2.20        │ $2.80               │
│ moonshot.kimi-k2-thinking            │ $0.60       │ $2.50        │ $3.10               │
│ qwen.qwen3-vl-235b-a22b              │ $0.53       │ $2.66        │ $3.19               │
│ moonshotai.kimi-k2.5                 │ $0.60       │ $3.00        │ $3.60               │
│ anthropic.claude-haiku-4.5           │ $1.00       │ $5.00        │ $6.00               │
│ anthropic.claude-sonnet-4.5          │ $3.00       │ $15.00       │ $18.00              │
│ anthropic.claude-opus-4.5            │ $5.00       │ $25.00       │ $30.00              │
│ anthropic.claude-opus-4.6            │ $5.00       │ $25.00       │ $30.00              │
│ anthropic.claude-sonnet-4.5-long     │ $6.00       │ $22.50       │ $28.50              │
│ anthropic.claude-opus-4.6-long       │ $10.00      │ $37.50       │ $47.50              │
└──────────────────────────────────────┴─────────────┴──────────────┴─────────────────────┘
```

## 價格排序 (由低至高)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$0.27  openai.gpt-oss-safeguard-20b        █
$0.38  openai.gpt-oss-20b-1:0              █
$0.47  zai.glm-4.7-flash                   █
$0.75  openai.gpt-oss-safeguard-120b       ██
$0.77  openai.gpt-oss-120b-1:0             ██
$1.35  qwen.qwen3-next-80b-a3b             ███
$1.50  minimax.minimax-m2                  ███
$1.50  minimax.minimax-m2.1                ███
$1.70  qwen.qwen3-coder-next               ████
$2.47  deepseek.v3.2                       █████
$2.80  zai.glm-4.7                         ██████
$3.10  moonshot.kimi-k2-thinking           ███████
$3.19  qwen.qwen3-vl-235b-a22b             ███████
$3.60  moonshotai.kimi-k2.5                ████████
$6.00  anthropic.claude-haiku-4.5          █████████████
$18.00 anthropic.claude-sonnet-4.5         ██████████████████████████████████████
$28.50 anthropic.claude-sonnet-4.5-lon     ████████████████████████████████████████████████████████████
$30.00 anthropic.claude-opus-4.5           ███████████████████████████████████████████████████████████████
$30.00 anthropic.claude-opus-4.6           ███████████████████████████████████████████████████████████████
$47.50 anthropic.claude-opus-4.6-long      ███████████████████████████████████████████████████████████████████████████████████████████████████
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Anthropic Claude 模型詳細定價 ($/M tokens)

| Model | Input | Output | Batch In | Batch Out | 5m Cache Write | 1h Cache Write | Cache Read |
|-------|-------|--------|----------|-----------|----------------|----------------|------------|
| Claude Haiku 4.5 | $1.00 | $5.00 | $0.50 | $2.50 | $1.25 | $2.00 | $0.10 |
| Claude Sonnet 4.5 | $3.00 | $15.00 | $1.50 | $7.50 | $3.75 | $6.00 | $0.30 |
| Claude Sonnet 4.5 Long | $6.00 | $22.50 | $3.00 | $11.25 | $7.50 | $12.00 | $0.60 |
| Claude Opus 4.5 | $5.00 | $25.00 | $2.50 | $12.50 | $6.25 | $10.00 | $0.50 |
| Claude Opus 4.6 | $5.00 | $25.00 | $2.50 | $12.50 | $6.25 | $10.00 | $0.50 |
| Claude Opus 4.6 Long | $10.00 | $37.50 | $5.00 | $18.75 | $12.50 | $20.00 | $1.00 |

## Prompt: 將所有模型加入 openclaw.json

```
Read the pricing table from https://gist.github.com/pahud/2af7b03d6838366fa2fd6337029688a5

Add all models to my ~/.openclaw/openclaw.json:
1. Add each model to models.providers.amazon-bedrock.models array with id, name, cost (input/output per M tokens)
2. Add each model to agents.defaults.models with alias

Keep my existing primary/fallback settings unchanged.
```

## 參考資料

- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Original Gist](https://gist.github.com/pahud/2af7b03d6838366fa2fd6337029688a5)
