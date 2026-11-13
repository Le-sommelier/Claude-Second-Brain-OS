Run the daily ingest for this workspace.

1. Invoke the `brain-ingest:orchestrator` skill and follow it exactly. It plans the date window (catching up any days missed since the last successful run), runs every installed ingest brick, and finalises the run.
2. You do not read source content (Slack text, transcripts, page bodies) in this session. You only handle the brick return objects.
3. Do not publish, post or send anything anywhere. The ingest is read-only on every external system.
4. End by repeating the run summary printed by `brain run finalise` verbatim. If planning fails, stop and report the error: without a run context there is no safe run.
