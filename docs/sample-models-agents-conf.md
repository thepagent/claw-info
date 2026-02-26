# Sample Models & Agents Config

Minimal shareable snippet for openclaw `openclaw.json`.

> **Note**: Fill in your own `apiKey` under `providers.ollama-cloud`. The `openai-codex` provider is built-in to openclaw and requires no additional config.

```json
{
  "models": {
    "providers": {
      "ollama-cloud": {
        "baseUrl": "https://ollama.com/v1",
        "api": "openai-completions",
        "apiKey": "<your-ollama-api-key>",
        "models": [
          "cogito-2.1:671b",
          "deepseek-v3.1:671b",
          "deepseek-v3.2",
          "devstral-2:123b",
          "devstral-small-2:24b",
          "gemini-3-flash-preview",
          "gemma3:12b",
          "gemma3:27b",
          "gemma3:4b",
          "glm-4.6",
          "glm-4.7",
          "glm-5",
          "glm-5-cloud",
          "gpt-oss:120b",
          "gpt-oss:20b",
          "kimi-k2-thinking",
          "kimi-k2.5",
          "kimi-k2:1t",
          "minimax-m2",
          "minimax-m2.1",
          "minimax-m2.5",
          "ministral-3:14b",
          "ministral-3:3b",
          "ministral-3:8b",
          "mistral-large-3:675b",
          "nemotron-3-nano:30b",
          "qwen3-coder-next",
          "qwen3-coder:480b",
          "qwen3-coder:480b-cloud",
          "qwen3-next:80b",
          "qwen3-vl:235b",
          "qwen3-vl:235b-instruct",
          "qwen3.5:397b",
          "rnj-1:8b"
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai-codex/gpt-5.2",
        "fallbacks": ["ollama-cloud/gemini-3-flash-preview"]
      }
    }
  }
}
```
