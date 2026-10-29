#!/usr/bin/env python3
"""Efficiency OS v2.1 installer. Reads the playbook Markdown, extracts every fenced block tagged `path=<file>`,
and installs them into the current project. Idempotent, diff-aware, never overwrites user content.

  install.py --from claude-code-efficiency-playbook.md [--dry-run] [--py python3] [--test-cmd "pytest -q"] [--lint-cmd "ruff check ."]
             [--update-runtime]   (refresh runtime files that an older Efficiency OS install wrote, by manifest hash)

Rules: new file -> create. Existing file whose hash matches the manifest -> skip. Existing file not in the manifest
(user-owned) -> skip and report. Existing runtime file with an older manifest hash -> update only with --update-runtime.
Merged files: .claude/settings.json (hooks appended if absent, permissions unioned, statusLine set only if absent),
CLAUDE.md (kernel block inserted or replaced between markers), .gitignore (lines appended). --dry-run prints the plan
and unified diffs and writes nothing except .claude/efficiency/install-plan.md."""
import argparse, json, re, pathlib, hashlib, difflib, sys, os, datetime, subprocess

START, END = "<!-- eos-kernel-start -->", "<!-- eos-kernel-end -->"
ENV_FORM = '"$CLAUDE_PROJECT_DIR/.claude/efficiency/bin/'

def hook_style_for(os_name=None):
    """Windows shells (cmd, PowerShell) do not expand $VAR; absolute paths work in every shell."""
    return "absolute" if (os_name or os.name) == "nt" else "env"

def quote_path(path, os_name=None):
    """Double quotes are the one quoting form cmd, PowerShell and POSIX shells all accept for paths with spaces or
    non-ASCII characters. Embedded double quotes cannot be represented portably and are rejected."""
    p = str(path)
    if '"' in p: raise ValueError("project path contains a double quote; move the project or pass --hook-style env on POSIX")
    return '"' + p + '"'

def hook_command(py, root, script, style, os_name=None):
    """Generates one hook command line. style=env keeps $CLAUDE_PROJECT_DIR (POSIX); style=absolute bakes the project path."""
    if style == "env": return f'{py} {ENV_FORM}{script}"'
    P = pathlib.PureWindowsPath if (os_name or os.name) == "nt" else pathlib.PurePosixPath
    return f"{py} {quote_path(P(str(root)) / '.claude' / 'efficiency' / 'bin' / script, os_name)}"

def rewrite_hooks(settings_text, py, root, style, os_name=None):
    """Rewrites every Efficiency OS hook and statusLine command in the settings payload for the chosen style.
    Works on the parsed JSON, so quoting inside the file never matters."""
    data = json.loads(settings_text); rx = re.compile(r"/\.claude/efficiency/bin/([\w.-]+\.py)\"?(.*)$")
    def fix(cmd):
        m = rx.search(cmd)
        if not m or "efficiency" not in cmd: return cmd
        return hook_command(py, root, m.group(1), style, os_name) + m.group(2)
    for ev in data.get("hooks", {}).values():
        for e in ev:
            for h in e.get("hooks", []): h["command"] = fix(h.get("command", ""))
    if "statusLine" in data: data["statusLine"]["command"] = fix(data["statusLine"]["command"])
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

def verify_launcher(py):
    try:
        p = subprocess.run(py.split() + ["-c", "import sys;print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True, timeout=30)
        ver = tuple(int(x) for x in p.stdout.strip().split(".")) if p.returncode == 0 else None
        return (ver is not None and ver >= (3, 8)), (p.stdout.strip() or p.stderr.strip()[-80:])
    except Exception as e: return False, str(e)[:80]

def sha(b): return hashlib.sha256(b).hexdigest()

def extract(md):
    out = {}
    for m in re.finditer(r"```[\w+-]*\s+path=(\S+)\n(.*?)\n```", md, re.S):
        out[m.group(1)] = m.group(2) + "\n"
    return out

PH = lambda n: "{{" + n + "}}"   # built at runtime so this file's own text carries no placeholder
def fill(text, a):
    """Text placeholders only. Structured values (gate commands, allow patterns) go through fill_json below."""
    return text.replace(PH("PY"), a.py)

def fill_json(rel, text, a):
    """Sets structured values on parsed JSON so quotes, backslashes and shell syntax are serialized correctly."""
    data = json.loads(text)
    if rel.endswith("gates.json"):
        cmds = data.setdefault("commands", {})
        cmds["test"] = a.test_cmd or ""; cmds["lint"] = a.lint_cmd or ""
        for k in [k for k, v in cmds.items() if not v]: del cmds[k]              # unregistered gates are absent, never ""
    if rel.endswith("settings.json"):
        perms = data.setdefault("permissions", {}); allow = perms.setdefault("allow", [])
        for pat in a.allow or []:
            if pat not in allow: allow.append(pat)
        if a.format_cmd:
            data.setdefault("hooks", {}).setdefault("PostToolUse", []).append({"matcher": "Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": f'{a.py} {ENV_FORM}format_hook.py"', "timeout": 60}]})
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
def validate_payload(files, root):
    """Every generated JSON parses; every agent and skill has closed frontmatter with name and description;
    Python files compile. Returns a list of problems (empty means valid)."""
    import ast
    problems = []
    for rel, body in files.items():
        if rel.endswith(".json"):
            try: json.loads(body)
            except Exception as e: problems.append(f"{rel}: invalid JSON ({str(e)[:60]})")
        elif rel.endswith(".py"):
            try: ast.parse(body)
            except SyntaxError as e: problems.append(f"{rel}: syntax error line {e.lineno}")
        elif rel.startswith((".claude/agents/", ".claude/skills/")) or "agents-disabled" in rel:
            m = FRONTMATTER.match(body)
            if not m: problems.append(f"{rel}: frontmatter not closed"); continue
            fm = m.group(1)
            if not re.search(r"^name:\s*\S", fm, re.M) or not re.search(r"^description:\s*\S", fm, re.M): problems.append(f"{rel}: frontmatter needs name and description")
            if rel.startswith(".claude/agents/") and not re.search(r"^model:\s*(haiku|sonnet|opus|fable|inherit|claude-)", fm, re.M): problems.append(f"{rel}: agent model must be haiku/sonnet/opus/fable/inherit or a full id")
    return problems

def merge_settings(existing, new):
    """User hooks and keys are kept; Efficiency OS hook entries (those calling /efficiency/bin/) are replaced by the
    new ones so an upgrade can change their command form; permissions are unioned; statusLine set only if absent."""
    cur = json.loads(existing) if existing.strip() else {}
    add = json.loads(new)
    cur.setdefault("hooks", {})
    is_eos = lambda e: "efficiency" in json.dumps(e) and "bin" in json.dumps(e)
    for ev, entries in add.get("hooks", {}).items():
        kept = [e for e in cur["hooks"].get(ev, []) if not is_eos(e)]
        cur["hooks"][ev] = kept + [e for e in entries if is_eos(e) or json.dumps(e) not in json.dumps(kept)]
    perms = cur.setdefault("permissions", {})
    for k in ("allow", "deny"):
        perms.setdefault(k, [])
        for p in add.get("permissions", {}).get(k, []):
            if p not in perms[k]: perms[k].append(p)
    if "statusLine" not in cur and "statusLine" in add: cur["statusLine"] = add["statusLine"]
    elif "statusLine" in cur and "efficiency" in json.dumps(cur["statusLine"]) and "statusLine" in add: cur["statusLine"] = add["statusLine"]
    return json.dumps(cur, indent=2, ensure_ascii=False) + "\n"

def merge_claude_md(existing, kernel):
    block = f"{START}\n{kernel.rstrip()}\n{END}\n"
    if START in existing and END in existing:
        return re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", block, existing, flags=re.S)
    return block + "\n" + existing if existing.strip() else block

def merge_gitignore(existing, lines):
    have = set(existing.splitlines()); add = [l for l in lines.splitlines() if l.strip() and l not in have]
    if not add: return existing
    return existing.rstrip("\n") + ("\n" if existing else "") + "\n".join(add) + "\n"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--from", dest="src", required=True); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--py", default="python3"); ap.add_argument("--test-cmd", default=""); ap.add_argument("--lint-cmd", default=""); ap.add_argument("--update-runtime", action="store_true")
    ap.add_argument("--hook-style", choices=["auto", "env", "absolute"], default="auto"); ap.add_argument("--skip-validation", action="store_true", help="only for environments where hooks cannot execute during install (recorded in the report)")
    ap.add_argument("--allow", action="append", default=[], help="extra permissions.allow pattern, e.g. 'Bash(pytest*)' (repeatable)"); ap.add_argument("--format-cmd", default="", help="formatter run after edits, with {file} as the placeholder, e.g. 'prettier --write {file}'")
    a = ap.parse_args()
    root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve(); eos = root / ".claude" / "efficiency"
    ok, ver = verify_launcher(a.py)
    if not ok: print(f"launcher check failed for '{a.py}': {ver}. Pass --py with a working Python 3.8+ launcher."); return 2
    style = hook_style_for() if a.hook_style == "auto" else a.hook_style
    files = extract(pathlib.Path(a.src).read_text(encoding="utf-8"))
    if not files: print("no `path=` blocks found in", a.src); return 2
    manifest = {}
    try: manifest = json.loads((eos / "manifest.json").read_text(encoding="utf-8")).get("files", {})
    except Exception: pass
    guard_rx = re.compile(r"rm -rf|--force|sudo|publish|deploy|dangerously", re.I)
    bad_allow = [x for x in a.allow if guard_rx.search(x)]
    if bad_allow: print(f"refusing to allowlist patterns the guard blocks: {bad_allow}"); return 2
    plan, new_manifest, diffs, finals = [], {}, [], {}
    for rel, body in sorted(files.items()):
        body = fill(body, a)
        if rel.endswith(".json"): body = fill_json(rel, body, a)
        if rel == ".claude/settings.json": body = rewrite_hooks(body, a.py, root, style)
        if rel.endswith("format_hook.py"): body = body.replace(PH("FORMAT_CMD"), json.dumps(a.format_cmd))
        dest = root / rel; action = "create"; final = body
        if rel == ".claude/settings.json" and dest.exists(): final = merge_settings(dest.read_text(encoding="utf-8"), body); action = "merge"
        elif rel == "CLAUDE.md": final = merge_claude_md(dest.read_text(encoding="utf-8") if dest.exists() else "", body); action = "merge" if dest.exists() else "create"
        elif rel == ".gitignore": final = merge_gitignore(dest.read_text(encoding="utf-8") if dest.exists() else "", body); action = "merge" if dest.exists() else "create"
        elif dest.exists():
            cur = dest.read_bytes(); h = sha(cur)
            if h == sha(final.encode("utf-8")): action = "skip (identical)"
            elif rel in manifest and manifest[rel] == h: action = "update (runtime, by manifest)" if (a.update_runtime or "/bin/" in rel or "/bench/" in rel or "/tests/" in rel) else "skip (runtime changed upstream; pass --update-runtime)"
            elif rel in manifest and manifest[rel] != h: action = "skip (modified locally since install; keeping yours)"
            else: action = "skip (exists, not installed by Efficiency OS; keeping yours)"
        if action.startswith("skip"): final = dest.read_text(encoding="utf-8") if dest.exists() else final
        if action in ("merge",) or action.startswith("update"):
            old = dest.read_text(encoding="utf-8").splitlines(keepends=True) if dest.exists() else []
            diffs.append(f"### {rel} ({action})\n```diff\n" + "".join(difflib.unified_diff(old, final.splitlines(keepends=True), "current", "proposed")) + "```\n")
        plan.append((rel, action)); new_manifest[rel] = sha(final.encode("utf-8")); finals[rel] = final
    problems = validate_payload(finals, root)
    if problems:
        print("CONFIGURATION VALIDATION FAILED (nothing written, no manifest):"); print("\n".join(" - " + x for x in problems)); return 4
    for rel, action in plan:
        dest = root / rel
        if not a.dry_run and not action.startswith("skip"):
            dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(finals[rel], encoding="utf-8")
    report = ["# Efficiency OS install " + ("plan (dry run)" if a.dry_run else "report"), f"date: {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}  python: {a.py} ({ver})  os: {os.name}/{sys.platform}  hook style: {style}", "", "| file | action |", "|---|---|"]
    report += [f"| {r} | {act} |" for r, act in plan] + [""] + diffs
    eos.mkdir(parents=True, exist_ok=True)
    (eos / ("install-plan.md" if a.dry_run else "install-report.md")).write_text("\n".join(report), encoding="utf-8")
    if not a.dry_run and not a.skip_validation:
        sys.path.insert(0, str(eos / "bin"))
        try:
            import verify; verify.rows.clear(); verify.run_hook_commands(json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8")))
            bad = [r for r in verify.rows if r[1] == "FAIL"]
            report += ["", "## Hook command validation (executed through the shell with sample payloads)", "| check | result | detail |", "|---|---|---|"] + [f"| {n} | {r} | {str(d)[:100]} |" for n, r, d in verify.rows]
            (eos / "install-report.md").write_text("\n".join(report), encoding="utf-8")
            if bad: print("\n".join(f"HOOK VALIDATION FAILED: {n}: {d}" for n, _, d in bad)); print("Installed files are in place but hooks do not execute on this machine. Fix the launcher or path style (--hook-style absolute) and rerun."); return 3
        except Exception as e: print("hook validation could not run:", str(e)[:120]); return 3
    if not a.dry_run:
        (eos / "manifest.json").write_text(json.dumps({"version": "2.1.2", "installed": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "py": a.py, "files": new_manifest}, indent=1), encoding="utf-8")
        for d in ("logs/sessions", "bench"): (eos / d).mkdir(parents=True, exist_ok=True)
    print("\n".join(report[:5 + len(plan)]))
    print("\nwritten:", "nothing (dry run; see .claude/efficiency/install-plan.md)" if a.dry_run else f"{sum(1 for _, x in plan if not x.startswith('skip'))} files, {len(finals)} files validated (JSON, frontmatter, syntax), manifest updated, hook commands {'validated by execution' if not a.skip_validation else 'NOT validated (--skip-validation)'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
