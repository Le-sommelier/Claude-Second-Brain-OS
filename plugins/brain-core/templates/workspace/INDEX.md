# INDEX — workspace map

Where things live. Paths are the defaults from `.claude/paths.json`; that file wins if they
differ. Each content folder also has a generated `_index.md` (`brain kb index`).

| Folder | Holds | Written by |
|---|---|---|
| `CRITICAL_FACTS.md`, `CLAUDE.md`, `RULES.md` | anchor and contract | {{OWNER_FIRST_NAME}} |
| `SOUL.md`, `BRAND.md` | identity and voice | {{OWNER_FIRST_NAME}} |
| `MEMORY.md` | learning store, newest first | Claude and the learning loop |
| `raw/` | immutable source material by kind and ISO week | ingest bricks |
| `projects/<slug>/` | facet logs, `teams.md`, `decisions/`, `rollups/`, `artefacts/` | `brain kb append` and {{OWNER_FIRST_NAME}} |
| `topics/<slug>/` | long-running themes that are not projects | `brain kb` and {{OWNER_FIRST_NAME}} |
| `people/` | person pages and `_org.yaml` | stakeholders module and {{OWNER_FIRST_NAME}} |
| `digests/` | weekly and monthly rollups | digests module |
| `growth/` | career and reviews (confidential) | growth module and {{OWNER_FIRST_NAME}} |
| `inbox/` | `attention.md`, `proposals/` | `brain kb attention`, learning loop |
| `todos/` | `todo.md`, `done.md` | {{OWNER_FIRST_NAME}} (agents only propose) |
| `system/` | `schema/`, `run/` (ingest state), `kb.db` (generated) | brain-core |
| `.claude/` | `brain.json`, `paths.json`, `rules/`, `output-styles/`, module config in `brain/` | setup and {{OWNER_FIRST_NAME}} |
| `.secrets/` | `apis.env` (never committed) | {{OWNER_FIRST_NAME}} |

## Installed modules

{{MODULES_LIST}}

Re-run `/brain-core:setup` after installing or removing a module; it merges paths, folders and
ingest bricks without overwriting anything.
