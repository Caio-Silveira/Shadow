import json, os, urllib.request, urllib.error

class CompatibleResponsesProvider:
    def __init__(self, provider):
        self.provider=provider
        if provider=="deepseek":
            self.model=os.getenv("SHADOW_DEEPSEEK_MODEL","deepseek-flash")
            self.key=os.getenv("DEEPSEEK_API_KEY")
            self.api=os.getenv("SHADOW_DEEPSEEK_URL","https://api.deepseek.com/v1/responses")
            if not self.key: raise RuntimeError("DEEPSEEK_API_KEY is not set")
        elif provider=="lmstudio":
            self.model=os.getenv("SHADOW_LMSTUDIO_MODEL","")
            self.key=os.getenv("LM_API_TOKEN","")
            self.api=os.getenv("SHADOW_LMSTUDIO_URL","http://127.0.0.1:1234/v1/responses")
            if not self.model: raise RuntimeError("SHADOW_LMSTUDIO_MODEL is not set")
        else: raise RuntimeError(f"unsupported compatible provider: {provider}")

    def _post(self,payload):
        headers={"Content-Type":"application/json"}
        if self.key: headers["Authorization"]=f"Bearer {self.key}"
        req=urllib.request.Request(self.api,data=json.dumps(payload).encode(),headers=headers,method="POST")
        try:
            with urllib.request.urlopen(req,timeout=180) as r:return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{self.provider} HTTP {e.code}: {e.read().decode('utf-8','replace')}")

    def create(self,*,instructions,text,tools):
        payload={"model":self.model,"instructions":instructions,"input":text,"tools":tools,"tool_choice":"auto"}
        resp=self._post(payload); resp["_shadow_input"]=text; resp["_shadow_instructions"]=instructions; return resp

    def continue_with_tool_outputs(self,previous,outputs,tools):
        if self.provider=="lmstudio" and previous.get("id"):
            payload={"model":self.model,"previous_response_id":previous["id"],"input":outputs,"tools":tools,"tool_choice":"auto"}
        else:
            prior=previous.get("_shadow_input")
            items=[{"role":"user","content":prior}] if isinstance(prior,str) else list(prior or [])
            items.extend(previous.get("output") or []); items.extend(outputs)
            payload={"model":self.model,"instructions":previous.get("_shadow_instructions",""),"input":items,"tools":tools,"tool_choice":"auto"}
        resp=self._post(payload); resp["_shadow_input"]=payload.get("input"); resp["_shadow_instructions"]=previous.get("_shadow_instructions",""); return resp
