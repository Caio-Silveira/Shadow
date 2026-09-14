import base64, json, os, time, urllib.request, urllib.error

BASE = "https://generativelanguage.googleapis.com/v1beta/models"

class GoogleProvider:
    def __init__(self, model=None):
        self.model = model or os.getenv("SHADOW_GOOGLE_MODEL") or os.getenv("SHADOW_MODEL") or "gemini-3.6-flash"
        self.key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")

    def _post(self, payload):
        url = f"{BASE}/{self.model}:generateContent?key={self.key}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code in (429, 503) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"Google Gemini HTTP {e.code}: {body}")

    @staticmethod
    def _clean_schema(value):
        if isinstance(value, dict):
            out={}
            for k,v in value.items():
                if k in {"$schema","additionalProperties","const","$id","title","default","examples"}:
                    continue
                if k in {"anyOf","oneOf"}:
                    choices=[GoogleProvider._clean_schema(x) for x in v if isinstance(x,dict)]
                    nonnull=[x for x in choices if x.get("type") != "null"]
                    if nonnull: return nonnull[0]
                    continue
                out[k]=GoogleProvider._clean_schema(v)
            return out
        if isinstance(value, list):
            return [GoogleProvider._clean_schema(x) for x in value]
        return value

    @staticmethod
    def _tools(tools):
        decl=[]
        for t in tools:
            decl.append({
                "name": t["name"],
                "description": t.get("description", "")[:2000],
                "parameters": GoogleProvider._clean_schema(t.get("parameters") or {"type":"object","properties":{}}),
            })
        return [{"functionDeclarations": decl}] if decl else []

    def create(self, *, instructions, text, tools, image_path=None):
        parts=[{"text":text}]
        if image_path and os.path.isfile(image_path):
            with open(image_path, "rb") as f:
                encoded=base64.b64encode(f.read()).decode("ascii")
            parts.append({"inlineData":{"mimeType":"image/jpeg","data":encoded}})
        payload={
            "systemInstruction": {"parts":[{"text":instructions}]},
            "contents":[{"role":"user","parts":parts}],
            "tools": self._tools(tools),
        }
        resp=self._post(payload)
        resp["_shadow_contents"] = payload["contents"]
        return resp

    def continue_with_tool_outputs(self, previous_response, outputs, tools):
        contents=list(previous_response.get("_shadow_contents") or [])
        candidate=(previous_response.get("candidates") or [{}])[0]
        model_content=candidate.get("content")
        if model_content:
            contents.append(model_content)
        parts=[]
        for item in outputs:
            parts.append({"functionResponse":{"name":item["name"],"response":item["response"]}})
        contents.append({"role":"user","parts":parts})
        payload={"contents":contents,"tools":self._tools(tools)}
        resp=self._post(payload)
        resp["_shadow_contents"] = contents
        return resp
