# Scheduled task: brain-growth-weekly

Runs weekly (Sunday evening). Mines the last ten days of your work for evidence against your framework and queues it for your triage. Everything it writes is confidential and lives under `growth/`.

Run the `growth-signals` skill from the brain-growth plugin in **mine** mode, then stop. Do not promote, do not write to MEMORY.md, do not message anyone. Stay inside the workspace.

1. Read `.claude/rules/confidential.md` if it exists, then the growth-signals SKILL.md.
2. Run the miner with its defaults (`mine_signals.py`). If it reports 0 candidates, stop and return the stats.
3. Classify the candidates against the framework (Phases 2 and 3 of the skill), write the classified payload under `growth/development/run/`, and run `append_evidence.py`.
4. Return only the stats the scripts printed: candidates added, duplicates skipped, hypotheses updated. No snippets, no criterion text, no names.

Triage is the owner's job: they tick boxes in `growth/development/evidence-candidates.md` and run `promote.py`.
