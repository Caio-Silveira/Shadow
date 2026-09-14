# Arquitetura

Shadow separa cinco responsabilidades:

```text
voz → STT local → identidade/runtime → provider de IA
                         ↕                 ↕
                 memória + Observer   tool calling
                         ↕                 ↕
                    permissões ← Desktop Commander → desktop
                         ↓
                    TTS local → voz
```

A identidade vive em `prompts/`, não no provider. Google, OpenAI, Anthropic, DeepSeek e LM Studio implementam apenas transporte/inferência. O runtime entrega a eles um conjunto reduzido de ferramentas MCP para diminuir tokens e latência.

Whisper e Kokoro rodam localmente. Capturas de tela são anexadas somente quando a intenção pede visão. Permissões comuns podem ser lembradas; ações de alto impacto continuam exigindo consentimento.

O serviço `shadow.service` mantém o loop de voz disponível na sessão do usuário. Ele é um serviço de usuário, não roda como root.
