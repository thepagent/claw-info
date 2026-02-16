# How to Configure Model Pricing in OpenClaw

OpenClaw doesn't include a built-in pricing database. Instead, you configure costs in your config file to match your actual provider expenses.

## Pricing Location

Model pricing is configured in `~/.openclaw/openclaw.json` under:

```json
{
  "models": {
    "providers": {
      "amazon-bedrock": {
        "models": [
          {
            "id": "qwen.qwen3-coder-next",
            "cost": {
              "input": 0.5,
              "output": 1.2,
              "cacheRead": 0,
              "cacheWrite": 0
            }
          }
        ]
      }
    }
  }
}
```

## Cost Fields

| Field | Description | Unit |
|-------|-------------|------|
| `input` | Cost per million input tokens | USD |
| `output` | Cost per million output tokens | USD |
| `cacheRead` | Cost per million cache read tokens | USD |
| `cacheWrite` | Cost per million cache write tokens | USD |

## Usage

OpenClaw tracks tokens per session and calculates costs as:

```
Input cost = (input_tokens / 1,000,000) × input_price
Output cost = (output_tokens / 1,000,000) × output_price
Total = Input cost + Output cost
```

## Example: Adding a New Model

To add a new model with custom pricing:

```json
{
  "models": {
    "providers": {
      "amazon-bedrock": {
        "models": [
          {
            "id": "my.custom.model",
            "name": "My Custom Model",
            "cost": {
              "input": 0.3,
              "output": 0.6,
              "cacheRead": 0,
              "cacheWrite": 0
            },
            "contextWindow": 131072,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

## Default Model Pricing Reference

| Model | Input Price | Output Price | Source |
|-------|-------------|--------------|--------|
| Qwen3 Coder Next | $0.50/M | $1.20/M | Amazon Bedrock |
| DeepSeek V3.2 | $0.62/M | $1.85/M | Amazon Bedrock |
| GLM 4.7 | $0.60/M | $2.20/M | Amazon Bedrock |
| GPT OSS 20B | $0.07/M | $0.31/M | Amazon Bedrock |
| GPT OSS 120B | $0.15/M | $0.62/M | Amazon Bedrock |
| MiniMax M2 | $0.30/M | $1.20/M | Amazon Bedrock |

*Note: Prices shown are examples. Check your provider's official pricing for accurate figures.*

## Viewing Costs

Session costs are displayed in `/status`:

```
📊 Tokens: 94k in / 19 out
🧮 Cost: ~$0.075 (USD)
```

## Related Docs

- [Configuration Guide](/gateway/configuration)
- [Session Management](/concepts/sessions)
