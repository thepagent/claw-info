# Amazon Bedrock Models Configuration for OpenClaw

This document provides a reference configuration for using Amazon Bedrock models with OpenClaw.

## Prerequisites

1. AWS credentials configured with `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` permissions
2. For model discovery, also need `bedrock:ListFoundationModels` permission
3. Set `AWS_PROFILE` in `.openclaw/.env` if using a specific profile

## Configuration

Add the following to your `openclaw.json` under the `models` section:

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "amazon-bedrock": {
        "baseUrl": "https://bedrock-runtime.us-east-1.amazonaws.com",
        "api": "bedrock-converse-stream",
        "models": [
          {
            "id": "qwen.qwen3-coder-next",
            "name": "Qwen3 Coder Next",
            "reasoning": true,
            "input": ["text"],
            "cost": {"input": 0.5, "output": 1.2, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 262144,
            "maxTokens": 8192
          },
          {
            "id": "deepseek.v3.2",
            "name": "DeepSeek V3.2",
            "reasoning": true,
            "input": ["text"],
            "cost": {"input": 0.62, "output": 1.85, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "deepseek.r1-v1:0",
            "name": "DeepSeek R1",
            "reasoning": true,
            "input": ["text"],
            "cost": {"input": 1.35, "output": 5.4, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 128000,
            "maxTokens": 8192
          },
          {
            "id": "qwen.qwen3-vl-235b-a22b",
            "name": "Qwen3 VL 235B",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {"input": 0.53, "output": 2.66, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "moonshotai.kimi-k2.5",
            "name": "Kimi K2.5",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {"input": 0.6, "output": 3, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "moonshot.kimi-k2-thinking",
            "name": "Kimi K2 Thinking",
            "reasoning": true,
            "input": ["text"],
            "cost": {"input": 0.6, "output": 2.5, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "minimax.minimax-m2.1",
            "name": "MiniMax M2.1",
            "reasoning": false,
            "input": ["text"],
            "cost": {"input": 0.3, "output": 1.2, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "zai.glm-4.7-flash",
            "name": "GLM 4.7 Flash",
            "reasoning": false,
            "input": ["text"],
            "cost": {"input": 0.07, "output": 0.4, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "zai.glm-4.7",
            "name": "GLM 4.7",
            "reasoning": false,
            "input": ["text"],
            "cost": {"input": 0.6, "output": 2.2, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "us.anthropic.claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "reasoning": false,
            "input": ["text"],
            "cost": {"input": 3, "output": 15, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 200000,
            "maxTokens": 8192
          },
          {
            "id": "anthropic.claude-opus-4-6-v1",
            "name": "Claude Opus 4.6",
            "reasoning": true,
            "input": ["text", "image"],
            "cost": {"input": 15, "output": 75, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 200000,
            "maxTokens": 8192
          },
          {
            "id": "meta.llama4-scout-17b-instruct-v1:0",
            "name": "Llama 4 Scout",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {"input": 0.17, "output": 0.17, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 3500000,
            "maxTokens": 8192
          },
          {
            "id": "meta.llama4-maverick-17b-instruct-v1:0",
            "name": "Llama 4 Maverick",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {"input": 0.17, "output": 0.17, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 1000000,
            "maxTokens": 8192
          },
          {
            "id": "mistral.mistral-large-3-675b-instruct",
            "name": "Mistral Large 3",
            "reasoning": false,
            "input": ["text"],
            "cost": {"input": 2, "output": 6, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 128000,
            "maxTokens": 8192
          }
        ]
      }
    },
    "bedrockDiscovery": {
      "enabled": true
    }
  }
}
```

## Model Aliases

You also need to add aliases under `agents.defaults.models`:

```json
{
  "agents": {
    "defaults": {
      "models": {
        "amazon-bedrock/qwen.qwen3-coder-next": {"alias": "Qwen3 Coder"},
        "amazon-bedrock/deepseek.v3.2": {"alias": "DeepSeek V3.2"},
        "amazon-bedrock/deepseek.r1-v1:0": {"alias": "DeepSeek R1"},
        "amazon-bedrock/qwen.qwen3-vl-235b-a22b": {"alias": "Qwen3 VL"},
        "amazon-bedrock/moonshotai.kimi-k2.5": {"alias": "Kimi K2.5"},
        "amazon-bedrock/moonshot.kimi-k2-thinking": {"alias": "Kimi Thinking"},
        "amazon-bedrock/minimax.minimax-m2.1": {"alias": "MiniMax M2.1"},
        "amazon-bedrock/zai.glm-4.7-flash": {"alias": "GLM Flash"},
        "amazon-bedrock/zai.glm-4.7": {"alias": "GLM 4.7"},
        "amazon-bedrock/us.anthropic.claude-sonnet-4-6": {"alias": "Claude Sonnet 4.6"},
        "amazon-bedrock/anthropic.claude-opus-4-6-v1": {"alias": "Claude Opus 4.6"},
        "amazon-bedrock/meta.llama4-scout-17b-instruct-v1:0": {"alias": "Llama 4 Scout"},
        "amazon-bedrock/meta.llama4-maverick-17b-instruct-v1:0": {"alias": "Llama 4 Maverick"},
        "amazon-bedrock/mistral.mistral-large-3-675b-instruct": {"alias": "Mistral Large 3"}
      }
    }
  }
}
```

## Model Categories

### Vision Models (text + image)
| Model | Context | Cost (input/output per 1M tokens) |
|-------|---------|-----------------------------------|
| Qwen3 VL 235B | 128k | $0.53 / $2.66 |
| Kimi K2.5 | 128k | $0.60 / $3.00 |
| Claude Opus 4.6 | 200k | $15.00 / $75.00 |
| Llama 4 Scout | 3.5M | $0.17 / $0.17 |
| Llama 4 Maverick | 1M | $0.17 / $0.17 |

### Reasoning Models
| Model | Context | Cost (input/output per 1M tokens) |
|-------|---------|-----------------------------------|
| DeepSeek R1 | 128k | $1.35 / $5.40 |
| DeepSeek V3.2 | 128k | $0.62 / $1.85 |
| Qwen3 Coder Next | 256k | $0.50 / $1.20 |
| Kimi K2 Thinking | 128k | $0.60 / $2.50 |
| Claude Opus 4.6 | 200k | $15.00 / $75.00 |

### Budget-Friendly Models
| Model | Context | Cost (input/output per 1M tokens) |
|-------|---------|-----------------------------------|
| GLM 4.7 Flash | 128k | $0.07 / $0.40 |
| Llama 4 Scout | 3.5M | $0.17 / $0.17 |
| Llama 4 Maverick | 1M | $0.17 / $0.17 |
| MiniMax M2.1 | 128k | $0.30 / $1.20 |

## Notes

1. **Inference Profiles**: Some models (like Nova) require inference profile IDs (e.g., `us.amazon.nova-pro-v1:0`) instead of base model IDs
2. **Region**: Change `baseUrl` if using a different region
3. **Discovery**: `bedrockDiscovery.enabled: true` allows viewing all available models with `openclaw models list --all`, but models must still be explicitly configured to be usable
4. **Nova Models**: Currently have API compatibility issues with OpenClaw's message format (require user message first, no system prompt)

## IAM Policy

Minimum required permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
```
