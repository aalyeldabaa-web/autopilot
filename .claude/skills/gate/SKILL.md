---
name: gate
description: Run the required quality gates for the current task and show the recorded verdict. Use when the user asks "did it pass", "run the gates", or before declaring a task done.
---
Take the task id from the latest [EOS] line. Run `python3 .claude/efficiency/bin/gate.py required --task <id>` then `gate.py status --task <id>`. Show the status output unchanged. A verdict of PASS is the only acceptable basis for saying a task is verified; if FAIL or NONE, say what failed and what you will repair. Never describe a gate as passed unless gate.py recorded exit 0 for it.
