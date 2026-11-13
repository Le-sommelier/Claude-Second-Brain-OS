---
name: ingest-meeting-files
description: Script-only brick (lane m365, no model). Normalises every transcript waiting in the Teams inbox (VTT from ingest-teams) and the drop inbox (VTT, TXT or DOCX exported from Teams, Zoom or any recorder) into raw/meetings/YYYY/YYYY-Www/mtg-YYYY-MM-DD-<slug>.md with frontmatter, and dedupes the same meeting arriving by both routes.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
---

# Meeting files: normalise brick

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/prepare.py
```

Applies by default; `--dry-run` reports without moving anything. It prints a brick-contract return
object, which the orchestrator collects as is.

| Inbox (`meetings.*` in paths.json) | Accepts | Route |
|---|---|---|
| `teams_inbox` (`inbox/transcripts/teams`) | `*.vtt` from `ingest-teams`, optional `<name>.meta.json` `{"invited": [...]}` | `m365` |
| `inbox` (`inbox/transcripts`) | `*.vtt`, `*.txt`, `*.docx` dropped by hand | `drop` |

**Naming.** Date and time come from the filename: `YYYY-MM-DD HH.MM.SS Title`, `YYYY-MM-DD_HH-MM_Title`,
`YYYY-MM-DD Title`; with none, the file's creation time. Output is `mtg-YYYY-MM-DD-<slug>.md`; the
stem is the stable ID. A name collision gets a `-2` suffix, never an overwrite.

**Frontmatter written:** `id, source_type: meeting, title, date, time, origin, source_file, participants,
attendance, tags, sensitivity, wiki_processed: false, todo_processed: false`. `attendance` is computed
against the owner's `person_id` in `.claude/brain.json`: `attended` when the owner speaks, `invited-absent`
when only the calendar invite names them, otherwise `not-invited`.

**Dedupe.** The same meeting arriving via the m365 route and a hand drop counts once: same day and same
title or start within 10 minutes (or identical transcript text). The m365 copy wins; the other moves to the
week's `duplicates/` folder, with its summary if it has one. Nothing is deleted. `_origin.json` in the week
folder records where each raw file came from.

**After processing** the original moves to `inbox/transcripts/_processed/`. A transcript with no speech
stays in the inbox with a warning.

Failure modes: unreadable or corrupt DOCX -> warning, file left in place, status `partial`. A corrupt
`_origin.json` raises before anything is written. The script never summarises; brain-summarise reads the
pending queue.
