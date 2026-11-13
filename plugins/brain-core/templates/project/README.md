---
title: {{TITLE}}
owner: {{OWNER_PERSON_ID}}
status: active
sensitivity: internal
last_reviewed: {{TODAY}}
---

<!-- generated -->
## Current state

- **Status**: no entries yet

<!-- /generated -->

# {{TITLE}}

<!-- human -->
> One paragraph: what this is, who it is for, why it matters, where it is heading.

## Goal

<!-- One sentence: what changes when this ships. -->

## Links

| Resource | Where |
|---|---|
| Channel | `#...` |
| Tracker | ... |
| Docs | ... |
<!-- /human -->

## How this folder works

- Facet logs (`status.md`, `risks.md`, `milestones.md`, `resources.md`, `hypotheses.md`) are
  append-only. Add entries with `brain kb append`, or by hand in the same grammar
  (`system/schema/entry-grammar.md`).
- `teams.md` lists the people on the project; it drives the trust tier of every source.
- `decisions/` holds one file per decision. `rollups/` holds monthly rollups.
- The block between the `generated` markers is rewritten by `brain kb index`. Everything between
  `human` fences is yours and is never rewritten by an agent.
