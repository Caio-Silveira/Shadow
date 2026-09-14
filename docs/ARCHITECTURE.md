# Architecture

Shadow separates four concerns that are often mixed together in desktop-agent projects:

1. **Identity and memory** live locally and are selected before each model turn.
2. **Model transport** is a provider adapter. OpenAI Responses API is first; Anthropic is planned.
3. **Desktop access** is Desktop Commander over MCP. The model sees DC as tools, not as a chat transport.
4. **Voice** stays local where practical: whisper.cpp/Silero for input and Kokoro for output.

The model should not receive a full desktop dump every turn. It asks for a specific file, process, search result or screen state only when needed. Tool output is capped before being sent back to the provider.

Mutating or executable Desktop Commander tools are gated by local approval. Read-only tools can run without interrupting the user.

```text
microphone
   |
whisper.cpp + VAD
   |
Shadow runtime ---- local memory / Graphify
   |
provider API
   |  ^
   v  |
Desktop Commander MCP
   |
OS / files / processes / GUI

provider response -> Kokoro -> speakers
```
