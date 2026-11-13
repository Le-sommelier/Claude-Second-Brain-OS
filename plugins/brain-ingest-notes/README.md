# brain-ingest-notes

Manual notes join the pipeline like any other source. Drop a `.md` or `.txt` into `inbox/notes/`, or
capture one in chat, and it becomes `raw/notes/YYYY/YYYY-Www/note-YYYY-MM-DD-<slug>.md` with
`wiki_processed: false` and `todo_processed: false`. Contract: [docs/module-contract.md](../../docs/module-contract.md).

## Install

```
/plugin install brain-ingest-notes --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

**Connectors:** none.

| Skill | What |
|---|---|
| `ingest-notes` | Script brick (lane `notes`, no model): normalise the inbox, parse the optional header, archive originals. |
| `note` | `/brain-ingest-notes:note`: save pasted or dictated text as a drop file, then normalise it. |

**Header syntax** (optional, first lines): `title:`, `project:`, `people:`, `tags:`, `date:`, `sensitivity: confidential`.
**Outputs:** `raw/notes/YYYY/YYYY-Www/note-*.md`; originals in `inbox/notes/_processed/`. Never overwrites.
**Scheduled tasks proposed:** none; the `brain-ingest` orchestrator runs the brick in its `fetch` stage.
