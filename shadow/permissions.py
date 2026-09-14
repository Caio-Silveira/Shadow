import hashlib, json, os, re, subprocess

ROOT = os.path.expanduser(os.getenv("SHADOW_HOME", "~/.local/share/shadow"))
STORE = os.path.join(ROOT, "config", "remembered_permissions.json")
APPROVER = os.path.expanduser("~/.local/bin/shadow-approve")

SAFE_TOOLS = {
    "get_config", "read_file", "read_multiple_files", "list_directory",
    "start_search", "get_more_search_results", "stop_search", "list_searches",
    "get_file_info", "read_process_output", "list_sessions", "list_processes",
    "get_usage_stats", "get_recent_tool_calls",
}

TOOL_SCOPES = {
    "write_file": "filesystem_write", "write_pdf": "filesystem_write",
    "create_directory": "filesystem_write", "move_file": "filesystem_write",
    "edit_block": "filesystem_write",
    "start_process": "command_execution", "interact_with_process": "command_execution",
    "force_terminate": "process_control", "kill_process": "process_control",
    "give_feedback_to_desktop_commander": "external_feedback",
    "get_prompts": "desktop_workflow",
}

ALWAYS_ASK = {"set_config_value"}
DANGEROUS_CMD = re.compile(r"(^|\s)(sudo|su|rm\s+-r|rm\s+-f|dd\s+if=|mkfs|shutdown|reboot|poweroff|passwd|iptables|nft|ufw|apt\s+(install|remove|purge)|dnf\s+(install|remove)|pacman\s+-S|curl.+\|\s*(sh|bash)|wget.+\|\s*(sh|bash))\b", re.I)

def _load():
    try:
        with open(STORE, encoding="utf-8") as f:
            data=json.load(f)
            if isinstance(data, dict): return data
    except Exception:
        pass
    return {"scopes": [], "exact": []}

def _save(data):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp=STORE+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    os.chmod(tmp,0o600); os.replace(tmp,STORE)

def _scope(name):
    return TOOL_SCOPES.get(name, f"tool:{name}")

def _summary(name,args):
    if name=="start_process": return f"start_process: {str(args.get('command',''))[:180]}"
    if name in {"write_file","write_pdf","edit_block"}: return f"{name}: {args.get('path') or args.get('file_path') or 'target'}"
    if name=="move_file": return f"move_file: {args.get('source','?')} -> {args.get('destination','?')}"
    if name in {"kill_process","force_terminate"}: return f"{name}: pid/session {args.get('pid') or args.get('sessionId') or '?'}"
    clean={k:v for k,v in args.items() if 'key' not in k.lower() and 'token' not in k.lower() and 'secret' not in k.lower()}
    return f"{name}: {json.dumps(clean,ensure_ascii=False)[:180]}"

def _high_risk(name,args):
    if name in ALWAYS_ASK: return True
    if name=="start_process" and DANGEROUS_CMD.search(str(args.get("command",""))): return True
    return False

def approve_calls(calls):
    data=_load(); scopes=set(data.get("scopes",[])); exact=set(data.get("exact",[]))
    pending=[]; risky=[]
    for name,args in calls:
        if name in SAFE_TOOLS: continue
        summary=_summary(name,args)
        if _high_risk(name,args):
            digest=hashlib.sha256(summary.encode()).hexdigest()
            if digest not in exact: risky.append((digest,summary))
            continue
        scope=_scope(name)
        if scope not in scopes: pending.append((scope,summary))
    if not pending and not risky: return True
    lines=[]
    if pending:
        lines.append("Permissões que serão lembradas:")
        for scope,summary in pending: lines.append(f"• {scope}: {summary}")
    if risky:
        lines.append("\nAções sensíveis aprovadas somente desta vez:")
        for _,summary in risky: lines.append(f"• {summary}")
    detail="\n".join(lines)[:5000]
    if not os.path.exists(APPROVER): return False
    r=subprocess.run([APPROVER,"Permissões do Shadow","Revise a lista abaixo. Um único clique em Permitir autoriza este lote; permissões comuns ficam memorizadas.",detail],stdout=subprocess.DEVNULL)
    if r.returncode != 0: return False
    for scope,_ in pending: scopes.add(scope)
    data["scopes"]=sorted(scopes); data["exact"]=sorted(exact)
    _save(data)
    return True

def list_permissions():
    return _load()

def reset_permissions():
    _save({"scopes":[],"exact":[]})

def main():
    import argparse
    p=argparse.ArgumentParser(prog="shadow-permissions")
    p.add_argument("action", choices=["list","reset"], nargs="?", default="list")
    a=p.parse_args()
    if a.action=="reset":
        reset_permissions(); print("Shadow remembered permissions cleared.")
    else:
        print(json.dumps(list_permissions(), ensure_ascii=False, indent=2))

if __name__=="__main__":
    main()
