---
name: ingest
description: Run the ingest now. Fetches new Slack, meetings, Confluence and notes through every installed brick, and optionally catches up N days. Use for "run the ingest", "ingest now", "catch up the last 3 days".
argument-hint: "[catch up N days]"
allowed-tools: Bash(brain *) Read Write Skill
---

# Run the ingest now

This is the manual entry to the orchestrator. It does no ingest work itself.

1. Parse the request.
   - No argument, or "now": a normal run. The window is every day since the last successful run, plus today.
   - "catch up N days" (or `N`): force the window to the last N days ending today. Pass it to the planner as `--catch-up N` (capped by `max_catchup_days` in the pipeline settings; say so if you had to cap it).
2. Run `brain doctor` once. If it reports a missing connector for an installed brick, tell the owner which one, and carry on: that brick will return `skipped`.
3. Invoke the `brain-ingest:orchestrator` skill with the parsed window and follow it.
4. Finish by showing the orchestrator's run summary, then one line on anything that needs the owner (a failed brick, a skipped connector, dates left partial).

Never read source content here. Never post or react anywhere.
