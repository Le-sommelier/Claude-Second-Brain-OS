# INDEX — workspace map

Where things live. Paths are the defaults from `.claude/paths.json`; that file wins if they
differ. Each content folder also has a generated `_index.md` (`brain kb index`).

| Folder | Holds | Written by |
|---|---|---|
| `CRITICAL_FACTS.md`, `CLAUDE.md`, `RULES.md` | anchor and contract | Alex |
| `SOUL.md`, `BRAND.md` | identity and voice | Alex |
| `MEMORY.md` | learning store, newest first | Claude and the learning loop |
| `raw/` | immutable source material by kind and ISO week | ingest bricks |
| `projects/<slug>/` | facet logs, `teams.md`, `decisions/`, `rollups/`, `artefacts/` | `brain kb append` and Alex |
| `topics/<slug>/` | long-running themes that are not projects | `brain kb` and Alex |
| `people/` | person pages and `_org.yaml` | stakeholders module and Alex |
| `digests/` | weekly and monthly rollups | digests module |
| `growth/` | career and reviews (confidential) | growth module and Alex |
| `inbox/` | `attention.md`, `proposals/` | `brain kb attention`, learning loop |
| `todos/` | `todo.md`, `done.md` | Alex (agents only propose) |
| `system/` | `schema/`, `run/` (ingest state), `kb.db` (generated) | brain-core |
| `.claude/` | `brain.json`, `paths.json`, `rules/`, `output-styles/`, module config in `brain/` | setup and Alex |
| `.secrets/` | `apis.env` (never committed) | Alex |

## Installed modules

brain-core, brain-ingest, brain-ingest-slack, brain-ingest-teams, brain-ingest-confluence, brain-ingest-notes, brain-summarise, brain-wiki, brain-digests, brain-growth, brain-mentoring, brain-stakeholders, brain-learning-loop, brain-steal-list, brain-grill

Re-run `/brain-core:setup` after installing or removing a module; it merges paths, folders and
ingest bricks without overwriting anything.
