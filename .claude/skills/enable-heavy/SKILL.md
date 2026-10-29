---
name: enable-heavy
description: Enable the Fable-backed heavy agent and allow paid-model switches, after explicit user authorization.
---
Explain that fable and [1m] models may consume usage credits beyond the subscription. Ask for an explicit "yes, enable paid models". On yes: tell the user to run `/model fable` once so Claude Code records the usage-credit consent, then create the empty file .claude/efficiency/paid-models.ok, set paid_models_allowed to true in .claude/efficiency/config.json (both are required by the model guard), move .claude/efficiency/agents-disabled/heavy.md to .claude/agents/heavy.md, and say a new session is needed for the agent to appear. To disable: reverse all three.
