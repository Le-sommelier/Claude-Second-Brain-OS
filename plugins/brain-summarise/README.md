# brain-summarise

Turns raw meeting transcripts into structured summaries, then pulls the owner's actions into the todo file.

## Install

```
/plugin install brain-summarise --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

| Skill | Stage | Model | What it does |
|---|---|---|---|
| `meeting-summarise` | transform | Haiku | One `<id>.summary.md` beside every raw `mtg-*` transcript (`.txt` or `.md`) that lacks one: purpose, updates, decisions, actions, risks, leadership feedback. Queued with `wiki_processed: false` and `todo_processed: false`. |
| `todo-extract` | derive | Sonnet | Reads the `todo_processed` queue, keeps actions the owner owns (or that have no clear owner), appends cards to the todo file's `## Inbox (from meetings)` section. Enabled by default. |

## Connectors

None. Both skills read local files only.

## Commands

- `/brain-summarise:meeting-summarise` - summarise unsummarised transcripts now (also runs inside the ingest pipeline).
- `/brain-summarise:todo-extract` - pull todos from recent summaries and flagged Slack files.

## Reads and writes

- Reads `raw/meetings/YYYY/YYYY-Www/mtg-* (.txt or .md)`, `people/_org.yaml`, `projects/*/README.md`, `.claude/brain.json`.
- Writes `raw/meetings/YYYY/YYYY-Www/<id>.summary.md` (frontmatter: `id, date, attendees, attendance, project, meeting_type, wiki_processed`, plus `todo_processed`), and the Inbox section of `todos/todo.md`.
- Confidential meetings are stored inside `<!-- CONFIDENTIAL: redact-on-share -->` markers with `sensitivity: confidential`, and todo cards from them carry no names, amounts or quotes.

## Queue flags: where they live

The **summary** carries `wiki_processed` and `todo_processed`; it is the queue item the wiki and todo bricks consume. When a fetched raw `mtg-*.md` also carries those flags, `meeting-summarise` flips them to `true` on the raw file once the summary is on disk, so a meeting is never processed twice. Raw transcripts stay otherwise untouched.

## Optional config

`.claude/brain/summarise.json` (created by you, not required): `{"tags": ["checkout-revamp", "partner-api"]}` limits the tag vocabulary.

## Scheduled tasks

None of its own: the ingest orchestrator (`brain-ingest`) runs both bricks on its schedule.

See `docs/module-contract.md` for the brick contract.
