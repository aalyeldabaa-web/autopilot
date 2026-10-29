#!/usr/bin/env python3
"""PreToolUse guard (layer 1 of 2). Blocks destructive, deploy, publish, privilege and secret-touching operations
with exit 2 so the model asks the user. Covers bash/zsh, PowerShell and cmd.exe syntax, command chains, and
obfuscation (encoded commands, eval, base64 pipes), which it blocks outright because it cannot inspect them.
Layer 2 is Claude Code's native permissions.deny list in settings.json (see settings). Regex is not a complete
security boundary: anything this script cannot parse is treated as sensitive (fail closed), and logs record
only a category and a hash of the command, never the command itself. Importable: check(tool, tool_input)."""
import sys, json, re, os, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*|\n")
# (regex, category). Checked per segment, case-insensitive, on a whitespace-normalized command.
RULES = [
    (r"(^|\s)(remove-item|ri|rmdir|rd|del|erase)\b.*(-recurse|-r\b|-force|-fo\b|/s|/q)", "recursive or forced delete (PowerShell or cmd)"),
    (r"(^|\s)rm\s+-r.*\s/\s*$", "delete root"),
    (r"\bgit\s+push\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b|\+[a-z])", "force push"),
    (r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|branch\s+-d\s|branch\s+--delete\s+--force|checkout\s+--\s+\.|restore\s+\.|push\s+\S+\s+--delete|filter-branch|update-ref\s+-d)", "destructive git operation"),
    (r"\b(drop|truncate)\s+(table|database|schema|index)\b|\bdelete\s+from\s+\w+\s*;?\s*$", "destructive SQL"),
    (r"\b(curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm)\b.*\|\s*(sudo\s+)?(ba|z|da)?sh\b|\b(iwr|irm|invoke-webrequest|invoke-restmethod)\b.*\|\s*(iex|invoke-expression)\b", "piping a remote script into a shell"),
    (r"(^|\s)(sudo|doas|runas|start-process\s+.*-verb\s+runas)\b", "privilege escalation"),
    (r"\bchmod\s+(-r\s+)?[0-7]*777\b|\bchown\s+-r\s+\S+\s+/|\bicacls\b.*\/grant\s+everyone|\bset-executionpolicy\b", "permission or policy escalation"),
    (r"\b(kubectl|terraform|pulumi|aws|gcloud|az|heroku|vercel|netlify|fly|flyctl|wrangler|serverless|sam|cdk)\s+(apply|deploy|destroy|delete|rm|push|publish|up)\b", "deployment or cloud mutation"),
    (r"\b(aws|gcloud|az|heroku|gh|flyctl|doctl|linode-cli)\s+[\w-]+(\s+[\w-]+)?\s+(rm|rb|delete|destroy|terminate|deploy|push|update|put|purge)\b", "cloud resource mutation"),
    (r"\bdocker\s+(push|rm|rmi|system\s+prune|volume\s+rm|run\b.*--privileged)|\bdocker-compose\s+down\s+.*-v", "container mutation"),
    (r"\b(mkfs|diskpart|format\s+[a-z]:|dd\s+if=)|:\(\)\s*\{\s*:\|:&\s*\};:|\bformat-volume\b|\bclear-disk\b", "disk write or fork bomb"),
    (r"\b(cat|type|printenv|less|more|head|tail|get-content|gc|select-string|findstr|grep|rg)\b[^|&;]*(\.env(\.\w+)?\b|id_rsa|id_ed25519|\.pem\b|credentials|\.netrc|\.npmrc|\.pypirc|secrets?\.(json|ya?ml|toml))", "secret exposure"),
    (r"(^|\s)(env|printenv|set|get-childitem\s+env:|dir\s+env:)\s*$|(^|\s)(echo|write-output|write-host)\s+\$?\{?env:?[a-z_]*(key|token|secret|pass)", "environment secret exposure"),
    (r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bgem\s+push\b|\bnuget\s+push\b|\bdotnet\s+nuget\s+push\b|\bgh\s+release\s+create\b", "package publish or release"),
    (r"(^|\s)(crontab\s+-r|schtasks\s+/delete|launchctl\s+unload)", "scheduler mutation"),
    (r"\b(ssh|scp|rsync)\b.*\s(root@|.*@prod|.*prod\.)", "remote production access"),
    (r"(^|\s)(-encodedcommand|-enc\s|-ec\s|-e\s+[a-z0-9+/]{20,}|frombase64string|base64\s+(-d|--decode)\s*\|)|\b(eval|invoke-expression|iex)\s|\$\(\s*(curl|wget|iwr|irm)\b", "encoded, evaluated or dynamically fetched command (cannot be inspected)"),
    (r"\bclaude\b.*--dangerously-skip-permissions|\bclaude\b.*--permission-mode\s+bypass", "disabling Claude Code permissions"),
    (r"efficiency[\\/]waivers", "any shell access to the Efficiency OS waivers folder (only the user may create a waiver, by hand)"),
    (r"(>|>>|\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btruncate\b|\bset-content\b|\bout-file\b|\badd-content\b).*efficiency[\\/](logs|gates\.json|config\.json|pricing\.json|bin|tests)|efficiency[\\/](logs|gates\.json|config\.json|pricing\.json|bin|tests)\S*\s*(>|>>)", "shell write to Efficiency OS logs, gates, config or runtime (edited only by the installer or the user)"),
]
SECRET_FILES = re.compile(r"(^|[\\/])(\.env(\.[\w-]+)?|id_rsa[\w.]*|id_ed25519[\w.]*|[\w.-]*\.(pem|key|p12|pfx)|[\w.-]*credentials[\w.-]*|secrets?\.[\w]+|\.npmrc|\.pypirc|\.netrc|\.git-credentials|\.aws[\\/]config|\.kube[\\/]config)$", re.I)
PROTECTED_WRITES = re.compile(r"(^|[\\/])(\.claude[\\/]settings(\.local)?\.json|\.claude[\\/]efficiency[\\/](bin|tests|bench[\\/](run|compare)\.py|config\.json|pricing\.json|gates\.json|waivers|logs)|\.github[\\/]workflows[\\/])", re.I)

def normalize(cmd):
    c = cmd.replace("\r", "\n")
    c = re.sub(r"`\s*\n", " ", c)                 # PowerShell backtick continuation
    c = re.sub(r"\\\s*\n", " ", c)                # bash backslash continuation
    c = re.sub(r"[\"']", "", c)                   # quotes do not change intent for these rules
    c = re.sub(r"\s+", " ", c).strip().lower()
    return c

DANGEROUS_TARGET = re.compile(r"^(/|~|\$home|\$\{home\}|%\w+%|[a-z]:[\\/]|\\\\|\*$|\.$|\.\.$|\.\./)")
def rm_rule(seg):
    """rm with a recursive flag whose target is absolute, home, drive-rooted, a bare wildcard, or the current/parent dir."""
    toks = seg.split()
    if not toks or toks[0] not in ("rm", "rmdir", "rd"): return False
    flags = [t for t in toks[1:] if t.startswith("-")]; targets = [t for t in toks[1:] if not t.startswith("-")]
    recursive = any("r" in f.lower() for f in flags) or toks[0] in ("rmdir", "rd")
    return recursive and any(DANGEROUS_TARGET.match(t) for t in targets)

def check(tool, tool_input):
    """Returns (blocked: bool, category: str)."""
    tool_input = tool_input or {}
    if tool in ("Bash", "PowerShell", "Shell"):
        raw = tool_input.get("command") or tool_input.get("cmd") or ""
        if not isinstance(raw, str): return True, "unparseable command input"
        full = normalize(raw)
        for seg in [s for s in SPLIT.split(full) if s and s.strip()] + [full]:
            if rm_rule(seg): return True, "recursive delete of an absolute, home, drive, wildcard or current-directory path"
            for rx, cat in RULES:
                if re.search(rx, seg): return True, cat
        return False, ""
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        fp = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if SECRET_FILES.search(fp): return True, "write to a credentials or secrets file"
        if PROTECTED_WRITES.search(fp): return True, "write to Claude Code settings, CI workflows, or the Efficiency OS runtime (ask the user)"
        return False, ""
    if tool == "Read":
        fp = tool_input.get("file_path") or ""
        if SECRET_FILES.search(fp): return True, "read of a credentials or secrets file"
        return False, ""
    return False, ""

def log(category, cmd_or_path):
    try:
        import common as C
        C.append_jsonl(C.logs_dir() / "events.jsonl", {"t": C.now(), "event": "guard_block", "category": category, "cmd_sha": C.sha(cmd_or_path)})
    except Exception: pass

def main():
    try: inp = json.load(sys.stdin)
    except Exception:
        sys.stderr.write("EOS guard: could not parse hook input; blocking as a precaution. Ask the user to run this step.\n"); return 2
    try:
        tool = inp.get("tool_name", ""); ti = inp.get("tool_input") or {}
        blocked, cat = check(tool, ti)
    except Exception as e:
        sys.stderr.write(f"EOS guard: internal error ({type(e).__name__}); blocking as a precaution. Ask the user to run this step.\n"); return 2
    if blocked:
        log(cat, json.dumps(ti, sort_keys=True))
        sys.stderr.write(f"EOS guard blocked this {tool} call: {cat}. If it is intended, ask the user to run it themselves.\n")
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
