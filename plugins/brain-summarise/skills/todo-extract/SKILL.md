---
name: todo-extract
description: Derive brick. Consumes the todo pending queue (summaries and flagged Slack files with todo_processed false, last 7 days), extracts actions the owner owns or must chase, and adds them to the todo file's Inbox section. Run on demand with "pull my todos from recent meetings".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
model: sonnet
---

# Todo extract: derive brick

Follows the brick contract in `docs/module-contract.md` section 4. Enabled by default in this module.

**Reads:** the todo pending queue and the todo file (`core.todos`, default `todos/todo.md`).
**Writes:** appends cards under `## Inbox (from meetings)` in the todo file, through `add_todos.py` only. Cards elsewhere in the file belong to the owner and are never touched. Complex tasks may get a context note in `todos/notes/YYYY-MM-DD-<slug>.md`.
**State:** the `todo_processed` flag on each consumed item.

## Steps

1. **Queue.** Run:
   ```bash
   brain pending --flag todo_processed --max-age-days 7
   ```
   Items under `stale` are older than 7 days: flip them in step 5 without extracting anything (such an action is already stale or already on the board). If nothing else is pending, return `skipped`.

2. **Extract.** Read each item. Keep only:
   - actions whose owner is the owner (match `owner.first_name`, `owner.name` or `owner.person_id` from `.claude/brain.json`), and
   - actions whose owner is `unclear`, rewritten as "Confirm owner of ...".

   Skip other people's actions, observations and risks. For Slack, each message section is one unit and its YAML block gives the channel and permalink. Confidential items (`sensitivity: confidential`) yield cards that say what to do without names, amounts or quotes.

3. **Classify.**
   - **Simple:** the title alone is actionable. One card.
   - **Complex:** needs context, several steps, or depends on decisions in the source. Write `todos/notes/YYYY-MM-DD-<slug>.md` (context, steps, open decisions) and put its relative path in the card's `note` field.

4. **Add.** Write a JSON array to `system/run/payloads/todos.json` with the Write tool. Each element: `{"title": "...", "owner": "<name or person-id>", "source": "<source id>", "due": "YYYY-MM-DD" (optional), "tag": "<project slug>" (optional), "note": "<relative path>" (optional)}`. `<source id>` is the item's frontmatter `id`, else `slack-<file stem>`. Then run:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/add_todos.py --file system/run/payloads/todos.json
   ```
   The script validates first and writes second: it rejects cards owned by someone else, skips cards already present (same source and title), and prints `{"added", "skipped_duplicate", "rejected"}`. It deletes the payload after a successful write.

   Prefer proposals over cards when the owner has asked for a review step: `brain kb propose --title "<task>" --source <source id>` per card, and the owner accepts with `brain kb confirm`.

5. **Flip.** Write every processed and stale path to `system/run/payloads/todo-done.json` (a JSON array of workspace-relative paths), then run:
   ```bash
   brain flag --set todo_processed=true --files-from system/run/payloads/todo-done.json
   ```

6. **Return** one JSON object: `counts` `{"items": N, "cards_added": N, "cards_skipped": N, "notes_created": N}`, `outputs` the todo file plus any new notes, `warnings` for rejected cards.

## Failure modes

- `add_todos.py` exits non-zero on a malformed payload: nothing was written, items stay pending, return `failed` with the error.
- Todo file missing: the script creates it with a minimal header; tell the owner in `observations`.
