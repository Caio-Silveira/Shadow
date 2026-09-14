# Providers

Shadow separa identidade de modelo. Trocar o cérebro não deve trocar quem é o Shadow.

| Provider | Variável de chave | Modelo padrão |
|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | `gemini-3.5-flash-lite` |
| OpenAI | `OPENAI_API_KEY` | `gpt-5.6-luna` |
| Anthropic Claude | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-flash` |
| LM Studio | opcional | definido por `SHADOW_LMSTUDIO_MODEL` |

Use `shadow-provider set <provider>` para trocar. Chaves ficam apenas em `~/.config/shadow/keys.env` com permissão local restrita.

LM Studio usa o endpoint compatível com OpenAI em `http://127.0.0.1:1234/v1/responses`. O servidor e um modelo com suporte adequado a tools precisam estar ativos.
