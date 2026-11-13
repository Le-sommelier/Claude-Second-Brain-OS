# brain-ingest-confluence

A general Confluence ingest: you list what to watch, it mirrors changed pages into `raw/confluence/`
verbatim and re-queues a page whenever its version changes. Contract: [docs/module-contract.md](../../docs/module-contract.md).

## Install

```
/plugin install brain-ingest-confluence --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

**Connector:** Atlassian (Confluence), read-only.
**Skill:** `ingest-confluence` (lane `atlassian`, Haiku).
**Config:** `.claude/brain/confluence-watch.json`, from `templates/confluence-watch.json`: `spaces` (optionally narrowed by labels),
`page_ids`, `labels`, free `cql` (use `{since}`), `decision_detection` (title patterns and labels that add a `decision-page` tag),
`confidential_labels`, `lookback_days`, `max_pages_per_run`.
**Outputs:** `raw/confluence/YYYY/YYYY-Www/conf-YYYY-MM-DD-<slug>.md` with page id, version, url, space, labels in frontmatter
and `wiki_processed: false`. State in `system/run/confluence-state.json`.
**Scheduled tasks proposed:** none; the `brain-ingest` orchestrator runs it in its `fetch` stage.
