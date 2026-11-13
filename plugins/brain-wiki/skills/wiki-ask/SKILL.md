---
name: wiki-ask
description: Answer a question from the knowledge base (projects, decisions, people, topics) using the kb index. Trigger on `/brain-wiki:wiki-ask <question>`, "ask the wiki ...", or any question about what is known, decided or risk-flagged on a project or person. Read-only; cites entry and raw IDs as [[id]].
allowed-tools: Bash(brain *) Read
model: sonnet
---

# Wiki ask: retrieval over the kb index

Answers from `projects/`, `people/` and `topics/` through `brain kb`. Returns a short answer grounded in entries and decisions, each cited by ID.

## Steps

1. **Find.** Run one or two of:
   - full text: `brain kb query "select id, kind, path from fts where fts match '<keywords>' limit 10"` (FTS5 syntax: `roadmap AND api`, `"exact phrase"`)
   - decisions: `brain kb query "select id, date, status, by, trust, title from decisions where project='<slug>' order by date desc limit 10"`
   - open risks: `brain kb query "select key, date, state, body from current_entries where project='<slug>' and facet='risks' and state in ('open','at-risk')"`
   - project state: read `projects/<slug>/README.md` (the generated current-state block)
   - a person: `people/<person-id>.md`; manager chain through `select id, manager from people`
   If `brain kb query` fails because the index is missing, run `brain kb build` once and retry.
2. **Read** at most four sources in full (`brain kb show <id>` for entries).
3. **Answer** in this shape and nothing more:
   ```
   **Answer (1-3 sentences).**
   **Evidence:**
   - <claim>. [[checkout-revamp/RSK-002]] (source: [[mtg-2026-11-04-checkout-weekly]])
   **Confidence:** high | medium | low, one line why (mention trust tier and proposed/ai status when it matters).
   ```
4. **Quotes.** For exact words, `brain kb show <raw id>` and open the file named in its `path`. Quote only non-confidential sources.

## Rules

- Read-only. Never edit entries, never write memory.
- Never invent. If nothing matches, say "the knowledge base does not cover this" and name the closest entries.
- Entries with `by: ai` and state `proposed` are unconfirmed: say so. The latest dated entry per ID is current state; note when it is older than 30 days.
- Confidential entries (`sensitivity: confidential`, redacted Slack, anything under the confidential globs such as `growth/`): abstract only. Refuse questions about performance ratings or pay.
- Style: terse, no preamble, no footer.
