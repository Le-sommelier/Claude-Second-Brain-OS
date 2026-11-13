---
name: person
description: Create or update a person's page from evidence, and keep the org chart honest. Sets stakeholder ratings, adds confidential notes and dated evidence lines, never touches human-fenced text. Use for "add Sam to my people", "update Riley's page", "note that Jordan prefers...", "check the org chart".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
---

# person

**Owns on a people page** (see `${CLAUDE_PLUGIN_ROOT}/references/page-shape.md`): the frontmatter keys `relationship`, `influence`, `interest`, `health`,
`last_contact`, `cadence_days`, and the sections `## Stakeholder notes`, `## 1:1 log`, `## Evidence log`.
brain-wiki owns the rest. `<!-- human -->...<!-- /human -->` is never rewritten, and the script aborts if it would change.

## Create

1. `brain new person <first-last>` (core scaffolds the page). Then add the person to the chart:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/org.py add --id <id> --name "Full Name" --role "Title" --manager <manager-id> --team <team>`
   (it refuses duplicates and unknown managers).
2. Ask for ratings only if the owner knows them: influence 1-5 (how much they can move your work), interest 1-5 (how much they care),
   health (strong, ok, at-risk, unknown). Do not guess; unrated people are listed as such on the map.

## Update from evidence

1. Gather the evidence in the conversation or from a named raw item (a meeting summary id). Prefer the owner's own words.
2. Write the payload with the Write tool to `growth/one-on-ones/payloads/person-<id>.json`:
   ```json
   {"fields": {"influence": 4, "health": "strong", "last_contact": "2026-11-05"},
    "notes": [{"date": "2026-11-05", "text": "Prefers a written pre-read two days ahead."}],
    "evidence": [{"date": "2026-11-04", "text": "Presented the roadmap unaided", "source": "mtg-2026-11-04-roadmap-review"}]}
   ```
   One line per note. **Notes are impressions about a person: they are written inside a confidential wrapper automatically.** Evidence lines are
   factual, dated and sourced; they are deduplicated.
3. `python3 ${CLAUDE_SKILL_DIR}/scripts/person_page.py --id <id> --payload growth/one-on-ones/payloads/person-<id>.json` (add `--dry-run` to preview).
4. On `invalid`, fix the listed errors and rerun. Nothing is written until it passes.

## Check the chart

`python3 ${CLAUDE_SKILL_DIR}/scripts/org.py check` flags duplicate ids, a manager who is not in the chart, manager cycles (errors), and people with no page or
whose page disagrees with the chart (warnings). `org.py tree` prints the reporting tree.

## Rules

- Notes about people never go to shared surfaces. Do not quote them in digests, Slack drafts or Confluence drafts.
- No sensitive personal detail (health, family, compensation). If it is work-relevant, abstract it.
- Never edit `_org.yaml` records the owner wrote; `org.py add` only appends.
