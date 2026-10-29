#!/usr/bin/env python3
"""Executable quality gates with required reviews, revision binding and recorded waivers.
A gate passes only because of a record this script wrote while running a command, or a review record that is
backed by a hook-recorded subagent execution. There is no self-report path.

  gate.py run [--task <id>] [--name <label>] -- <command ...>        AD-HOC run: recorded, never satisfies a required gate
  gate.py required [--task <id>]                                       runs the EXACT commands registered in gates.json
  gate.py review --task <id> --reviewer <agent> --verdict pass|block
                 [--finding "severity|file:line|note" ...] [--resolves <n> ...]   record a review (run by the reviewer agent)
  gate.py waiver-template --task <id> --gate <name>                    print the waiver JSON the USER must save by hand
  gate.py status [--task <id>] | verdict [--task <id>]                 show records and the derived verdict

gates.json: {"commands": {"test": "...", "lint": "..."},
             "required": {"T": [], "S": ["test","lint"], "M": ["test","lint","review:reviewer"], "L": ["test","lint","review:reviewer-deep"]},
             "flag_requires": {"security": ["review:reviewer-deep"]},
             "require_review_execution_record": true}
Verdict rules: a required command gate is satisfied only by a `required` run of the exact registered command, at
the CURRENT code revision and the CURRENT gates.json configuration hash; ad-hoc runs never count, whatever their label.
A review is satisfied only by a review record at the current revision whose verdict is pass with no unresolved
blocking findings, and which has been FINALIZED: a hook-recorded SubagentStop of that reviewer agent type, on that
task, ending at or after the record was written, and not already bound to another review. An earlier execution
never validates a later review. Waivers: there is no CLI to create one. The user writes
.claude/efficiency/waivers/<task_id>.json by hand (template from `waiver-template`); the model's Write/Edit/Bash
tools are blocked from that folder by guard.py and by the native deny list. This is tool-path denial, not identity
proof: see the Security section of the playbook for what it does and does not guarantee. Missing or invalid
gates.json fails closed. Logged per run: task, session, gate, kind, scrubbed command, command sha, config hash,
exit code, duration, output sha256, revision. Output text is never stored."""
import sys, os, json, subprocess, pathlib, hashlib, argparse, shlex
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C
import guard

GATES_LOG = lambda: C.logs_dir() / "gates.jsonl"

def tree_revision():
    """DERIVED. Identifies the code under test: git HEAD plus a hash of the working tree diff and untracked files.
    Without git: 'nogit:' plus a hash of mtimes of tracked-looking files (coarse but changes when code changes)."""
    root = C.project_root()
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=20)
        if head.returncode == 0:
            diff = subprocess.run(["git", "diff", "HEAD", "--binary"], cwd=str(root), capture_output=True, timeout=60).stdout
            untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=str(root), capture_output=True, text=True, timeout=60).stdout.split()
            h = hashlib.sha256(diff)
            for u in sorted(untracked):
                try: h.update(u.encode()); h.update(str(os.path.getmtime(root / u)).encode())
                except OSError: pass
            return head.stdout.strip()[:12] + ":" + h.hexdigest()[:12]
    except (OSError, subprocess.SubprocessError): pass
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts and ".claude" not in p.parts:
            try: h.update(str(p.relative_to(root)).encode()); h.update(str(p.stat().st_mtime_ns).encode())
            except OSError: pass
    return "nogit:" + h.hexdigest()[:12]

def resolve_task(task_id):
    if task_id: return task_id, C.find_session_for_task(task_id)
    sid = C.most_recent_session(); st = C.jload(C.session_path(sid), {}) if sid else {}
    return (st.get("task") or {}).get("task_id") or st.get("last_task_id"), sid

def task_info(task_id):
    for p in (C.logs_dir() / "sessions").glob("*.json"):
        st = C.jload(p, {})
        if (st.get("task") or {}).get("task_id") == task_id: return st["task"]
    for t in C.read_jsonl(C.logs_dir() / "tasks.jsonl"):
        if t.get("task_id") == task_id: return t
    return {}

def gates_cfg():
    """Fails closed: an unreadable gates.json is reported as invalid rather than treated as 'no gates'."""
    p = C.eos_dir() / "gates.json"
    try: cfg = json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {"_invalid": "gates.json missing or unparseable"}
    if not isinstance(cfg.get("required"), dict) or not isinstance(cfg.get("commands"), dict): return {"_invalid": "gates.json lacks 'required' or 'commands' objects"}
    return cfg

def config_hash(cfg=None):
    cfg = cfg if cfg is not None else gates_cfg()
    return hashlib.sha256(json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")}, sort_keys=True).encode()).hexdigest()[:12]

def required_for(cls, flags):
    g = gates_cfg(); req = list((g.get("required") or {}).get(cls or "", []))
    for fl in flags or []:
        for extra in (g.get("flag_requires") or {}).get(fl, []):
            if extra not in req: req.append(extra)
    return req

def run_one(task_id, sid, name, cmd, kind="adhoc"):
    blocked, cat = guard.check("Bash", {"command": cmd})
    if blocked: print(f"gate refused: {cat}"); return 126
    t0 = C.ts(); start = C.now()
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(C.project_root()), capture_output=True, text=True, timeout=1800)
        code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired: code, out = 124, "timeout"
    rec = {"t": start, "kind": kind, "task_id": task_id, "session_id": sid, "gate": name or "adhoc", "command": C.scrub(cmd, 200),
           "command_sha": hashlib.sha256(cmd.encode("utf-8", "replace")).hexdigest()[:12], "config_hash": config_hash() if kind == "required" else None,
           "exit_code": code, "duration_s": round(C.ts() - t0, 1), "output_sha256": hashlib.sha256(out.encode("utf-8", "replace")).hexdigest()[:16],
           "result": "pass" if code == 0 else "fail", "revision": tree_revision()}
    C.append_jsonl(GATES_LOG(), rec)
    print("\n".join(out.strip().splitlines()[-15:])); print(f"[gate {rec['gate']} ({kind})] exit {code} -> {rec['result']} (task {task_id}, rev {rec['revision'][:12]})")
    return code

def finalize_reviews(task_id, reviews, subagents=None):
    """Binds hook-recorded reviewer executions to review records. Each execution (in end-time order) vouches for the
    LATEST still-unbound record of its agent type written before it ended: the record the reviewer wrote during that
    run. One execution vouches for one record; a record written after every execution ended stays pending; an
    execution never vouches for a record of a different task. Returns {review index: agent_id or None}."""
    execs = sorted((s for s in (subagents if subagents is not None else C.read_jsonl(C.logs_dir() / "subagents.jsonl")) if s.get("task_id") == task_id and s.get("attribution", "mapped") == "mapped" and s.get("end")), key=lambda s: s["end"])
    bound = {i: None for i in range(len(reviews))}
    for ex in execs:
        cands = [i for i, r in enumerate(reviews) if bound[i] is None and r.get("reviewer") == ex.get("agent_type") and r["t"] <= ex["end"]]
        if cands: bound[max(cands, key=lambda i: reviews[i]["t"])] = ex["agent_id"]
    return bound

def load_waiver(task_id, gate_name):
    """A waiver is a JSON file the user saved by hand at .claude/efficiency/waivers/<task_id>.json:
    {"task_id": ..., "gates": ["review:reviewer-deep"], "reason": "...", "revision": "<from gate.py waiver-template>"}."""
    p = C.eos_dir() / "waivers" / f"{C.safe_name(task_id)}.json"
    w = C.jload(p, None)
    if not isinstance(w, dict) or w.get("task_id") != task_id or gate_name not in (w.get("gates") or []) or not w.get("reason"): return None
    return w

def verdict_for(task_id, cls=None, flags=None, check_stale=True, revision=None, records=None, subagents=None):
    """Returns (verdict, records, reason). verdict: PASS | FAIL | NONE. check_stale=False skips the git revision
    computation (used by the status line, which refreshes often); reports and the verdict command always check.
    Callers scoring many tasks pass revision= (computed once), records= and subagents= (loaded once)."""
    runs = [g for g in (records if records is not None else C.read_jsonl(GATES_LOG())) if g.get("task_id") == task_id]
    cfg = gates_cfg()
    if "_invalid" in cfg: return "FAIL", runs, f"gate configuration invalid: {cfg['_invalid']} (fail closed)"
    if not runs: return "NONE", runs, "no gate records"
    cur = (revision or tree_revision()) if check_stale else None; chash = config_hash(cfg); req = required_for(cls, flags); reasons = []; waived = []
    latest_req, reviews = {}, [g for g in runs if g.get("kind") == "review"]
    for g in runs:
        if g.get("kind") == "required": latest_req[g["gate"]] = g
    bound = finalize_reviews(task_id, reviews, subagents)
    latest_rev = {}
    for i, r in enumerate(reviews): latest_rev[r["reviewer"]] = (i, r)
    def check_cmd(name):
        g = latest_req.get(name)
        if not g: return f"{name}: not run as a required gate (ad-hoc runs do not count)"
        registered = (cfg.get("commands") or {}).get(name)
        if not registered: return f"{name}: no command registered in gates.json (fail closed)"
        if g.get("config_hash") != chash: return f"{name}: gate configuration changed since it ran; rerun"
        if g.get("command_sha") != hashlib.sha256(registered.encode("utf-8", "replace")).hexdigest()[:12]: return f"{name}: recorded command is not the registered one"
        if cur and g.get("revision") != cur: return f"{name}: STALE (ran at {str(g.get('revision'))[:12]}, code is now {cur[:12]})"
        return None if g["exit_code"] == 0 else f"{name}: exit {g['exit_code']}"
    def check_review(reviewer):
        if reviewer not in latest_rev: return f"review:{reviewer}: no review record"
        i, g = latest_rev[reviewer]
        if cur and g.get("revision") != cur: return f"review:{reviewer}: STALE (reviewed {str(g.get('revision'))[:12]}, code is now {cur[:12]})"
        if cfg.get("require_review_execution_record", True) and bound.get(i) is None: return f"review:{reviewer}: PENDING, no hook-recorded '{reviewer}' execution ended after this record on this task (an earlier run does not count)"
        if g.get("verdict") != "pass": return f"review:{reviewer}: verdict {g.get('verdict')}"
        open_block = [f for f in g.get("findings") or [] if f.get("blocking") and not f.get("resolved")]
        return f"review:{reviewer}: {len(open_block)} unresolved blocking finding(s)" if open_block else None
    if not req:
        if not latest_req and not reviews: return "NONE", runs, "no required gates for this class and nothing ran as required"
        bad = [r for r in (check_cmd(n) for n in latest_req) if r] + [r for r in (check_review(n) for n in latest_rev) if r]
        return ("FAIL" if bad else "PASS"), runs, ("; ".join(bad) if bad else "all recorded gates pass at current revision")
    for name in req:
        w = load_waiver(task_id, name)
        if w and (cur is None or w.get("revision") == cur): waived.append(name); continue
        if w: reasons.append(f"{name}: waiver exists but is for revision {str(w.get('revision'))[:12]}, code is now {cur[:12]}"); continue
        r = check_review(name.split(":", 1)[1]) if name.startswith("review:") else check_cmd(name)
        if r: reasons.append(r)
    if reasons: return "FAIL", runs, "; ".join(reasons)
    return "PASS", runs, ("all required gates pass at current revision" + (f" (WAIVED by user file: {', '.join(waived)})" if waived else ""))

def main():
    argv = sys.argv[1:]; cmd = []
    if "--" in argv: i = argv.index("--"); argv, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(); ap.add_argument("action", choices=["run", "required", "review", "waiver-template", "status", "verdict"])
    ap.add_argument("--task"); ap.add_argument("--name"); ap.add_argument("--reviewer"); ap.add_argument("--verdict", choices=["pass", "block"])
    ap.add_argument("--finding", action="append", default=[]); ap.add_argument("--resolves", action="append", default=[])
    ap.add_argument("--gate")
    a, rest = ap.parse_known_args(argv); cmd = cmd or rest
    task_id, sid = resolve_task(a.task)
    if not task_id: print("no task found; pass --task <id> from the [EOS] line"); return 1
    info = task_info(task_id); cls, flags = info.get("class"), info.get("flags") or []
    if a.action == "run":
        if not cmd: print("usage: gate.py run [--task id] [--name label] -- <command>"); return 1
        joined = cmd[0] if len(cmd) == 1 else (subprocess.list2cmdline(cmd) if os.name == "nt" else shlex.join(cmd))
        return run_one(task_id, sid, a.name, joined, kind="adhoc")
    if a.action == "required":
        cfg = gates_cfg()
        if "_invalid" in cfg: print(f"gate configuration invalid: {cfg['_invalid']}"); return 1
        names = [n for n in required_for(cls, flags) if not n.startswith("review:")]; reviews = [n for n in required_for(cls, flags) if n.startswith("review:")]
        if not names and not reviews: print(f"no required gates configured for class {cls}"); return 0
        worst = 0
        for n in names:
            c = (cfg.get("commands") or {}).get(n)
            if not c: print(f"gate {n}: no command registered in gates.json (fail closed)"); worst = max(worst, 1); continue
            worst = max(worst, run_one(task_id, sid, n, c, kind="required"))
        if reviews: print(f"required reviews for this task: {', '.join(reviews)} (the reviewer agent records them with gate.py review)")
        return worst
    if a.action == "review":
        if not a.reviewer or not a.verdict: print("usage: gate.py review --task id --reviewer <agent> --verdict pass|block [--finding 'severity|file:line|note']"); return 1
        findings = []
        for i, f in enumerate(a.finding):
            parts = (f.split("|", 2) + ["", ""])[:3]; sev = parts[0].strip().lower()
            findings.append({"n": i + 1, "severity": sev, "where": C.scrub(parts[1], 80), "note": C.scrub(parts[2], 200), "blocking": sev in ("critical", "high", "blocker", "blocking"), "resolved": False})
        prev = [g for g in C.read_jsonl(GATES_LOG()) if g.get("task_id") == task_id and g.get("kind") == "review" and g.get("reviewer") == a.reviewer]
        if prev and a.resolves:
            for f in prev[-1].get("findings", []):
                if str(f.get("n")) in a.resolves: f["resolved"] = True
            carried = [f for f in prev[-1].get("findings", []) if not f.get("resolved")]
            findings = carried + findings
        rec = {"t": C.now_us(), "kind": "review", "task_id": task_id, "session_id": sid, "reviewer": a.reviewer, "verdict": a.verdict, "findings": findings,
               "revision": tree_revision(), "status": "pending until the reviewer execution is recorded by the SubagentStop hook"}
        C.append_jsonl(GATES_LOG(), rec)
        print(f"[review {a.reviewer}] {a.verdict}, {len(findings)} findings ({sum(1 for f in findings if f['blocking'] and not f['resolved'])} blocking open), rev {rec['revision'][:12]}; finalizes when your own SubagentStop is recorded")
        return 0 if a.verdict == "pass" else 1
    if a.action == "waiver-template":
        if not a.gate: print("usage: gate.py waiver-template --task id --gate <name>"); return 1
        path = C.eos_dir() / "waivers" / f"{C.safe_name(task_id)}.json"
        print(f"Efficiency OS does not create waivers. If YOU (the user) want to skip '{a.gate}' for task {task_id}, save this JSON yourself at\n  {path}\n(the model's Write/Edit/Bash tools are blocked from that folder):")
        print(json.dumps({"task_id": task_id, "gates": [a.gate], "reason": "<why this gate is skipped>", "revision": tree_revision(), "saved_by": "the user, by hand"}, indent=2)); return 0
    v, runs, why = verdict_for(task_id, cls, flags)
    if a.action == "status":
        for g in runs:
            k = g.get("kind", "command")
            if k == "adhoc": print(f"{g['t']}  {g['gate']:<12} exit {g['exit_code']:<3} rev {g.get('revision', '?')[:12]}  (ad-hoc, does not satisfy required gates) {g['command']}")
            elif k == "review": print(f"{g['t']}  review:{g['reviewer']:<10} {g['verdict']:<5} rev {g.get('revision', '?')[:12]}  findings={len(g.get('findings') or [])}")
            elif k == "required": print(f"{g['t']}  {g['gate']:<12} exit {g['exit_code']:<3} rev {g.get('revision', '?')[:12]} cfg {g.get('config_hash')}  (required) {g['command']}")
        for name in required_for(cls, flags):
            w = load_waiver(task_id, name)
            if w: print(f"waiver file: {name} rev {str(w.get('revision'))[:12]}  reason: {C.scrub(str(w.get('reason')), 80)}")
        print(f"required: {required_for(cls, flags)}\nverdict: {v} ({why}) task {task_id} class {cls} flags {flags}")
    else: print(v)
    return 0 if v == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
