---
name: handoff
description: Write the current task state to .claude/efficiency/HANDOFF.md so the session can be cleared and resumed cheaply.
---
Write .claude/efficiency/HANDOFF.md: goal, decisions and why, files changed, what is done, what is next, open questions, the current task id from the [EOS] line and its gate verdict (`gate.py verdict --task <id>`). Under 40 lines. Then say: safe to /clear; next session starts with "read .claude/efficiency/HANDOFF.md and continue".
