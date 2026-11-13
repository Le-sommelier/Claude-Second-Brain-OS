---
name: new-project
description: Scaffold a new project (or topic) in the workspace from brain-core's templates, with the five append-only facet logs, teams.md, decisions/ and rollups/, then fill in the human sections with the owner. Use for "start a project for X", "add a project", "track this theme as a topic".
argument-hint: "<slug> [title]"
allowed-tools: Bash(brain *) Read Edit
---

# New project

## Inputs

- A slug in kebab-case (`checkout-revamp`). Suggest one from the name if the owner gives a phrase.
- Optional title; defaults to the slug in title case.
- Project or topic: a project has a team, milestones and decisions; a topic is a long-running
  theme with notes and hypotheses. Ask if unclear.

## Steps

1. Preview: `brain new project <slug> --title "<Title>" --dry-run` (or `brain new topic ...`). Show
   the file list. It refuses if the folder exists; nothing is overwritten.
2. On a yes, run it without `--dry-run`.
3. Ask the owner, one question at a time, and fill only the `<!-- human -->` sections of
   `README.md` with Edit: the one-paragraph pitch, the goal (one measurable sentence) and links.
4. For a project, ask who is on the team and their roles, and fill `teams.md` frontmatter
   (`person`, `role`, `owner: true`, `decision_maker: true`). Use person IDs from `people/_org.yaml`;
   for someone new, offer `brain new person <first-last>` and remind the owner to add them to the
   org chart. Who is an owner or decision-maker decides which meetings count as HIGH trust.
5. Optionally record the first status and milestones. Write them as a payload in
   `system/run/payloads/` and run `brain kb append --project <slug> --file <payload>`:

   ```json
   {"project": "<slug>", "entries": [
     {"id_prefix": "STA", "status": "on-track", "by": "human", "source": "owner", "rag": "green", "body": "Kick-off."},
     {"id_prefix": "MS", "status": "open", "by": "human", "source": "owner", "owner": "<person-id>", "due": "YYYY-MM-DD", "body": "First milestone."}
   ]}
   ```
6. Run `brain kb build` then `brain kb index` so the README's current-state block fills in.

## Outputs

`projects/<slug>/` with `README.md`, `status.md`, `risks.md`, `milestones.md`, `resources.md`,
`hypotheses.md`, `teams.md`, `decisions/_template.md`, `rollups/_README.md` (topics: `README.md`,
`hypotheses.md`).

## Failure modes

- `already exists`: offer to open the existing project instead.
- `not kebab-case`: suggest a corrected slug.
- `brain kb build` errors after step 5: show the `file:line` and fix the entry, never delete it.
