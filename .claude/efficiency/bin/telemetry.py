#!/usr/bin/env python3
"""Efficiency OS v2.1 telemetry. Invoked by Claude Code hooks: telemetry.py <HookEvent>; hook JSON on stdin.
Session-scoped state (logs/sessions/<id>.json), locked and atomically written. Per-model token accounting
read from transcripts (MEASURED). No prompt text, no tool output, no assistant text is stored: from the
assistant's final message only lines starting with route:/override:/done: are kept, scrubbed and truncated.
Always exits 0: telemetry never blocks work."""
import sys, os, re, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C

DISABLED = os.environ.get("EOS_DISABLED") == "1"
EMPTY = lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0}

def transcript_usage(path, start_line=0):
    """MEASURED. Returns (by_model, efforts, line_count, status).
    by_model: {model: usage} summed from assistant records at or after start_line, deduplicated by message id
    (streamed chunks of one message repeat the usage; the last record for an id wins).
    status: measured | unavailable (file missing/unreadable) | empty (no assistant usage in range)."""
    by_id, efforts, n = {}, set(), start_line
    if not path: return {}, efforts, start_line, "unavailable"
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            for i, line in enumerate(f):
                n = i + 1
                if i < start_line: continue
                try: rec = json.loads(line)
                except Exception: continue
                msg = rec.get("message") or {}
                if msg.get("role") != "assistant" and rec.get("type") != "assistant": continue
                u = msg.get("usage") or {}
                if not u: continue
                key = msg.get("id") or rec.get("requestId") or rec.get("uuid") or f"line{i}"
                by_id[key] = (msg.get("model") or "unknown", u)
                for k in ("effort", "effort_level", "effortLevel"):
                    v = msg.get(k) or rec.get(k)
                    if v: efforts.add(str(v))
    except (FileNotFoundError, PermissionError, OSError):
        return {}, efforts, start_line, "unavailable"
    by_model = {}
    for model, u in by_id.values():
        m = by_model.setdefault(model, EMPTY())
        m["input"] += int(u.get("input_tokens") or 0); m["output"] += int(u.get("output_tokens") or 0)
        m["cache_read"] += int(u.get("cache_read_input_tokens") or 0); m["cache_write"] += int(u.get("cache_creation_input_tokens") or 0)
        m["total"] = m["input"] + m["output"] + m["cache_read"] + m["cache_write"]
    return by_model, efforts, n, ("measured" if by_model else "empty")

PRICE_KEYS = ("input", "output", "cache_read", "cache_write")
def valid_price(p):
    """A price record is usable only if all four categories are present, numeric and strictly positive.
    Zero, null, missing or non-numeric values mean 'unknown', never 'free'."""
    if not isinstance(p, dict): return False
    for k in PRICE_KEYS:
        v = p.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0: return False
    return True

def price_for(model, prices):
    """Longest matching family substring wins (so 'opus-5-5' beats 'opus' if both exist). No cross-model substitution."""
    fams = sorted((k for k in prices if not k.startswith("_") and k in model), key=len, reverse=True)
    for fam in fams:
        if valid_price(prices[fam]): return prices[fam]
    return None

def cost_by_model(by_model, prices=None):
    """ESTIMATE. Each model's tokens times that model's own price. Returns (total_usd or None, kind, detail).
    kind: estimated (all priced) | partial (some models unpriced) | unavailable (nothing priced or no usage).
    A measured zero-token execution with valid prices is a genuine $0 estimate; unknown prices are never $0."""
    prices = prices if prices is not None else C.jload(C.eos_dir() / "pricing.json", {})
    if not by_model: return None, "unavailable", {}
    detail, total, unpriced = {}, 0.0, 0
    for model, u in by_model.items():
        p = price_for(model, prices)
        if not p: detail[model] = {"usd": None, "state": "unpriced", "tokens": u.get("total", 0)}; unpriced += 1; continue
        parts = {k: round(u[k] * p[k] / 1e6, 6) for k in PRICE_KEYS}
        c = sum(parts.values()); detail[model] = {"usd": round(c, 6), "state": "estimated", "by_category": parts}; total += c
    if unpriced == len(by_model): return None, "unavailable", detail
    return round(total, 6), ("estimated" if unpriced == 0 else "partial"), detail

def merge(dst, src):
    for model, u in src.items():
        m = dst.setdefault(model, EMPTY())
        for k in m: m[k] += u.get(k, 0)
    return dst

def intended_model(agent_type):
    for d in (C.project_root() / ".claude" / "agents", pathlib.Path.home() / ".claude" / "agents"):
        f = d / f"{agent_type}.md"
        if f.exists():
            m = re.search(r"^model:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
            return m.group(1) if m else "inherit"
    return "builtin"

def new_task(st, inp):
    tid = C.datetime.datetime.now(C.datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + C.sha(st.get("session_id", "") + C.now() + str(os.getpid()))[:4]
    prompt = inp.get("prompt") or ""
    try:
        import classify
        c = classify.classify(prompt, C.jload(C.eos_dir() / "env.json", {}), C.jload(C.eos_dir() / "calibration.json", {}), C.config())
    except Exception as e:
        c = {"class": "?", "route": "unclassified", "flags": [], "gates": "?", "estimate": f"classifier error: {str(e)[:80]}", "confidence": "low", "language": "?"}
    st["task"] = {"task_id": tid, "session_id": st.get("session_id"), "start": C.now(), "start_ts": C.ts(),
                  "cursor": st.get("cursor", 0), "prompt_words": len(prompt.split()), "language": c.get("language"),
                  "class": c["class"], "confidence": c.get("confidence"), "route": c["route"], "flags": c["flags"],
                  "gates": c["gates"], "estimate": c["estimate"], "subagents": [], "open_agents": {}, "decisions": [], "status": None}
    return c, tid

def close_task(st, status):
    task = st.get("task")
    if not task: return
    by_model, efforts, n, kind = transcript_usage(st.get("transcript_path", ""), task.get("cursor", 0))
    st["cursor"] = n
    task["main"] = {"by_model": by_model, "efforts": sorted(efforts), "kind": kind}
    task["end"] = C.now(); task["duration_s"] = round(C.ts() - task.pop("start_ts"), 1); task["status"] = task.get("status") or status
    agg = merge({}, by_model)
    parts_unavailable = 0 if kind == "measured" else 1
    for s in task["subagents"]:
        if s.get("kind") == "measured": merge(agg, s["by_model"])
        else: parts_unavailable += 1
    task["by_model"] = agg
    task["totals"] = {k: sum(u[k] for u in agg.values()) for k in EMPTY()} if agg else EMPTY()
    cost, ckind, detail = cost_by_model(agg)
    task["est_api_cost_usd"] = cost; task["cost_kind"] = ckind; task["cost_by_model"] = detail
    task["usage_kind"] = "measured" if parts_unavailable == 0 else ("partial" if agg else "unavailable")
    task.pop("open_agents", None)
    C.append_jsonl(C.logs_dir() / "tasks.jsonl", task)
    st["last_task_id"] = task["task_id"]
    st["last_task"] = {k: task.get(k) for k in ("task_id", "class", "flags", "route", "totals", "status", "duration_s")}
    st["task"] = None

def on_SessionStart(inp, st):
    path = inp.get("transcript_path") or st.get("transcript_path", "")
    st.update({"session_id": inp.get("session_id") or st.get("session_id"), "transcript_path": path, "started": C.now(), "source": inp.get("source")})
    _, _, n, _ = transcript_usage(path, 0)
    st["cursor"] = n  # everything already in the transcript belongs to earlier turns (startup, resume or compact alike)
    if inp.get("source") not in ("resume", "compact"): st["task"] = None

def on_UserPromptSubmit(inp, st):
    close_task(st, "superseded")
    c, tid = new_task(st, inp)
    flags = ",".join(c.get("flags", [])) or "none"
    line = (f"[EOS] task={tid} class={c['class']} conf={c.get('confidence','?')} lang={c.get('language','?')} route={c['route']} "
            f"flags={flags} gates={c['gates']} est=\"{c['estimate']}\" (deterministic first pass; override with a one-line reason if wrong)")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": line}}))

def on_SubagentStart(inp, st):
    """Records the agent -> task mapping in this session's state (locked), so the stop event resolves the ORIGINAL
    task even if that task has closed or another task has started by then."""
    if not st.get("task"): new_task(st, {"prompt": ""}); st["task"]["status"] = "implicit"
    aid = inp.get("agent_id", "?")
    entry = {"agent_type": inp.get("agent_type"), "task_id": st["task"]["task_id"], "start_ts": C.ts(), "start": C.now()}
    st["task"]["open_agents"][aid] = entry
    st.setdefault("agent_map", {})[aid] = entry

def on_SubagentStop(inp, st):
    aid = inp.get("agent_id", "?")
    recorded = st.setdefault("agents_recorded", [])
    if aid in recorded:
        C.append_jsonl(C.logs_dir() / "events.jsonl", {"t": C.now(), "event": "subagent_stop_duplicate_ignored", "agent_id": aid, "session_id": st.get("session_id")}); return
    mapped = (st.get("agent_map") or {}).pop(aid, None)
    task = st.get("task")
    owner_open = bool(task and mapped and task.get("task_id") == mapped.get("task_id"))
    if owner_open: task["open_agents"].pop(aid, None)
    by_model, efforts, _, kind = transcript_usage(inp.get("agent_transcript_path", ""), 0)
    atype = inp.get("agent_type") or (mapped or {}).get("agent_type") or "unknown"
    intended = intended_model(atype); actual = sorted(by_model)
    match = None if (intended in ("inherit", "builtin") or not actual) else all(intended.split("[")[0] in m for m in actual)
    rec = {"agent_id": aid, "agent_type": atype, "intended_model": intended, "models": actual, "efforts": sorted(efforts),
           "model_match": match, "by_model": by_model, "kind": kind, "start": (mapped or {}).get("start"), "end": C.now_us(),
           "duration_s": round(C.ts() - mapped["start_ts"], 1) if mapped else None,
           "task_id": (mapped or {}).get("task_id"), "attribution": "mapped" if mapped else "unavailable",
           "session_id": st.get("session_id"), "late": not owner_open}
    if owner_open: task["subagents"].append(rec)             # aggregated at close_task
    C.append_jsonl(C.logs_dir() / "subagents.jsonl", rec)    # authoritative; late records are joined by task_id at report time, once
    recorded.append(aid); st["agents_recorded"] = recorded[-500:]

def on_Stop(inp, st):
    task = st.get("task")
    if task:
        msg = inp.get("last_assistant_message") or ""
        for m in re.finditer(r"^\s*(route|override|done):\s*(.+)$", msg, re.M | re.I):
            task["decisions"].append(C.scrub(f"{m.group(1).lower()}: {m.group(2)}", 200))
        task["decisions"] = task["decisions"][-6:]
    close_task(st, "ended_turn")

def on_PreCompact(inp, st): st["compactions"] = st.get("compactions", 0) + 1

def on_SessionEnd(inp, st):
    close_task(st, "session_end"); st["ended"] = C.now(); st["end_reason"] = inp.get("reason")

def main():
    if DISABLED: return
    event = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    try: inp = json.load(sys.stdin)
    except Exception: inp = {}
    sid = inp.get("session_id") or (C.most_recent_session() if event in ("SubagentStart", "SubagentStop", "Stop") else None) or "nosession"
    C.append_jsonl(C.logs_dir() / "events.jsonl", {"t": C.now(), "event": event, "session_id": sid, "agent_id": inp.get("agent_id"),
                   "agent_type": inp.get("agent_type"), "source": inp.get("source"), "reason": inp.get("reason"), "trigger": inp.get("trigger")})
    handler = globals().get("on_" + event)
    if not handler: return
    try:
        with C.session_state(sid) as st:
            handler(inp, st)
    except Exception as e:
        C.append_jsonl(C.logs_dir() / "events.jsonl", {"t": C.now(), "event": "telemetry_error", "where": event, "err": str(e)[:300]})

if __name__ == "__main__":
    try: main()
    except Exception: pass
    sys.exit(0)
