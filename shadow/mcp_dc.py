import json, os, queue, subprocess, threading, time

class DesktopCommanderMCP:
    def __init__(self, command=None):
        node = os.environ.get("SHADOW_NODE", os.path.expanduser("~/.nvm/versions/node/v24.15.0/bin/node"))
        server = os.environ.get("SHADOW_DC_SERVER", os.path.expanduser("~/.local/share/desktop-commander/node_modules/@wonderwhy-er/desktop-commander/dist/index.js"))
        self.command = command or [node, server]
        self.proc = None
        self._id = 0
        self._pending = {}
        self._lock = threading.Lock()

    def start(self):
        if self.proc and self.proc.poll() is None:
            return self
        self.proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        threading.Thread(target=self._reader, daemon=True).start()
        result = self.request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "shadow", "version": "0.1.0"}
        })
        self.notify("notifications/initialized", {})
        return self

    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try: msg = json.loads(line)
            except Exception: continue
            ident = msg.get("id")
            if ident in self._pending:
                self._pending[ident].put(msg)

    def _send(self, obj):
        raw = json.dumps(obj, separators=(",", ":")) + "\n"
        with self._lock:
            self.proc.stdin.write(raw); self.proc.stdin.flush()

    def notify(self, method, params=None):
        self._send({"jsonrpc":"2.0","method":method,"params":params or {}})

    def request(self, method, params=None, timeout=20):
        self._id += 1; ident = self._id; q = queue.Queue(); self._pending[ident] = q
        self._send({"jsonrpc":"2.0","id":ident,"method":method,"params":params or {}})
        try: msg = q.get(timeout=timeout)
        finally: self._pending.pop(ident, None)
        if "error" in msg: raise RuntimeError(msg["error"])
        return msg.get("result")

    def list_tools(self):
        self.start(); return self.request("tools/list", {}).get("tools", [])

    def call_tool(self, name, arguments):
        self.start(); return self.request("tools/call", {"name":name,"arguments":arguments}, timeout=120)

    def close(self):
        if self.proc and self.proc.poll() is None: self.proc.terminate()
