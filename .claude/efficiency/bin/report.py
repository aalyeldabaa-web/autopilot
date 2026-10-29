#!/usr/bin/env python3
"""Efficiency report. Usage: report.py [N] [--task <id>] [--session <id>]
Prints: task table (last N), per-model usage with per-model cost, per-agent timings with intended vs actual
model, recorded routing decisions, gate runs with exit codes, and a Mermaid diagram for the selected task.
Every number is labeled measured / derived / estimated / unavailable. No model calls are made."""
import sys, json, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C
import telemetry as T
import gate
FENCE = "`" * 3   # built at runtime so this file can itself live inside a fenced block

def k(x): return f"{x//1000}k" if isinstance(x, int) else "?"

def load():
    tasks = C.read_jsonl(C.logs_dir() / "tasks.jsonl"); subs = C.read_jsonl(C.logs_dir() / "subagents.jsonl"); gates = C.read_jsonl(C.logs_dir() / "gates.jsonl")
    for sp in sorted((C.logs_dir() / "sessions").glob("*.json"), key=lambda x: x.stat().st_mtime):   # tasks still open in live sessions
        st = C.jload(sp, {}); t = st.get("task")
        if t and not any(x["task_id"] == t["task_id"] for x in tasks):
            t = dict(t); t.setdefault("main", {"by_model": {}, "kind": "open"}); t["status"] = "open"; t["duration_s"] = None; t["usage_kind"] = "open (not yet measured)"; tasks.append(t)
    by_task = {}
    for s in subs: by_task.setdefault(s.get("task_id"), []).append(s)
    for t in tasks:
        seen = {s["agent_id"] for s in t.get("subagents", [])}
        for s in by_task.get(t["task_id"], []):
            if s["agent_id"] not in seen: t.setdefault("subagents", []).append(s); seen.add(s["agent_id"])   # late (background) agents
        agg = T.merge({}, (t.get("main") or {}).get("by_model", {}))
        for s in t.get("subagents", []):
            if s.get("kind") == "measured": T.merge(agg, s.get("by_model", {}))
        t["by_model"] = agg; t["totals"] = {kk: sum(u[kk] for u in agg.values()) for kk in T.EMPTY()} if agg else T.EMPTY()
        t["est_api_cost_usd"], t["cost_kind"], t["cost_by_model"] = T.cost_by_model(agg)
    return tasks, gates, subs

def score(tasks, gates, subs):
    """Verdicts only for the rows that will be shown; the git revision is computed once."""
    rev = gate.tree_revision()
    for t in tasks: t["verdict"], t["gate_runs"], t["verdict_reason"] = gate.verdict_for(t["task_id"], t.get("class"), t.get("flags"), revision=rev, records=gates, subagents=subs)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("n", nargs="?", type=int, default=10); ap.add_argument("--task"); ap.add_argument("--session")
    a = ap.parse_args(); tasks, gates, subs = load()
    if a.session: tasks = [t for t in tasks if t.get("session_id") == a.session]
    shown = tasks[-a.n:] + [t for t in tasks if t["task_id"] == a.task and t not in tasks[-a.n:]]
    score(shown, gates, subs)
    print("| task | class/conf | classifier route | decisions recorded | agents (intended>actual) | tokens total / cache-read | est cost | dur | gate verdict |")
    print("|---|---|---|---|---|---|---|---|---|")
    for t in tasks[-a.n:]:
        ag = ", ".join(f"{s['agent_type']}:{s['intended_model']}>{'/'.join(s['models']) or '?'}{'' if s.get('model_match') in (True, None) else ' MISMATCH'}" for s in t.get("subagents", [])) or "none"
        dec = " / ".join(t.get("decisions") or []) or "none captured"
        cost = t.get("est_api_cost_usd"); costs = f"${cost:.4f} ({t.get('cost_kind')})" if cost is not None else f"unavailable"
        print(f"| {t['task_id']} | {t.get('class')}/{t.get('confidence','?')} | {t.get('route')} | {dec[:80].replace('|','/')} | {ag} | {k(t['totals'].get('total'))} / {k(t['totals'].get('cache_read'))} ({t.get('usage_kind')}) | {costs} | {t.get('duration_s')}s | {t['verdict']} |")
    print("\nLegend: tokens MEASURED from transcripts per model (usage_kind=measured|partial|unavailable); cost ESTIMATED per model from pricing.json, never the subscription bill; 'decisions recorded' are the route:/override:/done: lines the model printed (model judgment); gate verdict is DERIVED only from commands gate.py executed and reviews backed by hook-recorded reviewer runs, all at the current code revision.")
    sel = next((t for t in tasks if t["task_id"] == a.task), tasks[-1] if tasks else None)
    if not sel: return
    print(f"\n### Task {sel['task_id']}  (class {sel.get('class')}, confidence {sel.get('confidence')}, language {sel.get('language')}, estimate at prompt time: {sel.get('estimate')})")
    print("\n| model | input | output | cache read | cache write | total | est cost | kind |\n|---|---|---|---|---|---|---|---|")
    for m, u in sel["by_model"].items():
        c = (sel.get("cost_by_model") or {}).get(m) or {}
        usd = c.get("usd") if isinstance(c, dict) else None
        print(f"| {m} | {u['input']} | {u['output']} | {u['cache_read']} | {u['cache_write']} | {u['total']} | {('$%.4f' % usd) if usd is not None else 'unpriced'} | measured / {'estimated' if usd is not None else 'unavailable'} |")
    print("\n| agent | intended | actual | effort | start | duration | tokens | attribution | late |\n|---|---|---|---|---|---|---|---|---|")
    for s in sel.get("subagents", []):
        tot = sum(u["total"] for u in s.get("by_model", {}).values())
        print(f"| {s['agent_type']} | {s['intended_model']} | {'/'.join(s['models']) or 'unavailable'} | {'/'.join(s.get('efforts') or []) or '?'} | {s.get('start') or '?'} | {s.get('duration_s')}s | {tot} ({s.get('kind')}) | {s.get('attribution', 'mapped')} | {s.get('late')} |")
    orphans = [x for x in C.read_jsonl(C.logs_dir() / "subagents.jsonl") if x.get("attribution") == "unavailable" and x.get("session_id") == sel.get("session_id")]
    if orphans: print(f"\nunattributed agents in this session (no start mapping; usage counted nowhere): {[(o['agent_type'], o['agent_id']) for o in orphans]}")
    print("\n| gate | command / reviewer | exit / verdict | duration | revision | time |\n|---|---|---|---|---|---|")
    for g in sel["gate_runs"]:
        if g.get("kind") == "review": print(f"| review:{g['reviewer']} | {len(g.get('findings') or [])} findings ({sum(1 for f in g.get('findings') or [] if f.get('blocking') and not f.get('resolved'))} blocking open) | {g['verdict']} | | {g.get('revision', '?')[:12]} | {g['t']} |")
        elif g.get("kind") == "waiver": print(f"| waiver:{g['gate']} | {g.get('reason', '')[:60].replace('|', '/')} | approved by {g.get('approved_by')} | | {g.get('revision', '?')[:12]} | {g['t']} |")
        else: print(f"| {g['gate']} | {g['command'].replace('|','/')} | {g['exit_code']} | {g['duration_s']}s | {g.get('revision', '?')[:12]} | {g['t']} |")
    print(f"\nverdict: {sel['verdict']}  ({sel.get('verdict_reason', '')})")
    mains = "/".join((sel.get("main") or {}).get("by_model", {}).keys()) or "?"
    mtot = sum(u["total"] for u in (sel.get("main") or {}).get("by_model", {}).values())
    print(f"\n{FENCE}mermaid\nflowchart LR\n  U[\"prompt {sel['task_id']}<br/>class {sel.get('class')} ({sel.get('confidence')})<br/>route {sel.get('route')}\"] --> M[\"main: {mains}<br/>{mtot} tokens, {sel.get('duration_s')}s\"]")
    for i, s in enumerate(sel.get("subagents", [])):
        tot = sum(u["total"] for u in s.get("by_model", {}).values())
        print(f"  M --> A{i}[\"{s['agent_type']}: {'/'.join(s['models']) or '?'}<br/>{tot} tokens, {s.get('duration_s')}s{' (late)' if s.get('late') else ''}\"]")
    print(f"  M --> G{{\"gates: {sel['verdict']} ({len(sel['gate_runs'])} runs)\"}}\n{FENCE}")

if __name__ == "__main__":
    main()
