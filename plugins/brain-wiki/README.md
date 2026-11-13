# brain-wiki

Keeps the knowledge base current from the pending queue, and answers questions from it. Everything writes through `brain kb` into append-only logs under `projects/`, `people/` and `topics/` (KB v3).

## Install

```
/plugin install brain-wiki --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

| Skill | Role | Model | Writes |
|---|---|---|---|
| `wiki-update` | derive brick: routes pending items to projects, appends sourced facet entries and decisions (`by: ai`, trust tiers) | Sonnet | `projects/<slug>/*.md` via `brain kb append` only |
| `wiki-ask` | answer a question with `[[id]]` citations, confidence and trust notes | Sonnet | nothing |
| `contradiction-resolver` | surfaces clashing or duplicate entries, proposes the reconciling entry | Sonnet | proposals only |
| `stale-pruner` | surfaces live-but-untouched entries and decisions, proposes close or keep | Sonnet | proposals only |

Rewriting is never silent: logs are append-only, a later entry with the same ID supersedes, and `<!-- human -->` fenced blocks are never touched.

## Connectors

None.

## Commands

`/brain-wiki:wiki-update`, `/brain-wiki:wiki-ask <question>`, `/brain-wiki:contradiction-resolver`, `/brain-wiki:stale-pruner`.

## Scripts

- `validate_facets.py` - pre-checks a facet payload before `brain kb append`.
- `find_stale.py`, `find_conflicts.py` - deterministic candidate finders (read-only).
- `scripts/kbparse.py` - small reader for the entry grammar, shared by the three scripts.

## Scheduled tasks

None of its own. `wiki-update` runs in the ingest derive stage (`brain-ingest`); the two maintenance skills are meant to be called from the weekly system review (`brain-learning-loop`) or by hand.

## Left out on purpose

The legacy `wiki-index` brick: `brain kb index` generates `_index.md` for every folder, so a separate index adds nothing.

See `docs/module-contract.md`.
