---
name: ingest-owed-replies
description: Fetch brick (disabled in the pipeline by default). Sweeps roughly the last 14 days of Slack for messages genuinely waiting on the owner's reply (flagged messages, unanswered DMs, unanswered direct mentions) and writes a dated digest. Precision over recall. Read-only. Run on demand with "who do I owe a reply to?".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write mcp__slack__slack_search_public_and_private mcp__slack__slack_read_channel mcp__slack__slack_read_thread
model: sonnet
---

# Owed replies: fetch brick

Follow the brick contract (`docs/module-contract.md` section 4). From `system/run/run-context.json`
you need `today` and `slack.owed_after`. For a manual run with no context, use today minus 14 days.

**Connector:** the Slack MCP: `slack_search_public_and_private`, `slack_read_channel`, `slack_read_thread`. Read-only.
**Config:** `owner_slack_user_id` and `flag_reaction` in the Slack settings file (paths.json slack.settings). Read it first; if the ID is empty, return `needs_escalation` and ask the owner to fill it in.
**Writes:** `inbox/owed-replies/YYYY-MM-DD-owed-replies.md` (paths.json slack.owed_dir)
**State:** none. Each run is a fresh view of the last 14 days.

## What counts as owed

Dedupe by permalink. Better to miss an item than to cry wolf. Search with `limit = 20`,
`include_context = false`, `response_format = "detailed"`. `<ME>` is `owner_slack_user_id`.

| kind | query | keep when |
|---|---|---|
| `inbox_flag` | `hasmy::<emoji>: after:<owed_after>` | always: the owner flagged it |
| `dm` | `to:me after:<owed_after>`, `channel_types = "im,mpim"` | the true last message (verify with `slack_read_channel` or `slack_read_thread`, since search misorders threads) is not the owner's and is a real ask, not "thanks", "cool" or "sounds good" |
| `mention` | `<@<ME>> after:<owed_after>` | a clear direct ask the owner has not answered anywhere in the thread. An emoji reply counts as answered |

## Steps

1. Run the three searches and apply the filters.
2. Write the kept items as a JSON array to `system/run/payloads/owed-replies.json`. Each item is `{"kind", "permalink", "channel", "author", "ts", "text", "confidential"}`. `text` is verbatim. `confidential` is true for channels the owner marked confidential; the script also detects them by name.
3. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/format_owed_replies.py --payload "system/run/payloads/owed-replies.json" --date <today>`. If a search errored, do not write a payload: return `failed` and leave the previous digest in place. The script refuses bad input anyway.
4. Return `counts` = the script's `by_kind`, `outputs` = `[file]`, `warnings` = its `verbatim_warnings`.
