#!/usr/bin/env python3
"""PostToolUse formatter hook. Runs the formatter the installer registered (--format-cmd) on the edited file.
Never blocks: exit 0 always; formatter errors go to stderr for the model to see."""
import json, sys, subprocess, shlex, os
FORMAT_CMD = ""
def main():
    try: inp = json.load(sys.stdin)
    except Exception: return 0
    fp = (inp.get("tool_input") or {}).get("file_path") or ""
    if not fp or not FORMAT_CMD or not os.path.exists(fp): return 0
    cmd = FORMAT_CMD.replace("{file}", shlex.quote(fp) if os.name != "nt" else '"' + fp + '"')
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=55, cwd=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if p.returncode != 0: sys.stderr.write(f"formatter exit {p.returncode}: {(p.stderr or p.stdout)[-300:]}\n")
    except subprocess.TimeoutExpired: sys.stderr.write("formatter timed out\n")
    return 0
if __name__ == "__main__":
    sys.exit(main())
