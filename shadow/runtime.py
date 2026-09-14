import argparse, json, os, sys, subprocess
from .mcp_dc import DesktopCommanderMCP
from .openai_provider import OpenAIProvider

ROOT = os.path.expanduser(os.getenv("SHADOW_HOME", "~/.local/share/shadow"))

def read_text(path, fallback=""):
    try:
        with open(path, encoding="utf-8") as f: return f.read()
    except FileNotFoundError: return fallback

def mcp_tools_to_openai(tools):
    out=[]
    for t in tools:
        out.append({"type":"function","name":t["name"],"description":t.get("description","")[:2000],"parameters":t.get("inputSchema") or {"type":"object","properties":{}}})
    return out

def extract_text(resp):
    if resp.get("output_text"): return resp["output_text"]
    chunks=[]
    for item in resp.get("output",[]):
        if item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type") in ("output_text","text") and c.get("text"): chunks.append(c["text"])
    return "\n".join(chunks).strip()

def function_calls(resp):
    return [x for x in resp.get("output",[]) if x.get("type")=="function_call"]

SAFE_TOOLS = {
    "get_config", "read_file", "read_multiple_files", "list_directory",
    "start_search", "get_more_search_results", "stop_search",
    "read_process_output"
}

def approve_tool(name, args):
    if name in SAFE_TOOLS:
        return True
    helper=os.path.expanduser("~/.local/bin/shadow-approve")
    if not os.path.exists(helper):
        return False
    detail=json.dumps(args, ensure_ascii=False)[:1200]
    r=subprocess.run([helper, f"Desktop action: {name}", "Shadow wants to use a desktop tool that can change or execute something.", detail], stdout=subprocess.DEVNULL)
    return r.returncode == 0

def run_turn(text):
    dc=DesktopCommanderMCP().start()
    try:
        raw_tools=dc.list_tools(); tools=mcp_tools_to_openai(raw_tools)
        identity=read_text(os.path.join(ROOT,"prompts","shadow.md"), "You are Shadow, a desktop companion.")
        observer=read_text(os.path.join(ROOT,"prompts","observer.md"), "")
        instructions=(identity+"\n\nInternal critical review:\n"+observer+"\n\nUse Desktop Commander tools only when needed. Prefer targeted reads/actions. Never expose secrets. Ask for approval before destructive or high-impact actions.")
        provider=OpenAIProvider(); resp=provider.create(instructions=instructions,text=text,tools=tools)
        loops=0
        while True:
            calls=function_calls(resp)
            if not calls: return extract_text(resp), resp
            outputs=[]
            for call in calls:
                loops += 1
                if loops > 24: raise RuntimeError("tool loop limit reached")
                try: args=json.loads(call.get("arguments") or "{}")
                except Exception: args={}
                if not approve_tool(call["name"], args):
                    result={"denied": True, "reason": "User approval required and was not granted."}
                else:
                    result=dc.call_tool(call["name"], args)
                limit=int(os.getenv("SHADOW_TOOL_OUTPUT_CHARS", "24000"))
                outputs.append({"type":"function_call_output","call_id":call["call_id"],"output":json.dumps(result,ensure_ascii=False)[:limit]})
            resp=provider.continue_with_tool_outputs(resp["id"],outputs,tools)
    finally: dc.close()

def main():
    p=argparse.ArgumentParser(prog="shadow-api")
    p.add_argument("text", nargs="*")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--json", action="store_true")
    a=p.parse_args(); text=sys.stdin.read().strip() if a.stdin else " ".join(a.text).strip()
    if not text: p.error("message required")
    answer, raw=run_turn(text)
    if a.json: print(json.dumps({"text":answer,"response_id":raw.get("id")},ensure_ascii=False))
    else: print(answer)
if __name__=="__main__": main()
