# Shadow

Shadow is an experiment in making an AI assistant feel less like a website you visit and more like a persistent presence on your own computer.

The model is still remote. The desktop stays local. Shadow sits between them: it carries an identity, memory, context and permission model, then gives the model a controlled way to work with the machine through Desktop Commander.

The first goal is simple: speak to Shadow and get a spoken answer back without browser macros, fake clicks or typing into a chat box.

## Architecture

```text
voice -> whisper.cpp -> Shadow runtime -> provider API
                                      <-> Desktop Commander (MCP)
                                      <-> local memory/context
                         response -> Kokoro -> speakers
```

The provider layer is intentionally separate from the rest of the runtime. OpenAI and Google Gemini are supported today; Anthropic is planned on the same boundary.

Desktop Commander is not used as the conversation transport. It is Shadow's desktop tool layer. The model asks for only the state it actually needs, which also helps keep API context and cost down.

## What exists today

This repository contains the provider/API runtime and the Desktop Commander MCP bridge. The development machine already has the wider local stack running with whisper.cpp, Silero VAD, Kokoro ONNX, a small persistent memory layer and Graphify-assisted context selection.

The public repo deliberately does **not** contain personal memory, live prompts, credentials, runtime logs or machine-specific state.

## Quick start

You need Python 3.10+, Desktop Commander MCP and a provider API key. For development, Google Gemini is a convenient option because supported Gemini Developer API models have a free tier.

```bash
git clone https://github.com/Caio-Silveira/Shadow.git
cd Shadow
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
export SHADOW_PROVIDER=google
export GEMINI_API_KEY="your-key"
export SHADOW_GOOGLE_MODEL="gemini-2.5-flash"
shadow-api "What is running on my machine right now?"
```

Choose the provider with `SHADOW_PROVIDER=google` or `SHADOW_PROVIDER=openai`. Google defaults to `gemini-2.5-flash`; OpenAI defaults to `gpt-5.6-luna`. Provider-specific model variables are shown in `.env.example`.

The local Desktop Commander paths can be overridden with `SHADOW_NODE` and `SHADOW_DC_SERVER`. See `.env.example`.

## Why not send the whole desktop to the model?

Because most turns do not need it. Shadow should ask for the smallest useful piece of state, retrieve it locally, and send only that result back to the model. The same idea applies to project context: local indexing/search can narrow the context before the API sees it.

## Safety

Desktop access is powerful. Shadow is designed around explicit permission boundaries: ordinary low-risk reads can be automatic; destructive, privileged, security-sensitive, financial or external communication actions should require user approval.

Do not put API keys, credentials or personal memory in this repository.

## Status

Early prototype. Direct OpenAI and Google Gemini transports are wired to the Desktop Commander bridge and the existing voice loop. Anthropic provider support and packaging are next.

## License

MIT. See [LICENSE](LICENSE).
