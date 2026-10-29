#!/usr/bin/env python3
"""Installation verification. Usage: verify.py [--live] [--with-builder]
Deterministic section (always): manifest hashes, settings.json structure (hooks, native deny list, matcher coverage),
each registered hook command EXECUTED with a sample payload through the shell (not just parsed), scripts, agents,
skills, gates.json, kernel, the full unit suite (tests/test_all.py), measured hook overhead.
Live section (--live; needs an installed Claude Code and spends a little usage): claude --version, agent validation,
smoke.py. The smoke process exit code AND its per-check lines are both inspected; nonzero exit, malformed output,
timeout, or a missing required check is a FAIL. Importable: ingest_smoke(returncode, stdout, timed_out, with_builder).
Exit codes match the verdict: 0 RELEASE READY (zero FAIL, zero NOT RUN, builder live check included), 2 RELEASE CANDIDATE
(zero FAIL but something NOT RUN), 1 NOT READY (any FAIL). Synthetic stubs never count as live execution: the live
rows come only from the --live run of smoke.py against the real `claude` binary."""
import json, os, sys, subprocess, pathlib, hashlib, re, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C
R = C.project_root(); EOS = C.eos_dir(); B = EOS / "bin"; PY = sys.executable
rows = []
def check(name, ok, detail="", critical=True): rows.append((name, ("PASS" if ok else ("FAIL" if critical else "warn")), detail))
def notrun(name, why): rows.append((name, "NOT RUN", why))

REQUIRED_SMOKE = ("headless_run", "result_returned", "hooks_fired", "lifecycle_hooks", "scout_invoked", "scout_usage_measured", "scout_actual_model", "task_record")
REQUIRED_BUILDER = ("builder_invoked", "builder_attributed_to_task")

def ingest_smoke(returncode, stdout, timed_out=False, with_builder=False):
    """Turns smoke.py output into verification rows. Any required check that is FAIL, NOT RUN or absent is a FAIL;
    a nonzero exit without a SUMMARY line, a timeout, or unparseable output is a FAIL on every required check."""
    out = []; seen = {}
    for line in (stdout or "").splitlines():
        m = re.match(r"(PASS|FAIL|NOT RUN|WARN)\s+(\S+)(?:\s+::\s+(.*))?$", line.strip())
        if m: seen[m.group(2)] = (m.group(1), (m.group(3) or "")[:110])
    summary = re.search(r"^SUMMARY pass=(\d+) fail=(\d+) notrun=(\d+) warn=(\d+)", stdout or "", re.M)
    required = REQUIRED_SMOKE + (REQUIRED_BUILDER if with_builder else ())
    if timed_out: return [(f"live: {n}", "FAIL", "smoke test timed out") for n in required]
    if not summary: return [(f"live: {n}", "FAIL", f"smoke output malformed or process died (exit {returncode}): {(stdout or '')[-80:]!r}") for n in required]
    for n in required:
        st, d = seen.get(n, ("FAIL", "check missing from smoke output"))
        out.append((f"live: {n}", "FAIL" if st in ("FAIL", "NOT RUN") else st, d))
    for n, (st, d) in seen.items():
        if n not in required: out.append((f"live: {n}", "warn" if st in ("WARN", "FAIL", "NOT RUN") else st, d))
    if returncode != 0 and all(st == "PASS" for _, st, _ in out if _.replace("live: ", "") in required):
        out.append(("live: smoke exit code", "FAIL", f"process exited {returncode} although required checks read PASS; treating as failure"))
    return out

def run_hook_commands(settings):
    """Executes every Efficiency OS hook command exactly as Claude Code would (through the shell) with a sample payload."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(R), EOS_TEST="1")
    samples = {"SessionStart": {"session_id": "vfy", "transcript_path": "/nonexistent", "source": "startup"},
               "UserPromptSubmit": {"session_id": "vfy", "prompt": "verify hooks"}, "SubagentStart": {"session_id": "vfy", "agent_id": "v1", "agent_type": "scout"},
               "SubagentStop": {"session_id": "vfy", "agent_id": "v1", "agent_type": "scout", "agent_transcript_path": "/nonexistent"},
               "Stop": {"session_id": "vfy"}, "SessionEnd": {"session_id": "vfy", "reason": "exit"}, "PreCompact": {"session_id": "vfy"},
               "PreToolUse": {"session_id": "vfy", "tool_name": "Bash", "tool_input": {"command": "git status"}}, "PreModelSwitch": {"session_id": "vfy", "to_model": "sonnet"}}
    for ev, entries in (settings.get("hooks") or {}).items():
        for e in entries:
            for h in e.get("hooks", []):
                cmd = h.get("command", "")
                if "efficiency" not in cmd: continue
                try:
                    p = subprocess.run(cmd, shell=True, input=json.dumps(samples.get(ev, {"session_id": "vfy"})), capture_output=True, text=True, env=env, cwd=str(R), timeout=30)
                    ok = p.returncode == 0 and ("hookSpecificOutput" in p.stdout if ev == "UserPromptSubmit" else True)
                    check(f"hook command executes: {ev}", ok, (p.stderr or p.stdout).strip()[-100:] or f"exit {p.returncode}")
                except subprocess.TimeoutExpired: check(f"hook command executes: {ev}", False, "timeout")
    sl = (settings.get("statusLine") or {}).get("command")
    if sl:
        try:
            p = subprocess.run(sl, shell=True, input=json.dumps({"session_id": "vfy", "model": {"display_name": "Opus"}, "context_window": {"used_percentage": 12}}), capture_output=True, text=True, env=env, cwd=str(R), timeout=30)
            check("status line command executes", p.returncode == 0 and "ctx 12%" in p.stdout, p.stdout.strip()[:80] or p.stderr[-80:])
        except subprocess.TimeoutExpired: check("status line command executes", False, "timeout")
    shutil.rmtree(EOS / "logs" / "test", ignore_errors=True)

def main():
    live = "--live" in sys.argv; with_builder = "--with-builder" in sys.argv
    man = C.jload(EOS / "manifest.json", {})
    for f, h in (man.get("files") or {}).items():
        p = R / f; check(f"manifest {f}", p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == h, "missing or modified since install", critical=False)
    check("manifest version 2.1.2", man.get("version") == "2.1.2", str(man.get("version")))
    s = C.jload(R / ".claude" / "settings.json", None)
    if s is None: check("settings.json parses", False)
    else:
        hooks = s.get("hooks", {})
        for ev in ("SessionStart", "UserPromptSubmit", "SubagentStart", "SubagentStop", "Stop", "SessionEnd", "PreToolUse"):
            check(f"hook registered {ev}", ev in hooks and any("efficiency" in json.dumps(x) for x in hooks[ev]))
        check("hook PreModelSwitch", "PreModelSwitch" in hooks, "policy only if the event is unavailable in this version", critical=False)
        check("PreToolUse matcher covers Bash, PowerShell and file writes", any(all(k in json.dumps(x.get("matcher", "")) for k in ("Bash", "PowerShell", "Write", "Read")) for x in hooks.get("PreToolUse", [])))
        deny = json.dumps((s.get("permissions") or {}).get("deny", []))
        for pat in ("rm -rf", "--force", "sudo", ".env", "publish", "dangerously-skip-permissions"):
            check(f"native deny covers {pat}", pat in deny, "layer 2 of the guard is missing this pattern")
        allow = json.dumps((s.get("permissions") or {}).get("allow", []))
        check("allowlist contains no destructive pattern", not re.search(r"rm -rf|--force|sudo|publish|deploy", allow))
        check("statusLine configured", "statusLine" in s, critical=False)
        eos_cmds = [h.get("command", "") for ev in hooks.values() for e in ev for h in e.get("hooks", []) if "efficiency" in h.get("command", "")]
        style = "env" if any("$CLAUDE_PROJECT_DIR" in c for c in eos_cmds) else "absolute"
        check("hook path style matches OS", (os.name != "nt") or style == "absolute", f"style={style}; Windows requires absolute paths (POSIX $VAR expansion is not available in cmd/PowerShell)")
        run_hook_commands(s)
    for name in ("common", "telemetry", "classify", "guard", "model_guard", "gate", "statusline", "report", "calibrate", "smoke", "install"):
        p = subprocess.run([PY, "-c", f"import ast;ast.parse(open(r'{B / (name + '.py')}',encoding='utf-8').read())"], capture_output=True, text=True); check(f"syntax {name}.py", p.returncode == 0, p.stderr[-200:])
    check("legacy mark.py removed (self-reported gates)", not (B / "mark.py").exists())
    pr = C.jload(EOS / "pricing.json", {})
    try:
        import telemetry as T
        priced = [k for k in pr if not k.startswith("_") and T.valid_price(pr[k])]
        check("pricing.json has valid prices", bool(priced), f"priced families: {priced or 'none (cost will read unavailable until filled)'}", critical=False)
        check("pricing placeholders are null, not zero", all(not (isinstance(v, dict) and any(x == 0 for x in v.values())) for k, v in pr.items() if not k.startswith("_")), "a zero price would be treated as unknown anyway, but fix the file")
    except Exception as e: check("pricing validation", False, str(e)[:100])
    g = C.jload(EOS / "gates.json", {})
    check("gates.json requires reviews for M/L and security", "review:reviewer" in json.dumps(g.get("required", {}).get("M", [])) and "review:reviewer-deep" in json.dumps(g.get("required", {}).get("L", [])) and "review:reviewer-deep" in json.dumps((g.get("flag_requires") or {}).get("security", [])))
    for a in ("scout", "builder", "builder-isolated", "reviewer", "reviewer-deep", "architect"):
        f = R / ".claude" / "agents" / f"{a}.md"; txt = f.read_text(encoding="utf-8") if f.exists() else ""
        check(f"agent {a}", bool(f.exists() and re.search(r"^name:\s*" + a, txt, re.M) and "description:" in txt and "model:" in txt))
        if a.startswith("reviewer"): check(f"agent {a} records its review via gate.py", "gate.py review" in txt)
    check("heavy agent inactive unless enabled", not (R / ".claude" / "agents" / "heavy.md").exists() or ((EOS / "paid-models.ok").exists() and C.config().get("paid_models_allowed") is True), critical=False)
    for sk in ("route", "gate", "handoff", "codify", "efficiency-report", "cost-check", "lean-check", "benchmark", "calibrate", "enable-heavy"):
        check(f"skill {sk}", (R / ".claude" / "skills" / sk / "SKILL.md").exists() or (R / ".claude" / "commands" / f"{sk}.md").exists(), critical=False)
    check("ROUTING.md", (EOS / "ROUTING.md").exists())
    cm = (R / "CLAUDE.md").read_text(encoding="utf-8") if (R / "CLAUDE.md").exists() else ""
    check("kernel in CLAUDE.md", "Efficiency OS kernel" in cm and "gate.py" in cm and "mark.py" not in cm)
    check("CLAUDE.md lean (<=120 lines)", len(cm.splitlines()) <= 120, f"{len(cm.splitlines())} lines", critical=False)
    gi = (R / ".gitignore").read_text(encoding="utf-8") if (R / ".gitignore").exists() else ""
    check(".gitignore protects logs", ".claude/efficiency/logs/" in gi, critical=False)
    if os.environ.get("EOS_SKIP_UNIT") == "1": rows.append(("unit suite", "INFO", "skipped: verify.py is itself running inside the unit suite"))
    else:
      try:
        t = subprocess.run([PY, "-I", str(EOS / "tests" / "test_all.py")], capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(R)), timeout=900)
        m = re.search(r"Ran (\d+) tests", t.stderr); okm = re.search(r"^OK", t.stderr, re.M)
        check(f"unit suite ({m.group(1) if m else '?'} tests)", bool(okm), (t.stderr.strip().splitlines()[-1] if t.stderr.strip() else "no output")[:120])
        for line in t.stdout.splitlines():
            if "hook overhead" in line: check("hook overhead measured", True, line.split(":", 1)[1].strip()[:110], critical=False)
      except subprocess.TimeoutExpired: check("unit suite", False, "timed out after 900s (a test stalled; run tests/test_all.py -v to find it)")
    if live:
        if not shutil.which("claude"): check("claude on PATH (--live)", False, "install Claude Code first")
        else:
            p = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=60); check("claude --version", p.returncode == 0, p.stdout.strip()[:40])
            p = subprocess.run(["claude", "plugin", "validate", str(R / ".claude" / "agents")], capture_output=True, text=True, timeout=120); check("claude plugin validate agents", p.returncode == 0, (p.stdout + p.stderr).strip()[-120:], critical=False)
            smoke_cmd = os.environ.get("EOS_SMOKE_CMD")   # test hook: substitute the smoke process (marks the run as synthetic)
            if smoke_cmd: rows.append(("live: synthetic smoke substitute in use", "INFO", "EOS_SMOKE_CMD is set; these live rows are NOT evidence of Claude Code execution"))
            cmd = (smoke_cmd.split() if smoke_cmd else [PY, str(B / "smoke.py")]) + (["--with-builder"] if with_builder else [])
            try: sp = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(R)), timeout=1200); rows.extend(ingest_smoke(sp.returncode, sp.stdout, False, with_builder))
            except subprocess.TimeoutExpired: rows.extend(ingest_smoke(1, "", True, with_builder))
            if not with_builder:
                for n in REQUIRED_BUILDER: notrun(f"live: {n}", "RELEASE READY requires verify.py --live --with-builder")
    else:
        for n in ("claude --version", "claude plugin validate agents") + tuple(f"live: {x}" for x in REQUIRED_SMOKE + REQUIRED_BUILDER):
            notrun(n, "needs a live Claude Code session: run verify.py --live --with-builder")
        if os.name != "nt": rows.append(("Windows hook execution (cmd/PowerShell)", "INFO", "not this platform; it is verified by running verify.py on the Windows machine"))
    print("| check | result | detail |\n|---|---|---|")
    for n, r, d in rows: print(f"| {n} | {r} | {str(d).replace('|', '/')[:110]} |")
    crit = [x for x in rows if x[1] == "FAIL"]; nr = [x for x in rows if x[1] == "NOT RUN"]
    print(f"\n{sum(1 for x in rows if x[1] == 'PASS')} PASS, {sum(1 for x in rows if x[1] == 'warn')} warn, {len(crit)} FAIL, {len(nr)} NOT RUN")
    synthetic = any(x[0].startswith("live: synthetic") for x in rows)
    if not crit and not nr and synthetic: nr = [("synthetic", "NOT RUN", "")]
    print("verdict:", "NOT READY: critical checks failed" if crit else ("RELEASE CANDIDATE: deterministic checks pass; live or platform checks NOT RUN" + (" (synthetic smoke substitute detected)" if synthetic else "") if nr else "RELEASE READY: all required deterministic and live checks passed (scout and builder orchestration verified against the real claude binary)"))
    return 1 if crit else (2 if nr else 0)

if __name__ == "__main__":
    sys.exit(main())
