#!/usr/bin/env python3
"""Compares v1 vs v2 benchmark results. Pairs only runs of the same task with the same spec_hash (identical prompt,
setup, acceptance). Improvement % only from >= 2 valid runs per side; otherwise INCONCLUSIVE. Also sums per-model
tokens from claude -p's modelUsage so each side shows which models did the work."""
import json, pathlib, statistics, sys
EOS = pathlib.Path(__file__).resolve().parents[1]; RES = EOS / "bench" / "results.jsonl"

def tokens(r):
    u = r.get("usage") or {}
    return sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))

def per_model(rows):
    """Median per-run tokens for each model that claude -p reported (modelUsage)."""
    per = {}
    for r in rows:
        for m, u in (r.get("model_usage") or {}).items():
            if isinstance(u, dict):
                per.setdefault(m, []).append(sum(int(u.get(k) or 0) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")))
    return {m: int(statistics.median(v)) for m, v in per.items()}

def main():
    rows = [json.loads(l) for l in RES.read_text(encoding="utf-8").splitlines() if l.strip()] if RES.exists() else []
    print("| task | spec | metric | v1 (n) | v2 (n) | change | verdict |\n|---|---|---|---|---|---|---|")
    pairs = sorted({(r["task"], r.get("spec_hash")) for r in rows})
    for task, spec in pairs:
        sel = [r for r in rows if r["task"] == task and r.get("spec_hash") == spec]
        metrics = (("tokens", tokens), ("duration_s", lambda r: r.get("duration_s") or 0), ("est_api_cost", lambda r: r.get("total_cost_usd_estimate") or 0), ("turns", lambda r: r.get("num_turns") or 0))
        g = {c: [r for r in sel if r["config"] == c and r.get("valid")] for c in ("v1", "v2")}
        versions = sorted({r.get("claude_version", "unknown") for r in sel}); comparable = len(versions) == 1
        if not comparable: print(f"| {task} | {spec} | execution conditions | {versions} | | | INCONCLUSIVE: runs used different Claude Code versions |")
        leaks = [r for r in sel if r.get("telemetry_written_inside_worktree") is False and r["config"] == "v2"]
        if leaks: print(f"| {task} | {spec} | isolation | | | | WARN: {len(leaks)} v2 run(s) wrote no telemetry inside the worktree (hooks may have pointed at the main project) |")
        n1, n2 = len(g["v1"]), len(g["v2"])
        p1 = sum(1 for r in g["v1"] if r.get("acceptance_pass")); p2 = sum(1 for r in g["v2"] if r.get("acceptance_pass"))
        print(f"| {task} | {spec} | acceptance pass | {p1}/{n1} | {p2}/{n2} | | descriptive |")
        for metric, fn in metrics:
            if not comparable: print(f"| {task} | {spec} | {metric} | | | | INCONCLUSIVE: not comparable |"); continue
            if n1 < 2 or n2 < 2: print(f"| {task} | {spec} | {metric} | {n1} | {n2} | | INCONCLUSIVE: fewer than 2 valid runs per side |"); continue
            v1 = [fn(r) for r in g["v1"] if r.get("acceptance_pass")]; v2 = [fn(r) for r in g["v2"] if r.get("acceptance_pass")]
            if len(v1) < 2 or len(v2) < 2: print(f"| {task} | {spec} | {metric} | {len(v1)} | {len(v2)} | | INCONCLUSIVE: fewer than 2 passing runs per side (only passing runs are comparable) |"); continue
            m1, m2 = statistics.median(v1), statistics.median(v2)
            if m1 == 0: print(f"| {task} | {spec} | {metric} | 0 ({len(v1)}) | {m2:.0f} ({len(v2)}) | | INCONCLUSIVE: zero baseline |"); continue
            change = (m2 - m1) / m1 * 100
            overlap = max(v1) >= min(v2) and max(v2) >= min(v1)
            verdict = "INCONCLUSIVE: ranges overlap" if overlap and abs(change) < 25 else ("improvement" if change < 0 else "regression")
            print(f"| {task} | {spec} | {metric} | {m1:.0f} ({len(v1)}) | {m2:.0f} ({len(v2)}) | {change:+.0f}% | {verdict} |")
        for c in ("v1", "v2"):
            pm = per_model(g[c])
            if pm: print(f"| {task} | {spec} | models used ({c}), median tokens per run | {', '.join(f'{m}: {t}' for m, t in sorted(pm.items()))} | | | measured by claude -p |")
    print("| retries | not reported by claude -p; num_turns is the closest observable | | | | | |")
    print("\nMedians over valid, acceptance-passing runs with identical spec_hash and the same Claude Code version. Cost is the API-equivalent estimate reported by claude -p, not the subscription bill. 'Completed tasks per usage window' is not measurable headlessly; use tokens per passing task as the proxy.")

if __name__ == "__main__":
    try: main()
    except BrokenPipeError: pass
