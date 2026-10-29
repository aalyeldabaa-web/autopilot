# Efficiency OS install report
date: 2026-10-29T18:07:42+00:00  python: python3 (3.13)  os: posix/linux  hook style: env

| file | action |
|---|---|
| .claude/agents/architect.md | create |
| .claude/agents/builder-isolated.md | create |
| .claude/agents/builder.md | create |
| .claude/agents/reviewer-deep.md | create |
| .claude/agents/reviewer.md | create |
| .claude/agents/scout.md | create |
| .claude/efficiency/ROUTING.md | create |
| .claude/efficiency/agents-disabled/heavy.md | create |
| .claude/efficiency/bench/compare.py | create |
| .claude/efficiency/bench/run.py | create |
| .claude/efficiency/bench/tasks.json | create |
| .claude/efficiency/bin/calibrate.py | create |
| .claude/efficiency/bin/classify.py | create |
| .claude/efficiency/bin/common.py | create |
| .claude/efficiency/bin/format_hook.py | create |
| .claude/efficiency/bin/gate.py | create |
| .claude/efficiency/bin/guard.py | create |
| .claude/efficiency/bin/install.py | skip (identical) |
| .claude/efficiency/bin/model_guard.py | create |
| .claude/efficiency/bin/report.py | create |
| .claude/efficiency/bin/smoke.py | create |
| .claude/efficiency/bin/statusline.py | create |
| .claude/efficiency/bin/telemetry.py | create |
| .claude/efficiency/bin/verify.py | create |
| .claude/efficiency/config.json | create |
| .claude/efficiency/gates.json | create |
| .claude/efficiency/pricing.json | create |
| .claude/efficiency/tests/test_all.py | create |
| .claude/settings.json | create |
| .claude/skills/benchmark/SKILL.md | create |
| .claude/skills/calibrate/SKILL.md | create |
| .claude/skills/codify/SKILL.md | create |
| .claude/skills/cost-check/SKILL.md | create |
| .claude/skills/efficiency-report/SKILL.md | create |
| .claude/skills/enable-heavy/SKILL.md | create |
| .claude/skills/gate/SKILL.md | create |
| .claude/skills/handoff/SKILL.md | create |
| .claude/skills/lean-check/SKILL.md | create |
| .claude/skills/route/SKILL.md | create |
| .gitignore | create |
| CLAUDE.md | create |
| scripts/README.md | create |


## Hook command validation (executed through the shell with sample payloads)
| check | result | detail |
|---|---|---|
| hook command executes: SessionStart | PASS | exit 0 |
| hook command executes: UserPromptSubmit | PASS | history for this class yet\" (deterministic first pass; override with a one-line reason if wrong)"}} |
| hook command executes: SubagentStart | PASS | exit 0 |
| hook command executes: SubagentStop | PASS | exit 0 |
| hook command executes: Stop | PASS | exit 0 |
| hook command executes: SessionEnd | PASS | exit 0 |
| hook command executes: PreCompact | PASS | exit 0 |
| hook command executes: PreToolUse | PASS | exit 0 |
| hook command executes: PreModelSwitch | PASS | exit 0 |
| status line command executes | PASS | Opus | ctx 12% | last 0k · |