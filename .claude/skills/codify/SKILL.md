---
name: codify
description: Turn a task done more than once into a deterministic script in scripts/ and register it.
---
Ask which task if not stated. Write the script in the project's main language with arguments instead of hardcoded values, a usage line at the top, safe defaults, and no destructive operations without a --confirm flag. Run it once through gate.py so the run is recorded. Add one line to scripts/README.md. Report the token-free command the user can run next time.
