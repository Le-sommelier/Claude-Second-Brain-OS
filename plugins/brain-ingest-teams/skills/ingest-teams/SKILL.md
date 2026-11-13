---
name: ingest-teams
description: Fetch brick (lane m365). Finds every Teams meeting in the owner's Outlook calendar since the last run that produced a transcript, and saves the raw VTT byte-for-byte into inbox/transcripts/teams/ for ingest-meeting-files to normalise. A per-event ledger handles retries. Verbatim, read-only. Also runnable by hand to force a re-fetch.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read ToolSearch mcp__*__outlook_calendar_search mcp__*__read_resource
---

# Teams transcripts: fetch brick

Follows the brick contract in `docs/module-contract.md` §4. This brick owns its window through the
ledger, so it does not read the run context. Runs on Sonnet (calendar triage needs judgement); the
transcript text itself never passes through you, because scripts write it.

**Reads:** Microsoft 365 connector (`outlook_calendar_search`, `read_resource`). Read-only.
**Writes:** `inbox/transcripts/teams/<YYYY-MM-DD HH.MM.00 subject>.vtt` (+ optional `.meta.json`)
**State:** `meetings.ledger` in `.claude/paths.json` (default `system/run/teams-ledger.json`), via `scripts/ledger.py`
**Config:** `.claude/brain/teams.json` (lookback, retry policy, extra timezones)

**Step 0: load the M365 tools.** In a subagent session the connector tools are deferred. Run
`ToolSearch` with `query: "outlook_calendar_search read_resource"` and load both. If they are still
not callable, return `skipped` with reason `"M365 connector offline: reconnect Microsoft 365 in the connectors settings"` and do nothing else.

All commands are `python3 ${CLAUDE_SKILL_DIR}/scripts/<script> ...`, one per call, from the workspace root.

## Steps

1. **Get the window.** `ledger.py --window` prints `{since, until}`. Note the time now as `run_start`.
2. **List events.** `outlook_calendar_search(query="*", afterDateTime=since, beforeDateTime=until, order="oldest", limit=25)`; page with `offset` until exhausted.
3. **Triage each event.**
   1. `isCancelled` -> record `cancelled`; `isAllDay` -> record `all_day`; move on.
   2. `ledger.py --should-attempt --event-id <id> --start "<start.dateTime>"`. If false, skip.
   3. `read_resource("calendar:///events/<id>")`. No `onlineMeeting` -> record `no_online_meeting`.
   4. `event_window_utc.py --start "<start.dateTime>" --end "<end.dateTime>" --tz "<start.timeZone>" --subject "<subject>"` gives `start_utc`, `end_utc`, `vtt_filename`. An `Unmapped Windows timezone` error means: skip the event, add an observation naming the zone. Never guess a mapping.
   5. `read_resource("<meetingTranscriptUrl>?start=<start_utc>&end=<end_utc>")`. `notFoundReason: transcripts_empty` -> record `transcripts_empty`; any other not-found -> `meeting_not_found`.
   6. **Occurrence check.** Never compare against `meeting.startDateTime` (it is the series start for recurring meetings). The save script filters by `createdDateTime` against the occurrence window itself.
   7. **Save. Never type transcript text yourself.** Pass the attendee display names from the calendar event (names only) so attendance can be computed:
      - Result spilled to a file ("saved to <path>"): `python3 ${CLAUDE_SKILL_DIR}/scripts/save_transcript.py --src "<path>" --start-utc "<start_utc>" --end-utc "<end_utc>" --out "inbox/transcripts/teams/<vtt_filename>" --invited "Name A;Name B"`
      - Result came back inline: `python3 ${CLAUDE_SKILL_DIR}/scripts/save_transcript.py --from-session-uri "<exact uri>" ...` (same other flags). It reads the verbatim result from the session log. If it says `no read_resource result for that uri`, record nothing, add a warning, move on; the ledger retries next run.
      - Exit 2 / `occurrence_mismatch` -> record `occurrence_mismatch`. `ok: false` -> record `meeting_not_found` and add a warning; write nothing. Exit 3 `duplicate_bytes` (identical to a transcript already saved, usually the same meeting under another event) -> record `occurrence_mismatch` and add an observation naming the event.
      - Record `fetched` with `--vtt-path` only after the file exists and passed the script.
   8. Record every outcome: `ledger.py --record --event-id <id> --subject "<subject>" --start "<start.dateTime>" --status <status>` (+ `--vtt-path "<path>"` for `fetched`). The ledger applies the retry policy: `fetched` and structural skips are final, the rest retry up to `max_attempts` within `retry_window_days`.
4. **Close the run.** `ledger.py --set-last-run <until>`, then `ledger.py --summary --since <run_start>`. Return its counts as `counts` (`fetched` plus `by_status`) and its `files` as `outputs`. Never include transcript content.

Summarising is a separate brick (brain-summarise); never summarise here. To force a re-fetch, delete the event's entry from the ledger JSON and run this skill by hand.

## Failure modes

Connector offline -> `skipped` with reason. Single-event failures never fail the run: they go in `warnings` and stay retryable in the ledger. Return `status: partial` if any event warned.
