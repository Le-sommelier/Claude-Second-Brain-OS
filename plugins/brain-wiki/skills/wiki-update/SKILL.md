---
name: wiki-update
description: Derive brick. Consumes the pending queue (every raw file or summary with wiki_processed false - meetings, Slack, Confluence, notes, web clips), routes each item to the projects it informs, and appends dated, sourced facet entries and decisions through `brain kb append`. Append-only: never rewrites a log. Use in the ingest derive stage or on demand.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
model: sonnet
---

# Wiki update: derive brick (facet append)

Follows the brick contract in `docs/module-contract.md` section 4. Knowledge lives in `projects/<slug>/`, `people/` and `topics/` as append-only logs written in the entry grammar (`system/schema/entry-grammar.md`) and indexed by `brain kb`. This brick never edits a page: a later entry with the same ID supersedes an earlier one.

**Reads:** the pending queue, `CRITICAL_FACTS.md`, `projects/*/README.md` (generated current state), `system/schema/entry-grammar.md`.
**Writes:** `projects/<slug>/{status,risks,milestones,resources,hypotheses}.md` and `projects/<slug>/decisions/*.md`, only through `brain kb append`.
**State:** the `wiki_processed` flag on each consumed item.

## Steps

1. **Queue.** Run:
   ```bash
   brain pending --flag wiki_processed
   ```
   Count 0: return `skipped` ("queue empty"). Skip any raw `mtg-*` item that has a sibling `<id>.summary.md`: the summary is the queue item, and the raw flag is a leftover to flip. Web clips older than 30 days stay pending and go in `warnings`.

2. **Route.** Read each item. Find the projects: `brain kb query "select id, title from entities where type='project'"`, then match on the item's `project`, `tags`, `category` and content. One item may inform several projects. An item that informs none goes in a "no target" list. The item's **source ID** is its frontmatter `id`; if absent, `slack-<file stem>` for Slack, `conf-<date>-<slug>` for Confluence, `src-<clipped>-<slug>` for web clips.

3. **Append.** One Sonnet subagent per project, in parallel. Each gets `CRITICAL_FACTS.md`, the entry grammar, the project's `README.md`, its items and their source IDs, and returns a JSON array of what is **new** (never restate older state; `[]` when nothing is):
   ```json
   {"facet": "risks|status|milestones|resources|hypotheses", "prefix": "RSK|DEP|STA|MS|RES|HYP",
    "id": "(optional: existing ID to update)", "date": "YYYY-MM-DD", "state": "<grammar state>",
    "body": "one or two sentences", "source": ["<source id>"], "owner": "<person-id>", "due": "YYYY-MM-DD", "rag": "green|amber|red"}
   ```
   or `{"type": "decision", "date", "title", "body", "source": [...]}`. Write the array to `system/run/payloads/facets-<slug>.json` with the Write tool, then run, one command per line:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/validate_facets.py --project <slug> --file system/run/payloads/facets-<slug>.json
   brain kb append --project <slug> --file system/run/payloads/facets-<slug>.json
   ```
   `kb append` assigns the next IDs, computes `trust` from meeting attendance and the project roster (`HIGH`: the owner or a project decision-maker attended; `MEDIUM`: a project team member attended; `LOW`: otherwise), and appends with `by: ai`. HIGH-trust, non-hedged decisions are confirmed (`ai-confirmed`); everything else lands `proposed` for the owner. Pass `--confidential-sources <ids>` to the validator when an item is confidential.

4. **Flip.** An item is done when every project it was routed to appended successfully, or it had no target. Write the done paths to `system/run/payloads/wiki-done.json`, then:
   ```bash
   brain flag --set wiki_processed=true --files-from system/run/payloads/wiki-done.json
   ```
   Items whose append failed stay pending.

5. **Return** one JSON object: `counts` `{"items": N, "items_done": N, "entries_appended": N, "decisions_appended": N, "projects_touched": N}` (copied from the script and CLI output), `outputs` the project files touched, `warnings` for failed appends and unresolvable source IDs. Do not rebuild the index here; the next ingest step runs `brain kb index`.

## Source adapters

| source_type | What to extract | Source ID |
|---|---|---|
| `meeting` | status and RAG shifts, risks and blockers (RSK/DEP), milestone moves, headcount and capacity (RES), decisions with the forum and who decided | frontmatter `id` |
| `slack-channel`, `slack-flagged` | decision-shaped messages ("we decided", "going with", "switching to", "rejected because") become `proposed` decisions; blockers and risks | `slack-<stem>` |
| `confluence-decision` | a page marked done becomes one decision (cite the page); other statuses give context for risks only | `conf-<date>-<slug>` |
| `note` | whatever the grammar covers; the owner's own notes are `by: ai` here too | frontmatter `id` |
| `web-clip` | nothing in facets; add a pointer under `## External References` only when a project README is clearly the home | `src-...` |
| unknown type | leave pending and add an observation | none |

## Confidential items

`sensitivity: confidential`, `redact_content: true`, or a source matching the confidential channel patterns in `.claude/brain.json`: abstract ("leadership discussed X"). Never names, amounts, ratings or quotes. Never create a decision from one unless a non-confidential item corroborates it. `brain kb append` tags entries citing such sources `sensitivity: confidential`.

## What this brick does not do

It does not edit pages, resolve contradictions or prune stale entries. Those are `contradiction-resolver` and `stale-pruner`, which only propose. Fenced `<!-- human -->` blocks are never touched.

## Failure modes

- `validate_facets.py` exits 1: fix the payload, never bypass; items stay pending if it cannot be fixed.
- `brain kb append` rejects a payload: nothing was written for that project. Warn and continue with the other projects.
