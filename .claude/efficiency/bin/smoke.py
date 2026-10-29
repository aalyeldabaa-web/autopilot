#!/usr/bin/env python3
"""Live orchestration smoke test (needs Claude Code; spends a small amount of usage). Usage: smoke.py [--with-builder]
Runs headless sessions and checks the telemetry those sessions produced. Every check is aggregated; the exit code is
nonzero if ANY critical check fails or a required check could not run. Output: one line per check,
`PASS|FAIL|NOT RUN|WARN <name> :: <detail>`, then a final `SUMMARY pass=<n> fail=<n> notrun=<n> warn=<n>` line.
Required checks (verify.py --live demands all of them): headless_run, hooks_fired, lifecycle_hooks, scout_invoked,
scout_usage_measured, scout_actual_model, task_record, result_returned, builder_invoked (when --with-builder)."""
import json, os, subprocess, sys, pathlib, time, shutil, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C

ROWS = []
def out(status, name, detail=""):
    ROWS.append((status, name)); print(f"{status} {name} :: {str(detail)[:160]}", flush=True)

def headless(prompt, max_turns, R):
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--max-turns", str(max_turns), "--permission-mode", "acceptEdits"]
    t0 = time.time()
    try: p = subprocess.run(cmd, cwd=str(R), capture_output=True, text=True, timeout=420, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(R)))
    except subprocess.TimeoutExpired: return None, "timeout after 420s", time.time() - t0
    try: return json.loads(p.stdout), "", time.time() - t0
    except Exception: return None, f"non-JSON output (exit {p.returncode}): {(p.stdout + p.stderr)[-200:]!r}", time.time() - t0

def session_records(sid, logs):
    st = C.jload(C.session_path(sid), {}) if sid else {}
    evs = [e for e in C.read_jsonl(logs / "events.jsonl") if e.get("session_id") == sid]
    subs = [s for s in C.read_jsonl(logs / "subagents.jsonl") if s.get("session_id") == sid]
    tasks = [t for t in C.read_jsonl(logs / "tasks.jsonl") if t.get("session_id") == sid]
    return st, evs, subs, tasks

def main():
    with_builder = "--with-builder" in sys.argv
    if not shutil.which("claude"):
        out("NOT RUN", "headless_run", "claude not on PATH"); print("SUMMARY pass=0 fail=0 notrun=1 warn=0"); return 2
    R = C.project_root(); logs = C.logs_dir()
    res, err, dur = headless("Use the scout subagent to report the exact name of one file in the current directory, then reply with only that file name. Do nothing else.", 8, R)
    if res is None: out("FAIL", "headless_run", err); return finish()
    out("PASS" if res.get("is_error") is not True else "FAIL", "headless_run", f"{dur:.0f}s, turns={res.get('num_turns')}, exit_ok={res.get('is_error') is not True}")
    out("PASS" if isinstance(res.get("result"), str) and res.get("result").strip() else "FAIL", "result_returned", repr(str(res.get("result"))[:60]))
    sid = res.get("session_id"); time.sleep(1.5)
    st, evs, subs, tasks = session_records(sid, logs)
    out("PASS" if st else "FAIL", "hooks_fired", f"session state for {sid}: {'present' if st else 'absent (hook commands did not execute on this OS)'}")
    kinds = {e["event"] for e in evs}
    out("PASS" if {"SessionStart", "UserPromptSubmit", "Stop"} <= kinds else "FAIL", "lifecycle_hooks", f"events: {sorted(kinds)}")
    scouts = [s for s in subs if s.get("agent_type") == "scout"]
    out("PASS" if scouts else "FAIL", "scout_invoked", f"subagents seen: {[s.get('agent_type') for s in subs]}")
    if scouts:
        s = scouts[-1]
        out("PASS" if s.get("kind") == "measured" else "FAIL", "scout_usage_measured", json.dumps(s.get("by_model"))[:120])
        out("PASS" if s.get("model_match") else "FAIL", "scout_actual_model", f"intended={s.get('intended_model')} actual={s.get('models')} effort={s.get('efforts')} attribution={s.get('attribution')}")
    else:
        out("FAIL", "scout_usage_measured", "no scout record"); out("FAIL", "scout_actual_model", "no scout record")
    out("PASS" if tasks and tasks[-1].get("usage_kind") in ("measured", "partial") else "FAIL", "task_record", json.dumps((tasks[-1] if tasks else {}).get("totals"))[:100])
    out("PASS" if (res.get("modelUsage") or res.get("model_usage")) else "WARN", "claude_p_model_usage", "present" if (res.get("modelUsage") or res.get("model_usage")) else "field absent in this version (benchmark per-model column will be empty)")
    if with_builder:
        marker = f"eos_smoke_{int(time.time())}.txt"
        res2, err2, dur2 = headless(f"Use the builder subagent to create an empty file named {marker} in the current directory, then reply with only the word done.", 10, R)
        if res2 is None: out("FAIL", "builder_invoked", err2)
        else:
            sid2 = res2.get("session_id"); time.sleep(1.5); st2, evs2, subs2, tasks2 = session_records(sid2, logs)
            b = [s for s in subs2 if s.get("agent_type") == "builder"]
            out("PASS" if b and (R / marker).exists() else "FAIL", "builder_invoked", f"builder records={len(b)} file_created={(R / marker).exists()} actual={b[-1].get('models') if b else None}")
            out("PASS" if b and b[-1].get("task_id") == (tasks2[-1].get("task_id") if tasks2 else None) else "FAIL", "builder_attributed_to_task", f"agent task={b[-1].get('task_id') if b else None} task={tasks2[-1].get('task_id') if tasks2 else None}")
            try: (R / marker).unlink()
            except OSError: pass
    return finish()

def finish():
    n = {k: sum(1 for s, _ in ROWS if s == k) for k in ("PASS", "FAIL", "NOT RUN", "WARN")}
    print(f"SUMMARY pass={n['PASS']} fail={n['FAIL']} notrun={n['NOT RUN']} warn={n['WARN']}")
    return 1 if n["FAIL"] or n["NOT RUN"] else 0

if __name__ == "__main__":
    sys.exit(main())
