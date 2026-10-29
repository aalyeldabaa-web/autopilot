---
name: benchmark
description: Run the v1 vs v2 benchmark suite in isolated git worktrees and report comparable measurements or an explicit inconclusive result.
---
This consumes subscription usage (several headless runs). Before running: show .claude/efficiency/bench/tasks.json, the number of runs, and the rough usage this will take; get an explicit yes. Then run `python3 .claude/efficiency/bench/run.py --config v1 --task all --runs 3` and `python3 .claude/efficiency/bench/run.py --config v2 --task all --runs 3` (or `--task <name>` for one), followed by `python3 .claude/efficiency/bench/compare.py`. Show compare.py output unchanged. Improvement percentages appear only where compare.py computed them; otherwise report inconclusive and why. Confirm afterwards that `git worktree list` shows only the main tree.
