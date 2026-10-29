# Efficiency OS routing policy (loaded for class M/L/X only)

## Classes
The classifier (deterministic, Arabic/English/mixed) scores prompt length, file paths, keyword groups and repo size, and reports confidence. T requires positive evidence; unknown vocabulary is never T.
| Class | Meaning | Default route | Gate (executed by gate.py) |
|---|---|---|---|
| T | trivial: typo, rename, log line, comment, config value | direct, NO_DELEGATION | required gates for T (usually none) or one targeted check |
| S | small: one feature or fix in ≤ direct_file_threshold known files | direct; builder only if files unknown or > threshold | test + lint |
| M | medium: multi-file feature, non-trivial bug, needs a plan | (scout if exploration) -> plan in main -> builder -> reviewer | test + lint, then reviewer report |
| L | large: architecture, migration, cross-cutting refactor, hard debugging | architect -> builders (parallel, worktrees if overlapping) -> reviewer-deep | test + lint, reviewer-deep report, plan acceptance criteria |
| X | only after /enable-heavy and the user naming it | as L, heavy replaces builder for the hardest step | as L |
Flags: `security` adds reviewer-deep at any class ≥ S. `destructive` means stop and confirm with the user before any command in that category (the guard blocks it anyway). `broad` forces a scout first. `confidence=low` means the vocabulary was not recognized: state your own reading of the class in the route line.

## Overrides (model judgment, recorded)
Override the classifier when you can state why in one line, as `override: M->S (plan already in prompt, two known files)`. The Stop hook records route:/override:/done: lines you print, so the override is auditable in /efficiency-report.

## Execution strategy
1. NO_DELEGATION whenever direct work costs less than delegation overhead (an agent launch pays its own system prompt plus CLAUDE.md plus the files it reads). Rule of thumb: fewer than four files to read and ~150 lines to write means do it yourself.
2. Plan before delegating on M/L. Use plan mode for L. The plan lists files per step and marks independent steps.
3. Parallelism: independent steps run as concurrent builders up to `max_parallel_agents`. Use builder-isolated when two steps touch the same directory. Dependent steps run in order.
4. Pass agents only what they need: the step text, file paths, the gate command. Not the whole plan.
5. Collect reports, run `gate.py required --task <id>`, then review per the class.
6. Retry: on a failed gate, send the failing output and only the relevant files back to the same builder, up to `max_repair_attempts`. Then escalate: builder -> architect re-plan -> (if enabled) heavy. Never silently repeat the full route.
7. Agents never spawn agents.

## Estimate format (print before M/L work)
`est: agents <n> | tokens <p25>k-<p75>k (calibrated, n=<samples>) or "low confidence: no history" | time ~<min> | context: <files to load>`
Numbers come from calibration.json; below `estimate_min_samples` say "low confidence" and give no range.

## Explaining decisions
One route line before work, one done line after: `done: <task id> | <agents actually used> | gate <PASS/FAIL> | retries <n>`. Nothing more unless asked for /efficiency-report.

## Context health
Status line shows context %. At 60% finish the current step, /handoff, /clear. No CLAUDE.md edits, MCP changes or main-model switches inside a session.
