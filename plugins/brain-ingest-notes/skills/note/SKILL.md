---
name: note
description: Capture a note the owner dictates or pastes in chat ("note this", "save this note", "remember this meeting thought") into inbox/notes, then normalise it into raw/notes so it joins the wiki pipeline. Use when the owner wants text kept without creating a file by hand.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/../ingest-notes/scripts/*) Bash(brain *) Write
---

# Capture a note

Purpose: turn pasted or dictated text into a raw note without the owner touching the filesystem.

1. **Collect.** The note text is whatever the owner gave you, exactly. Do not tidy, summarise or
   reword it. If they named a title, project, people or tags, keep them for step 3; do not guess any
   you were not given (the wiki step decides the project).
2. **Write the payload** with the Write tool to `system/run/payloads/note.md`: the note text only.
3. **Drop it.** One command, from the workspace root (omit flags you have no value for):
   `python3 ${CLAUDE_SKILL_DIR}/scripts/drop.py --payload system/run/payloads/note.md --title "<title>" --project "<project>" --people "<A, B>" --tags "<x, y>"`
   It writes `inbox/notes/YYYY-MM-DD <title>.md` with a header and deletes the payload.
4. **Normalise.** `python3 ${CLAUDE_SKILL_DIR}/../ingest-notes/scripts/normalise.py` files it into
   `raw/notes/` with `wiki_processed: false`. Report the output path and nothing else.

Failure modes: an empty note is refused (`ok: false`); a name collision gets a `-2` suffix, never an
overwrite. Notes are the owner's own words: never publish or share them without an explicit yes.
