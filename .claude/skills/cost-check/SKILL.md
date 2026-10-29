---
name: cost-check
description: Monthly usage review against baseline.md using ccusage plus the local task log, with one recommended fix.
---
Run `npx ccusage@latest monthly` and `daily` (adapt flags via --help). Compare with .claude/efficiency/baseline.md: total tokens, cache-read share, tokens per active day. Run `python3 .claude/efficiency/bin/calibrate.py` and read its recommendations. Report in under ten lines: better or worse than baseline, the single biggest leak, one concrete fix. Append the summary to .claude/efficiency/history.md with the date. Say explicitly that ccusage cost figures are API-equivalent estimates, not the subscription bill.
