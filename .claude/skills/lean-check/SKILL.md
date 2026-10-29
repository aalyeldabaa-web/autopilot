---
name: lean-check
description: Audit what is loaded on every turn in this project (CLAUDE.md files, MCP servers, skills, agents) and propose cuts.
---
Measure line counts of global and project CLAUDE.md, list MCP servers from `claude mcp list` and .mcp.json with a rough tool count each, list skills and agents, and read .claude/efficiency/logs/overhead.json if present (hook latency measured by verify.py). Flag anything loaded every turn that this project does not use. Output a checklist of proposed cuts. Change nothing without approval.
