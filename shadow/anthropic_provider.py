import json, os, urllib.request, urllib.error

API = "https://api.anthropic.com/v1/messages"

class AnthropicProvider:
    def __init__(self, model=None):
        self.model = model or os.getenv("SHADOW_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        self.key = os.getenv("ANTHROPIC_API_KEY")
        if not self.key: raise RuntimeError("ANTHROPIC_API_KEY is not set")

    def _post(self, payload):
        req=urllib.request.Request(API,data=json.dumps(payload).encode(),headers={"x-api-key":self.key,"anthropic-version":"2023-06-01","content-type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=180) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Anthropic HTTP {e.code}: {e.read().decode('utf-8','replace')}")

    @staticmethod
    def tools(items):
        return [{"name":t["name"],"description":t.get("description","")[:2000],"input_schema":t.get("parameters") or {"type":"object","properties":{}}} for t in items]

    def create(self, *, instructions, text, tools):
        payload={"model":self.model,"max_tokens":1024,"system":instructions,"messages":[{"role":"user","content":text}],"tools":self.tools(tools)}
        resp=self._post(payload); resp["_shadow_messages"]=payload["messages"]; return resp

    def continue_with_tool_outputs(self, previous, outputs, tools):
        messages=list(previous.get("_shadow_messages") or [])
        messages.append({"role":"assistant","content":previous.get("content",[])})
        messages.append({"role":"user","content":[{"type":"tool_result","tool_use_id":x["id"],"content":x["content"]} for x in outputs]})
        payload={"model":self.model,"max_tokens":1024,"messages":messages,"tools":self.tools(tools)}
        resp=self._post(payload); resp["_shadow_messages"]=messages; return resp
