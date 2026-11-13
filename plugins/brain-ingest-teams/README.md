# brain-ingest-teams

Meetings into `raw/meetings/`: Teams transcripts through the Microsoft 365 connector, plus VTT, TXT
and DOCX transcript drops. Contract: [docs/module-contract.md](../../docs/module-contract.md).

## Install

```
/plugin install brain-ingest-teams --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

**Connector:** Microsoft 365 (optional; read-only calendar and transcripts). Without it, the drop route still works.

| Skill | What |
|---|---|
| `ingest-teams` | Calendar-window lookup, transcript fetch, per-event retry ledger. Lane `m365`, Sonnet. |
| `ingest-meeting-files` | Script brick: VTT/TXT/DOCX to `raw/meetings/YYYY/YYYY-Www/mtg-*.md`, attendance, cross-route dedupe. |

**Outputs:** `raw/meetings/YYYY/YYYY-Www/mtg-YYYY-MM-DD-<slug>.md` (`wiki_processed: false`, `todo_processed: false`),
`_origin.json` and `duplicates/` per week, originals in `inbox/transcripts/_processed/`.
**Config:** `.claude/brain/teams.json` (lookback, retries, extra timezones).
**Scheduled tasks proposed:** none; the `brain-ingest` orchestrator runs both bricks in its `fetch` stage.
**Drop a transcript:** put `YYYY-MM-DD HH.MM.SS Title.vtt` in `inbox/transcripts/` and run `/brain-ingest-teams:ingest-meeting-files`.
