---
name: route
description: Classify the next task, show the route, estimate and gates, and ask for confirmation before any class M/L work. Use when the user asks "how would you route this" or wants the plan before execution.
---
Run `python3 .claude/efficiency/bin/classify.py "<the task text>"`. Print the route line as defined in ROUTING.md, add your own one-line judgment (agree or override with reason), the estimate labeled calibrated or low confidence, and the files you expect to load. Wait for the user before executing class M or L.
