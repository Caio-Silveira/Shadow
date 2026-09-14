import json, os, urllib.request, urllib.error

API = "https://api.openai.com/v1/responses"

class OpenAIProvider:
    def __init__(self, model=None):
        self.model = model or os.getenv("SHADOW_OPENAI_MODEL") or os.getenv("SHADOW_MODEL", "gpt-5.6-luna")
        self.key = os.getenv("OPENAI_API_KEY")
        if not self.key: raise RuntimeError("OPENAI_API_KEY is not set")

    def _post(self, payload):
        req = urllib.request.Request(API, data=json.dumps(payload).encode(), headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"OpenAI HTTP {e.code}: {body}")

    def create(self, *, instructions, text, tools):
        return self._post({"model":self.model,"instructions":instructions,"input":text,"tools":tools,"tool_choice":"auto"})

    def continue_with_tool_outputs(self, previous_response_id, outputs, tools):
        return self._post({"model":self.model,"previous_response_id":previous_response_id,"input":outputs,"tools":tools,"tool_choice":"auto"})
