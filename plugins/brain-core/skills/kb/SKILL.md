---
name: kb
description: Query and maintain the workspace knowledge base with the brain CLI. Look up anything by ID, run SQL over projects, entries, decisions, people and raw items, append dated sourced entries, raise proposals, and confirm or reject AI-written decisions and entries. Use for "what's open on X", "show me RSK-002", "log this risk", "confirm that decision", "what needs my attention".
allowed-tools: Bash(brain *) Read Write
---

# Knowledge base

Markdown is the source of truth; `system/kb.db` is a generated index (`brain kb build`). The
contract is in the workspace's `system/schema/` (`_schema.md`, `entry-grammar.md`, `kb.sql`).

## Read

| Need | Command |
|---|---|
| Rebuild the index (validates first; writes nothing on error) | `brain kb build` |
| Validate only | `brain kb build --check` |
| Everything about an ID (`[[id]]` accepted) | `brain kb show <id>` |
| SQL, JSON lines out | `brain kb query "<sql>"` |
| The attention list (`inbox/attention.md`) | `brain kb attention` |
| Trust tier of meetings for a project | `brain kb trust <slug> [--raw <id>]` |
| Regenerate `_index.md` files and README state blocks | `brain kb index` |

Tables: `entities`, `entries` (and the view `current_entries`: latest state per ID),
`decisions`, `people`, `project_members`, `raw_items`, `meeting_attendees`, `links`, `proposals`,
`sessions`, `fts` (full text: `select id, kind, title from fts where fts match 'tax quotes'`).

```
brain kb query "select key, state, owner, due from current_entries where project='checkout-revamp' and state in ('open','at-risk')"
brain kb query "select id, title, status, trust from decisions where status='proposed'"
```

Never quote the body of an item with `redact_content = 1` or `sensitivity: confidential` into anything shared.

## Write

**Append entries.** Write a payload with the Write tool to `system/run/payloads/<name>.json`, then
`brain kb append --project <slug> --file system/run/payloads/<name>.json`. Add `--dry-run` to
preview. The CLI validates every item before writing any, assigns the next number per prefix,
computes trust from the sources and prints the assigned IDs.

```json
{"project": "checkout-revamp", "entries": [
  {"id_prefix": "RSK", "status": "open", "by": "ai", "source": "mtg-2026-11-04-checkout-weekly", "owner": "sam-patel", "due": "2026-11-20", "body": "..."},
  {"id_prefix": "RSK", "id": "RSK-002", "status": "mitigated", "by": "ai", "source": "slack-2026-11-03-proj-checkout", "body": "..."},
  {"id_prefix": "DEC", "title": "Hold the 50% rollout", "by": "ai", "source": "mtg-2026-11-04-checkout-weekly", "body": "..."}
]}
```

- `id_prefix`: `STA`, `RSK`, `DEP`, `MS`, `RES`, `HYP` (facet entries) or `DEC` (a decision file).
- `status`: an entry state (`open`, `closed`, `mitigated`, `proposed`, `accepted`, `superseded`, `at-risk`, `on-track`, `off-track`, `done`, `slipped`). Decisions get theirs computed: `accepted` only from a HIGH-trust source that doesn't hedge, otherwise `proposed`.
- Pass `id` to update an existing entry (a new dated entry with the same ID). Check `current_entries` first so you don't open a duplicate.
- `source` is mandatory: raw IDs, entry IDs, or `owner`. `trust` is never typed; it is computed.
- Append never creates a facet file and never edits an old entry.

**Propose** an improvement (never auto-applied):
`brain kb propose --audience system|owner --title "..." --source <id> [--body "..." | --body-file <payload.md>]`.

**Confirm** what the owner approves: `brain kb confirm DEC-<slug>-NNN`, `brain kb confirm <slug>/RSK-002`,
`brain kb confirm PRP-003`; add `--reject` to reject. Run `brain kb build` first so the ID is indexed.
Only confirm on the owner's explicit say-so for that item.

## Failure modes

| Output | Meaning |
|---|---|
| `kb.db missing` | run `brain kb build` |
| build `status: error` with `file:line` | fix the grammar at that line; never delete an entry to pass |
| append `facet/prefix mismatch`, `unknown ID`, `source is mandatory` | fix the payload; nothing was written |
| `need exactly one entry (use project/ID)` | the ID exists in several projects; pass `<slug>/<ID>` |
