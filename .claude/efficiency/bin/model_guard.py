#!/usr/bin/env python3
"""PreModelSwitch guard. Denies switching to models that may incur usage credits (fable, [1m] variants)
unless .claude/efficiency/paid-models.ok exists. Logs every switch (each switch discards the prompt cache)."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C

def target_model(inp):
    for k, v in inp.items():
        if isinstance(v, str) and any(t in k.lower() for t in ("to", "new", "target", "next", "requested")):
            return v
    return " ".join(str(v) for k, v in inp.items() if isinstance(v, str) and k not in ("session_id", "transcript_path", "cwd", "hook_event_name", "permission_mode"))

def main():
    try: inp = json.load(sys.stdin)
    except Exception: inp = {}
    target = target_model(inp).lower()
    paid = ("fable" in target) or ("[1m]" in target) or ("1m" in target.split("-"))
    allowed = (C.eos_dir() / "paid-models.ok").exists() and C.config().get("paid_models_allowed") is True
    try: C.append_jsonl(C.logs_dir() / "events.jsonl", {"t": C.now(), "event": "model_switch", "target": target[:60], "paid": paid, "allowed": (not paid) or allowed})
    except Exception: pass
    if paid and not allowed:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreModelSwitch", "permissionDecision": "deny",
              "permissionDecisionReason": "Efficiency OS: this model may use usage credits. Run /enable-heavy (requires an explicit yes) to allow it."}}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
