#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"; BASE="$HOME/.local/share/shadow"; CFG="$HOME/.config/shadow"
VOICE=1; [[ " ${*:-} " == *" --no-voice "* ]] && VOICE=0
mkdir -p "$BIN" "$BASE" "$BASE/prompts" "$CFG" "$HOME/.config/systemd/user"
chmod 700 "$BASE" "$CFG"

for f in "$ROOT"/scripts/bin/*; do install -m 700 "$f" "$BIN/$(basename "$f")"; done
install -m 600 "$ROOT/prompts/shadow.md" "$BASE/prompts/shadow.md"
install -m 600 "$ROOT/prompts/observer.md" "$BASE/prompts/observer.md"
install -m 644 "$ROOT/systemd/shadow.service" "$HOME/.config/systemd/user/shadow.service"

cat > "$BIN/shadow-api" <<WRAP
#!/usr/bin/env bash
set -euo pipefail
for f in "\$HOME/.config/shadow/provider.env" "\$HOME/.config/shadow/keys.env"; do [[ ! -f "\$f" ]] || . "\$f"; done
export PYTHONPATH="$ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m shadow.runtime "\$@"
WRAP
chmod 700 "$BIN/shadow-api"

cat > "$BIN/shadow-provider" <<'PROVIDER'
#!/usr/bin/env bash
set -euo pipefail
F="$HOME/.config/shadow/provider.env"; mkdir -p "${F%/*}"; touch "$F"; chmod 600 "$F"
case "${1:-show}" in
 show) . "$F" 2>/dev/null || true; echo "${SHADOW_PROVIDER:-google}" ;;
 set) case "${2:-}" in google|openai|anthropic|deepseek|lmstudio) printf 'export SHADOW_PROVIDER=%q\n' "$2" > "$F";; *) echo 'use: google|openai|anthropic|deepseek|lmstudio' >&2; exit 2;; esac ;;
 *) echo 'usage: shadow-provider {show|set PROVIDER}' >&2; exit 2;;
esac
PROVIDER
chmod 700 "$BIN/shadow-provider"
cat > "$BIN/shadow-key" <<'KEYS'
#!/usr/bin/env bash
set -euo pipefail
F="$HOME/.config/shadow/keys.env"; mkdir -p "${F%/*}"; touch "$F"; chmod 600 "$F"
p="${2:-${1:-}}"
case "$p" in google) var=GEMINI_API_KEY;; openai) var=OPENAI_API_KEY;; anthropic|claude) var=ANTHROPIC_API_KEY;; deepseek) var=DEEPSEEK_API_KEY;; lmstudio) var=LM_API_TOKEN;; *) echo 'provider: google|openai|anthropic|deepseek|lmstudio' >&2; exit 2;; esac
case "${1:-status}" in
 set) printf '%s key: ' "$p" >&2; IFS= read -r -s key; printf '\n' >&2; grep -v "^export $var=" "$F" > "$F.tmp" || true; printf 'export %s=%q\n' "$var" "$key" >> "$F.tmp"; chmod 600 "$F.tmp"; mv "$F.tmp" "$F"; unset key; echo "$p key: configured";;
 status) grep -q "^export $var=" "$F" && echo "$p key: configured" || echo "$p key: not configured";;
 *) echo 'usage: shadow-key {set|status} PROVIDER' >&2; exit 2;;
esac
KEYS
chmod 700 "$BIN/shadow-key"

if (( VOICE )); then
  need=(git cmake curl python3 parec paplay)
  missing=(); for x in "${need[@]}"; do command -v "$x" >/dev/null || missing+=("$x"); done
  if ((${#missing[@]})); then
    echo "Dependências de voz ausentes: ${missing[*]}" >&2
    echo "Instale-as e rode ./install.sh novamente, ou use --no-voice." >&2
    exit 2
  fi
  STT="$BASE/voice/stt"; mkdir -p "$STT/models" "$BASE/voice/models"
  if [[ ! -d "$STT/vendor/whisper.cpp/.git" ]]; then git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$STT/vendor/whisper.cpp"; fi
  cmake -S "$STT/vendor/whisper.cpp" -B "$STT/vendor/whisper.cpp/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$STT/vendor/whisper.cpp/build" -j"$(nproc)" >/dev/null
  [[ -s "$STT/vendor/whisper.cpp/models/ggml-small.bin" ]] || (cd "$STT/vendor/whisper.cpp" && ./models/download-ggml-model.sh small)
  [[ -s "$STT/models/ggml-silero-v6.2.0.bin" ]] || (cd "$STT/vendor/whisper.cpp" && ./models/download-vad-model.sh silero-v6.2.0 && cp models/ggml-silero-v6.2.0.bin "$STT/models/")
  python3 -m venv "$BASE/voice/venv"; "$BASE/voice/venv/bin/pip" -q install -U pip kokoro-onnx soundfile
  KURL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
  [[ -s "$BASE/voice/models/kokoro-v1.0.onnx" ]] || curl -fL "$KURL/kokoro-v1.0.onnx" -o "$BASE/voice/models/kokoro-v1.0.onnx"
  [[ -s "$BASE/voice/models/voices-v1.0.bin" ]] || curl -fL "$KURL/voices-v1.0.bin" -o "$BASE/voice/models/voices-v1.0.bin"
fi

[[ -s "$CFG/provider.env" ]] || printf 'export SHADOW_PROVIDER=google\nexport SHADOW_GOOGLE_MODEL=gemini-3.5-flash-lite\n' > "$CFG/provider.env"
chmod 600 "$CFG/provider.env"
mkdir -p "$BASE/config"
[[ -s "$BASE/config/audio.json" ]] || cat > "$BASE/config/audio.json" <<'JSON'
{"input":{"engine":"PipeWire","source":"default","sample_rate":16000,"channels":1},"stt":{"engine":"whisper.cpp","model":"small","language":"pt","vad":"silero-v6.2.0","threads":6,"prompt":"Shadow é o nome do assistente."}}
JSON
[[ -s "$BASE/config/voice.json" ]] || cat > "$BASE/config/voice.json" <<'JSON'
{"engine":"kokoro-onnx","language":"pt-br","voice":"pm_alex","speed":1.05,"available_voices":{"pf_dora":"Dora","pm_alex":"Alex","pm_santa":"Santa"}}
JSON
chmod 600 "$BASE/config/audio.json" "$BASE/config/voice.json"
systemctl --user daemon-reload
if (( VOICE )); then systemctl --user enable --now shadow.service; fi

echo
echo 'Shadow instalado.'
echo "Provider: $($BIN/shadow-provider show)"
echo 'Troque com: shadow-provider set google|openai|anthropic|deepseek|lmstudio'
echo 'Chave: shadow-key set PROVIDER'
echo 'Serviço: systemctl --user status shadow'
