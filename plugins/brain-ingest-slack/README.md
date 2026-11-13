# brain-ingest-slack

Slack for your second brain. Three bricks that the `brain-ingest` orchestrator runs in the `slack` lane of the fetch stage.

## Install

```
/plugin install brain-ingest-slack --marketplace YOUR-ORG/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

| Skill | Model | What it does |
|---|---|---|
| `ingest-slack-channels` | haiku | Copies the messages and threads of your watched channels, one file per channel per day, verbatim |
| `ingest-slack-flagged` | haiku | Collects every message you flagged with a reaction (default `:inbox_tray:`), once ever, via a permalink ledger |
| `ingest-owed-replies` | sonnet | On demand (disabled in the pipeline by default): who is waiting on you |

## Connector

The **Slack MCP connector**, read-only. Tools used: `slack_read_channel`, `slack_read_thread`,
`slack_read_user_profile`, `slack_search_channels`, `slack_search_public_and_private`. The tool
prefix depends on how the connector is installed (the skills assume `mcp__slack__`); allow-list
the real names in your settings. No write tool (send, react, canvas) is ever called.

## Configure

Setup copies two files into `.claude/brain/` (never overwriting them):

- `slack-channels.json`: the watched channels. Fields: `name`, `id` (optional, resolved on first run), `tags`, `sensitivity`, `transient`, `tech_decisions`. The template lists fictional Fernhill channels.
- `slack-config.json`: `timezone`, `workspace_url` (permalinks are derived from channel ID plus ts), `flag_reaction` (emoji name without colons), `owner_slack_user_id`, limits.

## Output

- `raw/slack/YYYY/YYYY-Www/slack-YYYY-MM-DD-<channel>.md`: per-channel day files, frontmatter `source_type: slack-channel`, `wiki_processed: false` (the pending queue).
- `raw/slack/YYYY/YYYY-Www/slack-YYYY-MM-DD-slack-ingest.md`: the day's flagged messages (`source_type: slack-flagged`, plus `todo_processed: false`).
- `inbox/owed-replies/YYYY-MM-DD-owed-replies.md`: the owed-replies digest.
- Ledgers in `system/run/`: channel attempts per date (an absent key is a gap the next run retries), flagged permalinks.

## Confidentiality

Channels marked `sensitivity: confidential`, or whose name matches the patterns in
`.claude/brain.json` (`*-leadership*`, `*-leads`, `*-exec*` by default), are stored inside
`<!-- CONFIDENTIAL: redact-on-share -->` markers with `sensitivity: confidential` and
`redact_content: true`. Downstream modules never quote them.

## Commands

Run by `/brain-ingest:ingest`. Manual: invoke a skill directly, for example `/brain-ingest-slack:ingest-slack-channels 2026-11-03`.
Scheduled tasks: none of its own; the daily run belongs to `brain-ingest`.
