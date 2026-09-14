import argparse, json, os, subprocess, sys
from .mcp_dc import DesktopCommanderMCP
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider
from .anthropic_provider import AnthropicProvider
from .compatible_provider import CompatibleResponsesProvider
from .permissions import approve_calls

ROOT = os.path.expanduser(os.getenv("SHADOW_HOME", "~/.local/share/shadow"))
HISTORY = os.path.expanduser("~/.local/share/shadow/runtime/conversation.json")

def read_text(path, fallback=""):
    try:
        with open(path, encoding="utf-8") as f: return f.read()
    except FileNotFoundError: return fallback

def recent_history():
    try:
        data=json.load(open(HISTORY,encoding="utf-8"))[-4:]
        return "\n".join(f"User: {x['user']}\nShadow: {x['shadow']}" for x in data)
    except Exception: return ""

def remember_turn(user, shadow):
    os.makedirs(os.path.dirname(HISTORY),exist_ok=True)
    try: data=json.load(open(HISTORY,encoding="utf-8"))
    except Exception: data=[]
    data=(data+[{"user":user,"shadow":shadow}])[-8:]
    with open(HISTORY,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False)
    os.chmod(HISTORY,0o600)

ACTIVE_TOOLS={"read_file","read_multiple_files","write_file","create_directory","list_directory","move_file","start_search","get_more_search_results","stop_search","get_file_info","edit_block","start_process","read_process_output","interact_with_process","list_sessions","list_processes","kill_process"}

def mcp_tools(tools):
    out=[]
    for t in tools:
        if t["name"] not in ACTIVE_TOOLS: continue
        out.append({"name":t["name"],"description":t.get("description","")[:600],"parameters":t.get("inputSchema") or {"type":"object","properties":{}}})
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

def anthropic_text(resp):
    return "\n".join(x.get("text","") for x in resp.get("content",[]) if x.get("type")=="text").strip()

def anthropic_calls(resp):
    return [x for x in resp.get("content",[]) if x.get("type")=="tool_use"]

def provider_name():
    return os.getenv("SHADOW_PROVIDER", "openai").strip().lower()

def wants_screen(text):
    t=text.lower()
    cues=("o que você está vendo", "o que voce esta vendo", "minha tela", "na tela", "olha a tela", "veja a tela", "vê na tela", "ver na tela", "screen")
    return any(c in t for c in cues)

def capture_screen():
    helper=os.path.expanduser("~/.local/bin/dc-vision")
    if not os.path.exists(helper): return None
    try:
        r=subprocess.run([helper,"frame"], capture_output=True, text=True, timeout=10, check=True)
        path=r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return path if path and os.path.isfile(path) else None
    except Exception:
        return None

def run_turn(text):
    provider_id=provider_name()
    image_path=capture_screen() if (provider_id == "google" and wants_screen(text)) else None
    dc=DesktopCommanderMCP().start()
    try:
        raw_tools=dc.list_tools()
        identity=read_text(os.path.join(ROOT,"prompts","shadow.md"), "You are Shadow, a desktop companion.")
        observer=read_text(os.path.join(ROOT,"prompts","observer.md"), "")
        history=recent_history()
        instructions=(identity+"\n\nConversation style: This is a live spoken conversation. Answer naturally, directly and usually briefly. Avoid markdown formatting in ordinary speech. Do not restate the user request.\n\nRecent conversation (context only):\n"+history+"\n\nInternal critical review:\n"+observer+"\n\nUse Desktop Commander tools whenever the user asks you to act on the computer. You can use start_process with installed desktop utilities. Desktop Commander itself runs headless, BUT ~/.local/bin/gui-run bridges commands into the user active X11 desktop (DISPLAY=:0); therefore GUI control IS available. Always use absolute /home/silverdev/.local/bin/gui-run (not a bare gui-run) for wmctrl, xdotool, playerctl, gdbus and GUI application launches. Do not claim you lack GUI control merely because there is no dedicated app API. For GUI tasks, inspect visible windows with wmctrl, focus the target window, then use keyboard/mouse automation when appropriate and verify the result when practical. For media players prefer playerctl. If the user asks to calculate something specifically in the Calculator app, actually interact with that app instead of merely computing the answer yourself. IMPORTANT: when you claim an external action is done, it must have been performed by a tool in this turn. Never say an app was opened, a song was started, a window was changed, or a GUI action completed unless you actually executed and, when practical, verified it. For X11 GUI actions through start_process, prefix commands with /home/silverdev/.local/bin/gui-run so DISPLAY/XAUTHORITY are correct. Do not infer GUI is unavailable from Desktop Commander own headless environment; test via /home/silverdev/.local/bin/gui-run wmctrl -l first. Example: ~/.local/bin/gui-run wmctrl -l; ~/.local/bin/gui-run wmctrl -a Calculator; ~/.local/bin/gui-run xdotool key 2 plus 2 Return. Spotify is controllable with ~/.local/bin/gui-run playerctl --player=spotify play-pause/next/previous and its window can be focused with wmctrl; do not claim a dedicated API is required for ordinary playback controls. Prefer targeted reads/actions. Never expose secrets. Ask for approval before destructive or high-impact actions.")
        if provider_id == "google":
            tools=mcp_tools(raw_tools); provider=GoogleProvider(); screen_instructions=instructions + ("\n\nA JPEG image is attached to this user turn. It is a fresh capture of the user current desktop screen. Analyze what is visibly present in that image and answer from it; do not claim you cannot see the screen." if image_path else ""); resp=provider.create(instructions=screen_instructions,text=text,tools=tools,image_path=image_path)
            loops=0
            while True:
                calls=google_calls(resp)
                if not calls:
                    answer=extract_google_text(resp); remember_turn(text,answer); return answer, resp
                pairs=[(call["name"], call.get("args") or {}) for call in calls]
                approved=approve_calls(pairs)
                outputs=[]
                for call in calls:
                    loops += 1
                    if loops > 24: raise RuntimeError("tool loop limit reached")
                    name=call["name"]; args=call.get("args") or {}
                    result={"denied":True,"reason":"User approval required and was not granted."} if not approved else dc.call_tool(name,args)
                    limit=int(os.getenv("SHADOW_TOOL_OUTPUT_CHARS","24000"))
                    raw=json.dumps(result,ensure_ascii=False)[:limit]
                    try: response=json.loads(raw)
                    except Exception: response={"result":raw}
                    outputs.append({"name":name,"response":response})
                resp=provider.continue_with_tool_outputs(resp,outputs,tools)
        elif provider_id == "anthropic":
            tools=mcp_tools(raw_tools); provider=AnthropicProvider(); resp=provider.create(instructions=instructions,text=text,tools=tools)
            loops=0
            while True:
                calls=anthropic_calls(resp)
                if not calls:
                    answer=anthropic_text(resp); remember_turn(text,answer); return answer,resp
                parsed=[(c["name"],c.get("input") or {}) for c in calls]
                approved=approve_calls(parsed); outputs=[]
                for call in calls:
                    loops += 1
                    if loops > 24: raise RuntimeError("tool loop limit reached")
                    result={"denied":True,"reason":"User approval required and was not granted."} if not approved else dc.call_tool(call["name"],call.get("input") or {})
                    outputs.append({"id":call["id"],"content":json.dumps(result,ensure_ascii=False)[:int(os.getenv("SHADOW_TOOL_OUTPUT_CHARS","24000"))]})
                resp=provider.continue_with_tool_outputs(resp,outputs,tools)
        elif provider_id in {"openai","deepseek","lmstudio"}:
            tools=openai_tools(raw_tools); provider=OpenAIProvider() if provider_id=="openai" else CompatibleResponsesProvider(provider_id); resp=provider.create(instructions=instructions,text=text,tools=tools)
            loops=0
            while True:
                calls=openai_calls(resp)
                if not calls:
                    answer=extract_openai_text(resp); remember_turn(text,answer); return answer, resp
                parsed=[]
                for call in calls:
                    try: args=json.loads(call.get("arguments") or "{}")
                    except Exception: args={}
                    parsed.append((call,args))
                approved=approve_calls([(call["name"],args) for call,args in parsed])
                outputs=[]
                for call,args in parsed:
                    loops += 1
                    if loops > 24: raise RuntimeError("tool loop limit reached")
                    result={"denied":True,"reason":"User approval required and was not granted."} if not approved else dc.call_tool(call["name"],args)
                    limit=int(os.getenv("SHADOW_TOOL_OUTPUT_CHARS","24000"))
                    outputs.append({"type":"function_call_output","call_id":call["call_id"],"output":json.dumps(result,ensure_ascii=False)[:limit]})
                resp=provider.continue_with_tool_outputs(resp["id"],outputs,tools) if provider_id=="openai" else provider.continue_with_tool_outputs(resp,outputs,tools)
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
