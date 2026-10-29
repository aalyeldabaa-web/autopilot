#!/usr/bin/env python3
"""Benchmark runner. Usage: run.py --config v1|v2 --task <name>|all [--runs 3]
Each run: fresh detached git worktree from HEAD -> config applied -> headless claude -p -> acceptance command -> record.
Worktrees are always removed (finally block) and pruned. Results carry a spec_hash so compare.py only pairs runs
that used identical prompt, setup and acceptance criteria. Set EOS_CLAUDE_CMD to substitute the claude binary (tests)."""
import argparse, json, os, pathlib, shutil, subprocess, tempfile, time, datetime, hashlib, sys, shlex, re
EOS = pathlib.Path(__file__).resolve().parents[1]; ROOT = EOS.parents[1]
RESULTS = EOS / "bench" / "results.jsonl"
CLAUDE_VERSION_HOLDER = ["unknown"]

def sh(cmd, cwd, env=None, timeout=None):
    return subprocess.run(cmd, cwd=str(cwd), shell=isinstance(cmd, str), capture_output=True, text=True, env=env, timeout=timeout)

def copy_config(src_dir, dst, py):
    """Copies the config into the worktree and rewrites every Efficiency OS hook command to point INSIDE the worktree,
    so an install with absolute hook paths never writes telemetry into (or reads config from) the original project."""
    if (src_dir / ".claude").is_dir():
        shutil.copytree(src_dir / ".claude", dst / ".claude", dirs_exist_ok=True, ignore=shutil.ignore_patterns("logs", "results.jsonl", "*.lock", "sessions", "waivers"))
    if (src_dir / "CLAUDE.md").exists(): shutil.copy2(src_dir / "CLAUDE.md", dst / "CLAUDE.md")
    settings = dst / ".claude" / "settings.json"
    if settings.exists() and (dst / ".claude" / "efficiency" / "bin" / "install.py").exists():
        sys.path.insert(0, str(dst / ".claude" / "efficiency" / "bin"))
        try:
            import importlib, install; importlib.reload(install)
            style = "absolute" if "$CLAUDE_PROJECT_DIR" not in settings.read_text(encoding="utf-8") else "env"
            settings.write_text(install.rewrite_hooks(settings.read_text(encoding="utf-8"), py, dst, style), encoding="utf-8")
        except Exception as e: print("warning: could not rewrite hook paths in worktree:", str(e)[:80])

PLACEHOLDER = re.compile(r"^\s*<.*>\s*$")
def validate_spec(name, spec):
    """Rejects metadata keys, placeholders and incomplete definitions before anything runs."""
    if name.startswith("_") or not isinstance(spec, dict): return f"{name}: not a task specification"
    for k in ("prompt", "acceptance"):
        v = spec.get(k)
        if not isinstance(v, str) or not v.strip() or PLACEHOLDER.match(v): return f"{name}: '{k}' is missing or still a placeholder"
    if not isinstance(spec.get("max_turns", 40), int) or spec.get("max_turns", 40) < 1: return f"{name}: max_turns must be a positive integer"
    if not isinstance(spec.get("allowed_tools", []), list): return f"{name}: allowed_tools must be a list"
    return None

def one_run(cfg, name, spec, i):
    spec_hash = hashlib.sha256(json.dumps({k: spec.get(k) for k in ("prompt", "setup", "acceptance", "max_turns")}, sort_keys=True).encode()).hexdigest()[:12]
    wt = pathlib.Path(tempfile.mkdtemp(prefix=f"eos-bench-{cfg}-{name}-"))
    rec = {"t": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "config": cfg, "task": name, "run": i + 1, "spec_hash": spec_hash, "valid": False}
    try:
        r = sh(["git", "worktree", "add", "--detach", str(wt), "HEAD"], ROOT)
        if r.returncode != 0: rec["error"] = "worktree add failed: " + r.stderr[-200:]; return rec
        env = dict(os.environ)
        for p in (".claude", "CLAUDE.md"):
            t = wt / p
            if t.is_dir(): shutil.rmtree(t)
            elif t.exists(): t.unlink()
        py = os.environ.get("EOS_PY") or (json.loads((EOS / "manifest.json").read_text(encoding="utf-8")).get("py", "python3") if (EOS / "manifest.json").exists() else "python3")
        if cfg == "v1":
            copy_config(EOS / "baseline-config", wt, py); env["EOS_DISABLED"] = "1"
        else:
            copy_config(ROOT, wt, py)
        env["CLAUDE_PROJECT_DIR"] = str(wt)
        if spec.get("setup"):
            s = sh(spec["setup"], wt, env=env)
            if s.returncode != 0: rec["error"] = "setup failed: " + s.stderr[-200:]; return rec
        claude = shlex.split(os.environ.get("EOS_CLAUDE_CMD", "claude"))
        cmd = [*claude, "-p", spec["prompt"], "--output-format", "json", "--permission-mode", "acceptEdits", "--max-turns", str(spec.get("max_turns", 40))]
        for t in spec.get("allowed_tools", []): cmd += ["--allowedTools", t]
        t0 = time.time()
        try: r = sh(cmd, wt, env=env, timeout=spec.get("timeout_s", 1800)); rec["timed_out"] = False
        except subprocess.TimeoutExpired: r = None; rec["timed_out"] = True
        rec["duration_s"] = round(time.time() - t0, 1)
        try: out = json.loads(r.stdout) if r else {}
        except Exception: out = {"parse_error": True}
        rec.update({"is_error": out.get("is_error"), "num_turns": out.get("num_turns"), "usage": out.get("usage"), "retries": "unavailable (claude -p does not report retries; see num_turns)",
                    "claude_version": CLAUDE_VERSION_HOLDER[0], "worktree_clean_after": None,
                    "model_usage": out.get("modelUsage") or out.get("model_usage"), "total_cost_usd_estimate": out.get("total_cost_usd"), "parse_error": out.get("parse_error", False)})
        if spec.get("acceptance"):
            acc = sh(spec["acceptance"], wt, env=env); rec["acceptance_exit"] = acc.returncode; rec["acceptance_pass"] = acc.returncode == 0
        rec["valid"] = (not rec["timed_out"]) and not rec["parse_error"] and out.get("is_error") is not True
        return rec
    finally:
        leaked = (wt / ".claude" / "efficiency" / "logs").exists()
        rec["telemetry_written_inside_worktree"] = leaked
        sh(["git", "worktree", "remove", "--force", str(wt)], ROOT)
        shutil.rmtree(wt, ignore_errors=True)
        sh(["git", "worktree", "prune"], ROOT)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True, choices=["v1", "v2"]); ap.add_argument("--task", required=True); ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    specs = json.loads((EOS / "bench" / "tasks.json").read_text(encoding="utf-8"))
    tasks = {k: v for k, v in specs.items() if not k.startswith("_")}
    names = list(tasks) if a.task == "all" else [a.task]
    unknown = [n for n in names if n not in tasks]
    if unknown: print(f"unknown task(s): {unknown}; available: {list(tasks)}"); return 2
    bad = [validate_spec(n, tasks[n]) for n in names]; bad = [b for b in bad if b]
    if bad: print("benchmark definitions rejected:\n" + "\n".join(" - " + b for b in bad)); return 2
    claude = shlex.split(os.environ.get("EOS_CLAUDE_CMD", "claude"))
    try: v = subprocess.run(claude + ["--version"], capture_output=True, text=True, timeout=60); CLAUDE_VERSION_HOLDER[0] = v.stdout.strip()[:40] or "unknown"
    except Exception: CLAUDE_VERSION_HOLDER[0] = "unknown"
    tree = lambda: "\n".join(l for l in sh(["git", "status", "--porcelain"], ROOT).stdout.splitlines() if ".claude/efficiency/" not in l)
    before = tree()
    if sh(["git", "rev-parse", "--is-inside-work-tree"], ROOT).returncode != 0: print("not a git repository; benchmarks need git worktrees"); return 2
    for name in names:
        for i in range(a.runs):
            rec = one_run(a.config, name, tasks[name], i)
            with open(RESULTS, "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
            print(json.dumps({k: rec.get(k) for k in ("config", "task", "run", "duration_s", "acceptance_pass", "valid", "error")}))
    after = tree()
    if after != before: print("WARNING: the main working tree changed during the benchmark; inspect git status"); return 3
    return 0

if __name__ == "__main__":
    sys.exit(main())
