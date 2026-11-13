---
name: ingest-slack-flagged
description: Fetch brick. Collects every Slack message the owner flagged with the configured reaction (default :inbox_tray:), in any channel, DM or group DM, with its full thread, into the day's flagged file under raw/slack/. A permalink ledger means each flag is ingested exactly once. Verbatim and read-only.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write mcp__slack__slack_search_public_and_private mcp__slack__slack_read_thread mcp__slack__slack_read_user_profile
model: haiku
---

# Slack flagged messages: fetch brick

Follow the brick contract (`docs/module-contract.md` section 4). From
`system/run/run-context.json` you need `today` and `slack.flagged_after`; if absent, return
`needs_escalation`. You only ever read from Slack: reacting to a message to "mark it done" is a
write and is not allowed.

**Connector:** the Slack MCP: `slack_search_public_and_private`, `slack_read_thread`,
`slack_read_user_profile`.
**Writes:** `raw/slack/YYYY/YYYY-Www/slack-YYYY-MM-DD-slack-ingest.md` (the ingest day)
**State:** the flagged ledger (permalinks already ingested; written by the formatter)
**Config:** `flag_reaction` and `owner_slack_user_id` in the Slack settings file (paths.json slack.settings). Read it with the Read tool. `<emoji>` below is the `flag_reaction` value.

## Steps

1. **Search.** `slack_search_public_and_private` with `query = "hasmy::<emoji>: after:<flagged_after>"`, `sort = "timestamp"`, `sort_dir = "desc"`, `limit = 20`, `include_context = false`, `response_format = "detailed"`. Paginate with `cursor`. `hasmy::` means the owner reacted, whoever wrote the message. The window is deliberately wide: the ledger drops anything already ingested.

2. **Hydrate each hit.**
   - Hit is a reply (`thread_ts` differs from `ts`): fetch the parent thread with `slack_read_thread` (`message_ts = thread_ts`, `limit = 1000`, detailed). The parent becomes the primary message and the flagged reply sits in its thread.
   - Hit has replies (`reply_count > 0`): fetch its thread the same way.
   - Resolve each user ID once with `slack_read_user_profile`.

3. **Tag and score.**
   - `tags`: the `tags` of the matching channel in the channel list (paths.json slack.channels_config), plus obvious project or topic names from `projects/` and `topics/`. Empty is fine.
   - `signal_quality`: `high` for a decision, a blocker, a named action, or an author who is a manager or exec (check `people/_org.yaml` if it exists); `medium` for a concrete update; `low` for social messages or a bare link.
   - Authors you cannot place become an `observation`.

4. **Format.** Write all messages to `system/run/payloads/slack-flagged.json` (schema in the docstring of `scripts/format_flagged_file.py`), copying every `text` exactly. Then run `python3 ${CLAUDE_SKILL_DIR}/scripts/format_flagged_file.py --payload "system/run/payloads/slack-flagged.json" --date <today>`. If the search found nothing, skip this step and return `skipped` with reason `"no flagged messages"`.

5. **Re-fetch on warnings.** If `verbatim_warnings` is not empty, re-fetch those messages and run the formatter again. The ledger makes this safe.

6. **Return:** `counts` = `{"messages_added": N, "already_ingested": N}` copied from the formatter; `outputs` = `[file]`.

Messages from confidential channels are wrapped in CONFIDENTIAL markers by the formatter and the
file becomes `sensitivity: confidential`. Never quote them in a return.
