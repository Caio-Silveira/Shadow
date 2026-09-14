import argparse, json, os, sys, subprocess
from .mcp_dc import DesktopCommanderMCP
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider

ROOT = os.path.expanduser(os.getenv("SHADOW_HOME", "~/.local/share/shadow"))

def read_text(path, fallback=""):
    try:
        with open(path, encoding="utf-8") as f: return f.read()
    except FileNotFoundError: return fallback

def mcp_tools(tools):
    out=[]
    for t in tools:
        out.append({"name":t["name"],"description":t.get("description","")[:2000],"parameters":t.get("inputSchema") or {"type":"object","properties":{}}})
    return out

def openai_tools(tools):
    return [{"type":"function", **t} for t in mcp_tools(tools)]

def extract_openai_text(resp):
    if resp.get("output_text"): return resp["output_text"]
    chunks=[]
    for item in resp.get("output",[]):
        if item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type") in ("output_text","text") and c.get("text"): chunks.append(c["text"])
    return "\n".join(chunks).strip()

def openai_calls(resp):
    return [x for x in resp.get("output",[]) if x.get("type")=="function_call"]

def extract_google_text(resp):
    chunks=[]
    for cand in resp.get("candidates",[]):
        for p in (cand.get("content") or {}).get("parts",[]):
            if p.get("text"): chunks.append(p["text"])
    return "\n".join(chunks).strip()

def google_calls(resp):
    calls=[]
    for cand in resp.get("candidates",[]):
        for p in (cand.get("content") or {}).get("parts",[]):
            fc=p.get("functionCall")
            if fc: calls.append(fc)
    return calls

SAFE_TOOLS = {"get_config","read_file","read_multiple_files","list_directory","start_search","get_more_search_results","stop_search","read_process_output"}

def approve_tool(name, args):
    if name in SAFE_TOOLS: return True
    helper=os.path.expanduser("~/.local/bin/shadow-approve")
    if not os.path.exists(helper): return False
    detail=json.dumps(args, ensure_ascii=False)[:1200]
    r=subprocess.run([helper, f"Desktop action: {name}", "Shadow wants to use a desktop tool that can change or execute something.", detail], stdout=subprocess.DEVNULL)
    return r.returncode == 0

def provider_name():
    return os.getenv("SHADOW_PROVIDER", "openai").strip().lower()

def run_turn(text):
    provider_id=provider_name()
    dc=DesktopCommanderMCP().start()
    try:
        raw_tools=dc.list_tools()
        identity=read_text(os.path.join(ROOT,"prompts","shadow.md"), "You are Shadow, a desktop companion.")
        observer=read_text(os.path.join(ROOT,"prompts","observer.md"), "")
        instructions=(identity+"\n\nInternal critical review:\n"+observer+"\n\nUse Desktop Commander tools only when needed. Prefer targeted reads/actions. Never expose secrets. Ask for approval before destructive or high-impact actions.")
        if provider_id == "google":
            tools=mcp_tools(raw_tools); provider=GoogleProvider(); resp=provider.create(instructions=instructions,text=text,tools=tools)
            loops=0
            while True:
                calls=google_calls(resp)
                if not calls: return extract_google_text(resp), resp
                outputs=[]
                for call in calls:
                    loops += 1
                    if loops > 24: raise RuntimeError("tool loop limit reached")
                    name=call["name"]; args=call.get("args") or {}
                    result={"denied":True,"reason":"User approval required and was not granted."} if not approve_tool(name,args) else dc.call_tool(name,args)
                    limit=int(os.getenv("SHADOW_TOOL_OUTPUT_CHARS","24000"))
                    raw=json.dumps(result,ensure_ascii=False)[:limit]
                    try: response=json.loads(raw)
                    except Exception: response={"result":raw}
                    outputs.append({"name":name,"response":response})
                resp=provider.continue_with_tool_outputs(resp,outputs,tools)
        elif provider_id == "openai":
            tools=openai_tools(raw_tools); provider=OpenAIProvider(); resp=provider.create(instructions=instructions,text=text,tools=tools)
            loops=0
            while True:
                calls=openai_calls(resp)
                if not calls: return extract_openai_text(resp), resp
                outputs=[]
                for call in calls:
                    loops += 1
                    if loops > 24: raise RuntimeError("tool loop limit reached")
                    try: args=json.loads(call.get("arguments") or "{}")
                    except Exception: args={}
                    result={"denied":True,"reason":"User approval required and was not granted."} if not approve_tool(call["name"],args) else dc.call_tool(call["name"],args)
                    limit=int(os.getenv("SHADOW_TOOL_OUTPUT_CHARS","24000"))
                    outputs.append({"type":"function_call_output","call_id":call["call_id"],"output":json.dumps(result,ensure_ascii=False)[:limit]})
                resp=provider.continue_with_tool_outputs(resp["id"],outputs,tools)
        else:
            raise RuntimeError(f"Unsupported SHADOW_PROVIDER: {provider_id}")
    finally: dc.close()

def main():
    p=argparse.ArgumentParser(prog="shadow-api")
    p.add_argument("text", nargs="*"); p.add_argument("--stdin", action="store_true"); p.add_argument("--json", action="store_true")
    a=p.parse_args(); text=sys.stdin.read().strip() if a.stdin else " ".join(a.text).strip()
    if not text: p.error("message required")
    answer, raw=run_turn(text)
    if a.json: print(json.dumps({"provider":provider_name(),"text":answer},ensure_ascii=False))
    else: print(answer)
if __name__=="__main__": main()
