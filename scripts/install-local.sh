#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$HOME/.local/bin"
CFG="$HOME/.config/shadow"
mkdir -p "$BIN" "$CFG"
chmod 700 "$CFG"
cat > "$BIN/shadow-api" <<EOF
#!/usr/bin/env bash
set -euo pipefail
[ ! -f "\$HOME/.config/shadow/openai.env" ] || . "\$HOME/.config/shadow/openai.env"
export PYTHONPATH="$ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m shadow.runtime "\$@"
EOF
chmod 700 "$BIN/shadow-api"
cat > "$BIN/shadow-key" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="$HOME/.config/shadow"; FILE="$DIR/openai.env"
mkdir -p "$DIR"; chmod 700 "$DIR"
case "${1:-status}" in
  status) [ -s "$FILE" ] && echo 'OpenAI API key: configured' || echo 'OpenAI API key: not configured' ;;
  set)
    printf 'OpenAI API key: ' >&2; IFS= read -r -s key; printf '\n' >&2
    case "$key" in sk-*) ;; *) echo 'Key does not look like an OpenAI API key.' >&2; exit 2;; esac
    umask 077; printf 'export OPENAI_API_KEY=%q\n' "$key" > "$FILE"; chmod 600 "$FILE"; unset key
    echo 'OpenAI API key saved locally.' ;;
  clear) rm -f "$FILE"; echo 'OpenAI API key removed.' ;;
  *) echo 'usage: shadow-key {status|set|clear}' >&2; exit 2 ;;
esac
EOF
chmod 700 "$BIN/shadow-key"
echo "Installed: $BIN/shadow-api and $BIN/shadow-key"
echo "Next: shadow-key set"
