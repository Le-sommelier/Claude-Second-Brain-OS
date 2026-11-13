---
name: ingest-notes
description: Script-only brick (lane notes, no model). Normalises every note dropped into inbox/notes (markdown or text, with an optional header) into raw/notes/YYYY/YYYY-Www/note-YYYY-MM-DD-<slug>.md with frontmatter and pending-queue flags, then archives the original.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
---

# Notes: normalise brick

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/normalise.py
```

Applies by default; `--dry-run` reports only. It prints a brick-contract return object, which the
orchestrator collects as is. No model is involved: the script reads, normalises and files.

**Inbox:** `inbox/notes/*.md|*.txt` (`notes.inbox` in paths.json). Files starting with `_` or `.` are ignored.
**Output:** `raw/notes/YYYY/YYYY-Www/note-YYYY-MM-DD-<slug>.md`
**Archive:** originals move to `inbox/notes/_processed/`. Nothing is deleted.

## Optional header

The first lines of a file, up to the first blank line (or a YAML frontmatter block):

```
title: Retro takeaways
project: partner-api
people: Casey Nguyen, sam-patel
tags: retro, process
date: 2026-11-06
sensitivity: confidential

The note text starts here...
```

All keys are optional. `people` are slugged to `first-last` IDs. `project` is kept only when you wrote it;
otherwise it stays `null` and the wiki step decides. `sensitivity: confidential` stores the body inside
confidential markers. Date comes from the header, then a `YYYY-MM-DD` filename prefix, then the file time.
Title comes from the header, then a leading `# heading`, then the filename.

## Frontmatter written

`id, source_type: note, title, date, tags, people, project, sensitivity, source_file, content_sha,
wiki_processed: false, todo_processed: false`. The body is your text exactly as written.

## Guarantees and failure modes

- Never overwrites: an existing target gets a `-2` suffix (exclusive create).
- An identical body already in `raw/notes` counts as a duplicate: the original is archived, nothing written.
- An empty note stays in the inbox with a warning. A file that cannot be read gives status `partial`.
- Capture without a file: use `/brain-ingest-notes:note`.
