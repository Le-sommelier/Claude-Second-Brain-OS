---
name: one-on-ones
description: Detect new 1:1 meetings with the people on your roster, draft a short note for each, queue the drafts locally, and push each onto the person's page only when the owner says yes to that draft. Use for "draft my 1:1 notes", "push my 1:1 drafts", "process my one-on-ones", or as an ingest brick.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
---

# one-on-ones

Two modes. Mode 1 is local and safe to run unattended. Mode 2 changes people pages, so it needs a yes per draft.

**Reads:** `raw/meetings/**/mtg-*.txt|md` for roster meetings, the `.summary.md` beside each, the roster
(`.claude/brain/one-on-one-roster.json`), `references/note-style.md` (next to this file), the banned-word list in `BRAND.md` if present.
**Writes:** `growth/one-on-ones/queue/<person-id>/<id>.json`, the ledger `growth/one-on-ones/ledger.json`, and (mode 2) the person's page.
Everything is confidential: 1:1 content never goes in a return, a digest or a message.

## Mode 1: draft (brick, unattended)

Follows the brick contract: one JSON return, stats only.

1. First run only: `python3 ${CLAUDE_SKILL_DIR}/scripts/detect.py --init` records today as the go-live date (no back-fill).
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/detect.py`. If `count` is 0, return `skipped`, reason "no new roster 1:1s".
3. For each item, one at a time: read the transcript (the summary only to check you missed nothing), write the draft JSON following
   `references/note-style.md` to `growth/one-on-ones/payloads/1on1-<id>.json`, then
   `python3 ${CLAUDE_SKILL_DIR}/scripts/queue_draft.py --payload growth/one-on-ones/payloads/1on1-<id>.json`.
   On `invalid`, fix every listed error and rerun (at most 3 tries, then leave the payload and add a warning).
4. Return `counts` `{detected, queued, invalid}`, `outputs` (queued paths), `warnings`. Never put note text in the return.

## Mode 2: push (interactive)

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/queue_status.py`. If `queued` is 0, say so in one line and stop.
2. For each draft: `python3 ${CLAUDE_SKILL_DIR}/scripts/queue_status.py --show <id>`, show the entry to the owner, and ask: "Add this to <person>'s page?"
   Mention `withheld` (topics left out for being off the record or personal) only to the owner.
3. **Only on a yes to that draft:** `python3 ${CLAUDE_SKILL_DIR}/scripts/push_draft.py --id <id> --approved`. It inserts the entry first in the page's `## 1:1 log`,
   inside the confidential wrapper, updates `last_contact`, marks the ledger and deletes the queue file. A no leaves the draft queued; an edit means rewrite the
   queue file's text, then ask again.
4. Report one line per person: pushed or waiting.

## Boundaries

- Only people on the roster. Never draft a 1:1 with anyone else, even if a transcript suggests it.
- Never write a page without the per-draft yes. `--approved` is not a default.
- If the page is missing, run `brain new person <id>` first. Human-fenced sections are never changed (the script aborts otherwise).
- Never post notes to Slack, Confluence or email.

## Failure modes

`ledger missing`: run `detect.py --init`. `roster missing`: copy the roster template and list your people. `unknown person_id`: the draft's id is not in the roster.
Two copies of one meeting (same person, same day) are counted once.
