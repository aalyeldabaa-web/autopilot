#!/usr/bin/env python3
"""Deterministic calibration from measured tasks. Writes calibration.json (per class: n, p25/median/p75 tokens,
median duration, gate fail rate, direct vs delegated medians, model mismatches, per-model token share) and prints
rule-based recommendations. Never claims one model is better than another."""
import json, statistics, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common as C
import gate

def q(xs, p):
    xs = sorted(xs); i = max(0, min(len(xs) - 1, int(round(p * (len(xs) - 1))))); return xs[i]

def main():
    tasks = [t for t in C.read_jsonl(C.logs_dir() / "tasks.jsonl") if (t.get("totals") or {}).get("total", 0) > 0 and t.get("class") in ("T", "S", "M", "L", "X")]
    min_n = C.config().get("estimate_min_samples", 5); out, recs = {}, []
    rev = gate.tree_revision(); gates = C.read_jsonl(C.logs_dir() / "gates.jsonl"); subs = C.read_jsonl(C.logs_dir() / "subagents.jsonl")
    for cls in ("T", "S", "M", "L", "X"):
        ts = [t for t in tasks if t["class"] == cls]
        if not ts: continue
        tot = [t["totals"]["total"] for t in ts]; dur = [t.get("duration_s") or 0 for t in ts]
        verdicts = [gate.verdict_for(t["task_id"], cls, t.get("flags"), revision=rev, records=gates, subagents=subs)[0] for t in ts]
        rec = sum(1 for v in verdicts if v != "NONE"); fails = sum(1 for v in verdicts if v == "FAIL")
        delegated = [t["totals"]["total"] for t in ts if t.get("subagents")]; direct = [t["totals"]["total"] for t in ts if not t.get("subagents")]
        mism = sum(1 for t in ts for s in t.get("subagents", []) if s.get("model_match") is False)
        share = {}
        for t in ts:
            for m, u in (t.get("by_model") or {}).items(): share[m] = share.get(m, 0) + u["total"]
        out[cls] = {"n": len(ts), "p25": q(tot, .25), "median": q(tot, .5), "p75": q(tot, .75), "median_duration_s": statistics.median(dur),
                    "gate_fail_rate": round(fails / rec, 2) if rec else None, "gate_recorded_rate": round(rec / len(ts), 2),
                    "delegated_n": len(delegated), "direct_n": len(direct), "median_delegated": statistics.median(delegated) if delegated else None,
                    "median_direct": statistics.median(direct) if direct else None, "model_mismatches": mism, "tokens_by_model": share,
                    "low_confidence_n": sum(1 for t in ts if t.get("confidence") == "low")}
        c = out[cls]
        if c["n"] < min_n: recs.append(f"{cls}: {c['n']} samples, below {min_n}; estimates stay low confidence.")
        if c["median_delegated"] and c["median_direct"] and c["median_delegated"] > 1.5 * c["median_direct"] and cls in ("S", "M"):
            recs.append(f"{cls}: delegated tasks cost {c['median_delegated']/c['median_direct']:.1f}x direct ones in this project's history; consider raising direct_file_threshold.")
        if c["gate_fail_rate"] is not None and c["gate_fail_rate"] > 0.3: recs.append(f"{cls}: gate fail rate {c['gate_fail_rate']}; consider a reviewer step earlier or higher builder effort.")
        if c["gate_recorded_rate"] < 0.6: recs.append(f"{cls}: only {c['gate_recorded_rate']*100:.0f}% of tasks ran a gate; gate.py is being skipped.")
        if mism: recs.append(f"{cls}: {mism} subagent runs used a model other than the one in the agent file; check CLAUDE_CODE_SUBAGENT_MODEL and availableModels.")
        if c["low_confidence_n"] > c["n"] / 2: recs.append(f"{cls}: most prompts classified at low confidence; add project vocabulary to classify.py keyword lists.")
    C.atomic_write_json(C.eos_dir() / "calibration.json", out)
    print(json.dumps(out, indent=1, ensure_ascii=False)); print("\nRecommendations (deterministic rules over this project's measured history, not verdicts about model quality):")
    print("\n".join(f"- {x}" for x in recs) or "- none yet")

if __name__ == "__main__":
    main()
