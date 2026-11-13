# Output style — wiki page

Use for pages bound for Confluence, a team wiki or any shared documentation space.

## Rules

- **Headings**: one H1 (the page title), H2 for sections, H3 for sub-sections. Never skip a level.
- **First paragraph**: two or three lines saying what the page is and who it's for.
- **Status**: when reporting RAG, put a fixed RAG table at the top. **Never invent or change a RAG colour** without explicit instruction.
- **Owners and dates** on every action, or `TBD` flagged explicitly.
- **Tables for status**: three to five columns (workstream, status, what moved, risk, owner).
- **Bullets over prose** for status; prose for context and rationale.
- **Link to the source**: cite the meeting summary or decision ID, not a raw transcript.
- **Diagrams**: Mermaid renders in most wikis; use it for flows and sequences, with short node labels.

## Never changes without instruction

- RAG colours on an existing page
- Page-to-URL mappings
- Owners listed on the page

## Templates

**Project status page**

```
# <Project> — week of <ISO date>

<Two or three lines: overall colour, headline event, biggest risk.>

## RAG snapshot

| Workstream | Status | Trend | Owner |
|---|---|---|---|

## What moved this week
## Risks and blockers
## Decisions needed
## Next week
```

**Decision page**

```
# Decision — <topic>

**Decided:** <one line>
**Date:** YYYY-MM-DD
**Owner:** ...
**Stakeholders:** ...

## Context
## Options considered
## Decision rationale
## Consequences and next steps
```
