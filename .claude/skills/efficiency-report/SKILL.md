---
name: efficiency-report
description: Show execution history, per-model tokens and cost, per-agent timings with intended vs actual model, recorded routing decisions, gate runs, and a Mermaid orchestration diagram. Use when the user asks for a usage report, what agents ran, or how a task was routed.
---
Run `python3 .claude/efficiency/bin/report.py 15` (add `--task <id>` if the user named one, `--session <id>` for one session) and show the output as is: tables, legend, Mermaid block. Then add at most three sentences: the biggest token consumer, any intended-vs-actual model mismatch, any tasks whose gate verdict is NONE or FAIL. Do not editorialize about model quality. Do not spawn agents or make model calls to produce this report.
