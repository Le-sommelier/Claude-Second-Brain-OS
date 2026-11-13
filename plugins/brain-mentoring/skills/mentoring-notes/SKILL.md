---
name: mentoring-notes
description: Capture a mentoring session after it happens. Writes the dated note, extracts actions with owners and dates, and ticks off the ones that are done. Use for "log my session with X", "mentoring notes", "capture the session", "here is what we discussed".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
---

# mentoring-notes

**Writes:** `growth/mentoring/<id>/sessions/<date>-session.md` and `actions.md`. Confidential, wrapped in markers.
The payload goes to `growth/mentoring/_run/` (inside growth, so it stays confidential) and is deleted on success.

## Steps

1. Get the material: what they say (or paste a transcript or notes). Ask for the **date** if it is not clear.
2. Read `growth/mentoring/<id>/actions.md` so you can close the right ids and not duplicate an action.
3. Write the payload with the Write tool to `growth/mentoring/_run/notes-<id>.json`:
   ```json
   {"date": "2026-11-19",
    "discussed": ["short factual bullet per topic, with its outcome"],
    "insights": ["what the mentee realised, or the pattern you noticed"],
    "actions": [{"owner": "<person-id or your own id>", "what": "concrete commitment", "due": "2026-12-03"}],
    "closed": ["A-003"]}
   ```
   Real commitments only, a due date only if one was said. Owners are the mentee's id, your id (from `.claude/brain.json`) or `both`.
4. `python3 ${CLAUDE_SKILL_DIR}/scripts/mentoring_notes.py --person <id> --payload growth/mentoring/_run/notes-<id>.json`
5. If it returns `invalid`, fix every listed error in the payload and run again (at most 3 tries). Nothing is written until it passes.
6. Report in two lines: the note path, and counts (actions added, closed, still open).

## Rules

- No personal-life detail, no performance ratings, nothing the mentee asked to keep off the record.
- Do not paste confidential notes into digests, the wiki or messages.
- If a growth evidence candidate comes out of the session (the mentee stepped up), leave it to `growth-signals`: it already mines `growth/mentoring/`.
