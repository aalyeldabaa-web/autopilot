#!/usr/bin/env python3
"""Status line: model | context% | current task class and route | open agents | last task tokens and gate verdict.
Reads this session's own state file (session_id from the status payload), so concurrent sessions never mix."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    import common as C
    inp = json.load(sys.stdin)
except Exception:
    inp = {}; C = None
model = ((inp.get("model") or {}).get("display_name") or (inp.get("model") or {}).get("id") or "?").replace("Claude ", "")
ctx = (inp.get("context_window") or {}).get("used_percentage")
parts = [model, (f"ctx {ctx:.0f}%" + (" !" if ctx >= 60 else "")) if isinstance(ctx, (int, float)) else "ctx ?"]
st = C.jload(C.session_path(inp.get("session_id")), {}) if (C and inp.get("session_id")) else {}
t = st.get("task")
if t:
    parts.append(f"{t.get('class', '?')} {t.get('route', '')}")
    n = len(t.get("open_agents") or {})
    if n: parts.append(f"agents {n}")
lt = st.get("last_task")
if lt and lt.get("totals"):
    try:
        import gate; v, _, _ = gate.verdict_for(lt["task_id"], lt.get("class"), lt.get("flags"), check_stale=False)
    except Exception: v = "?"
    parts.append(f"last {lt['totals'].get('total', 0) // 1000}k {'✓' if v == 'PASS' else '✗' if v == 'FAIL' else '·'}")
print(" | ".join(parts))
