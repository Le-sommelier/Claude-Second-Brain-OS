---
name: stakeholder-map
description: Build the stakeholder map: an influence and interest grid with relationship health and who is overdue for contact, as a markdown file (mermaid chart plus table). Use for "stakeholder map", "who am I neglecting", "map my stakeholders", "who is at risk".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
---

# stakeholder-map

**Reads:** `people/*.md` frontmatter and `people/_org.yaml`. Only ratings, never notes.
**Writes:** `people/_stakeholder-map.md` (mermaid quadrant chart plus table). It is
marked confidential (module `confidential_globs`), because rating people is sensitive.

## Steps

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/build_map.py`. Prints counts: rated, unrated, at-risk, stale.
2. Tell the owner, in a few lines: who is **manage-closely** and overdue for contact, who is **at-risk**, and who is **unrated** (a number of pages with no
   `influence` and `interest` is the real gap; offer to fill them in with `person`).
3. Quadrants: influence 4-5 and interest 4-5 = manage closely; high influence, lower interest = keep satisfied; lower influence, high interest = keep informed;
   otherwise monitor. A person is stale when `last_contact` is older than their `cadence_days` (defaults: 14, 30, 30, 60 days by quadrant).
4. Offer a plan for the top two risks: what the relationship needs (a conversation, a pre-read, a favour returned), and a date.

## Rules

- Do not publish or post the map. It is for the owner. A shared version needs a fresh yes and ratings removed.
- Ratings are the owner's judgement. Do not change them from a transcript without asking.
- Dashes in a mermaid label break rendering; names are used as given.

## Failure modes

"no people pages found": run `person` to create pages first. Everyone unrated: add `influence` and `interest` (1 to 5) to the page frontmatter.
