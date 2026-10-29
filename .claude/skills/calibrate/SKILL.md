---
name: calibrate
description: Recompute estimate ranges and routing recommendations from measured task history.
---
Run `python3 .claude/efficiency/bin/calibrate.py`. Show the per-class table and the recommendations. If a recommendation suggests changing config.json thresholds, propose the exact change and apply it only on approval. Never conclude that one model is better than another from this data; say "in this project's measured history" instead.
