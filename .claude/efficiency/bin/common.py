#!/usr/bin/env python3
"""Efficiency OS v2.1 shared runtime: paths, session-scoped state, file locks, atomic writes, scrubbing.
Every other script imports this. No third-party dependencies."""
import os, re, sys, json, time, datetime, pathlib, hashlib

VERSION = "2.1.2"

def project_root():
    r = os.environ.get("CLAUDE_PROJECT_DIR")
    return pathlib.Path(r).resolve() if r else pathlib.Path.cwd().resolve()

def eos_dir(): return project_root() / ".claude" / "efficiency"

def logs_dir():
    d = eos_dir() / ("logs/test" if os.environ.get("EOS_TEST") == "1" else "logs")
    (d / "sessions").mkdir(parents=True, exist_ok=True)
    return d

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
def now_us(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")
def ts(): return time.time()

def jload(p, default):
    try: return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception: return default

def config(): return jload(eos_dir() / "config.json", {})

def safe_name(s): return re.sub(r"[^\w.-]", "_", str(s or "nosession"))[:80]

def sha(s): return hashlib.sha256(str(s).encode("utf-8", "replace")).hexdigest()[:12]

SECRET_RX = re.compile(r"((?:api[_-]?key|token|secret|passw(?:or)?d|authorization|bearer|cookie|private[_-]?key)\s*[=:]\s*)(\S+)", re.I)
def scrub(text, limit=200):
    """Removes credential-looking values; never used on prompt text (prompts are not logged at all)."""
    t = SECRET_RX.sub(lambda m: m.group(1) + "<redacted>", str(text))
    t = re.sub(r"\b(sk|ghp|gho|xox[abp]|AKIA)[A-Za-z0-9_-]{8,}", "<redacted>", t)
    return t[:limit]

class FileLock:
    """Exclusive lock on a sidecar .lock file. fcntl on POSIX, msvcrt on Windows, with a bounded wait."""
    def __init__(self, path, timeout=5.0):
        self.path = pathlib.Path(str(path) + ".lock"); self.timeout = timeout; self.fh = None
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a+")
        deadline = ts() + self.timeout
        while True:
            try:
                try:
                    import fcntl; fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except ImportError:
                    import msvcrt; self.fh.seek(0); msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except (OSError, IOError):
                if ts() > deadline: raise TimeoutError(f"lock timeout on {self.path}")
                time.sleep(0.005)
    def __exit__(self, *a):
        try:
            try:
                import fcntl; fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            except ImportError:
                import msvcrt; self.fh.seek(0); msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception: pass
        self.fh.close()

def atomic_write_json(path, obj):
    path = pathlib.Path(path); tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def append_jsonl(path, obj):
    path = pathlib.Path(path)
    with FileLock(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n"); f.flush()

def read_jsonl(path):
    try:
        return [json.loads(l) for l in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception: return []

def session_path(session_id): return logs_dir() / "sessions" / f"{safe_name(session_id)}.json"

class session_state:
    """Locked read-modify-write of one session's state file. Other sessions are never touched."""
    def __init__(self, session_id):
        self.sid = session_id or "nosession"; self.path = session_path(self.sid); self.lock = None
    def __enter__(self):
        self.lock = FileLock(self.path).__enter__()
        self.state = jload(self.path, {"session_id": self.sid, "cursor": 0, "task": None, "last_task_id": None})
        return self.state
    def __exit__(self, et, ev, tb):
        try:
            self.state["updated"] = now(); atomic_write_json(self.path, self.state)
        finally:
            self.lock.__exit__(et, ev, tb)

def most_recent_session():
    files = sorted((logs_dir() / "sessions").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0].stem if files else None

def find_session_for_task(task_id):
    """Looks for an open task first (session files), then closed tasks (tasks.jsonl)."""
    for p in (logs_dir() / "sessions").glob("*.json"):
        st = jload(p, {})
        if (st.get("task") or {}).get("task_id") == task_id or st.get("last_task_id") == task_id:
            return st.get("session_id")
    for t in read_jsonl(logs_dir() / "tasks.jsonl"):
        if t.get("task_id") == task_id: return t.get("session_id")
    return None
