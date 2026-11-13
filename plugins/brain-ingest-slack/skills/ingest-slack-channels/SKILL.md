---
name: ingest-slack-channels
description: Fetch brick. Copies the full message flow (roots and threads) of the watched Slack channels for one target date into per-channel-per-day files under raw/slack/, and records every attempt in the channel ledger. Verbatim and read-only. Run by the ingest orchestrator, or by hand for one date.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write mcp__slack__slack_read_channel mcp__slack__slack_read_thread mcp__slack__slack_read_user_profile mcp__slack__slack_search_channels
model: haiku
---

# Slack channels: fetch brick

Follow the brick contract (`docs/module-contract.md` section 4 in the claude-second-brain-os repo): one
JSON return, stats only, verbatim text, read-only. The caller gives you a `target_date`.

**Connector:** the Slack MCP. Tools used (names as exposed by the connector; the prefix varies
by install): `slack_read_channel`, `slack_read_thread`, `slack_read_user_profile`,
`slack_search_channels`. Allow-list them in your settings if the prefix differs from
`mcp__slack__`. You never call a write tool (no send, react or canvas tools).

**Reads:** the channel list (`paths.json` slack.channels_config) and settings (slack.settings).
**Writes:** `raw/slack/YYYY/YYYY-Www/slack-YYYY-MM-DD-<slug>.md`
**State:** the channel ledger (written by the formatter, not by you).

## Steps

1. **Plan.** Run `python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_channels.py --date <target_date>`. It prints the window (`oldest_ts`, `latest_ts`), limits and channel list. Use the two timestamps exactly as given. If it exits 2 there is no window in the run context: return `needs_escalation` with the reason. Never compute a window yourself.

2. **Missing IDs.** For each name in `channels_missing_id`, resolve it with `slack_search_channels`, then run `python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_channels.py --set-id "#name" <ID>`.

3. For each channel (skip those with `already_attempted: true` unless the caller asked for a re-fetch):
   1. **Roots.** `slack_read_channel` with `channel_id`, `oldest = oldest_ts`, `latest = latest_ts`, `limit = page_limit` and `response_format = "detailed"`. Follow `cursor` until exhausted. Drop bot messages (unless `include_bot_messages`) and join/leave/topic system messages.
   2. **Threads.** For every root with `reply_count > 0`, call `slack_read_thread` with `message_ts` = the root's ts, `limit = thread_limit`, `response_format = "detailed"`.
   3. **Names.** Resolve each distinct user ID once per run with `slack_read_user_profile`.
   4. **Payload, if there are messages.** Write `system/run/payloads/slack-<slug>-<target_date>.json` with the Write tool, using the schema in the docstring of `scripts/format_channel_file.py`. Set `"date": target_date`. Copy every `text` exactly. Take `ts` from the message's `Message TS:` line and `user_name` from its `Message from <name>` header. Do not write `permalink` or `time`: the formatter derives both from `ts`. Then run `python3 ${CLAUDE_SKILL_DIR}/scripts/format_channel_file.py --payload "system/run/payloads/slack-<slug>-<target_date>.json"`.
   5. **Silent day.** If there are no messages, run `python3 ${CLAUDE_SKILL_DIR}/scripts/format_channel_file.py --empty --channel "#<name>" --date <target_date>`.
   6. **Verbatim warnings.** If the output lists `verbatim_warnings`, re-fetch the flagged messages with the same calls (`response_format = "detailed"`) and rewrite the payload with the full schema: every message needs its real `ts` and `user_name`, not just `text`. Run the formatter again. Messages already in the file are deduped by ts.
   7. **MCP failure.** Record it in `warnings` and continue with the next channel. Do not run `--empty` for it: an absent ledger key is how the next run knows to retry.

4. **Return** one JSON object:
   - `counts`: `{"channels_ok": N, "channels_failed": N, "messages_added": N, "files_written": N}`, summed from formatter output, never recounted by hand
   - `outputs`: every `files_written` path
   - `status`: `success`; `partial` if any channel failed; `failed` if all did; `skipped` if the Slack connector is unavailable (reason: reconnect it in Settings, Connectors)
   - `observations`, only when true: a channel added more than `hot_day_threshold` messages; a transient channel silent for `stale_transient_dead_days` (check `scripts/ledger.py --query-date`); the same MCP error across channels

The formatter handles local-date routing, confidential wrapping, permalink derivation, dedup by
ts, counts, and resetting `wiki_processed`.

## Failure modes

| Symptom | What to do |
|---|---|
| Formatter exits 2 "missing required fields" | The payload only had `text`. Re-fetch and rewrite with `ts` and `user_name` |
| `verbatim_warnings` persist after a re-fetch | Leave them in the return `warnings`; never edit text by hand |
| Channel not in list | Add it to the channel list file; the formatter refuses unknown channels |
